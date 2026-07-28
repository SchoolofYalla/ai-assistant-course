"""
Gemini Live Audio Proxy
-----------------------
Replaces the entire Whisper + eval + TTS pipeline with a single
bidirectional Gemini Live session. Python is a pure proxy — no STT,
no separate LLM call, no TTS. Latency: < 1 second.
"""

import os
import os
import asyncio
import json
import base64
import struct
import io
import math
import wave
import uuid
import re
import azure.cognitiveservices.speech as speechsdk
from openai import AsyncOpenAI
from google import genai
from google.genai import types
from fastapi import WebSocket, WebSocketDisconnect
from vocabulary import DAILY_VOCABULARY


def safe_print(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"))


def is_audio_silent(wav_bytes: bytes, threshold: float = 5.0) -> bool:
    try:
        with wave.open(io.BytesIO(wav_bytes), 'rb') as w:
            frames = w.readframes(w.getnframes())
            if w.getsampwidth() == 2: # 16-bit
                samples = struct.unpack(f"<{len(frames)//2}h", frames)
                if not samples:
                    return True
                sum_sq = sum(float(s) * float(s) for s in samples)
                if len(samples) > 0:
                    rms = math.sqrt(sum_sq / len(samples))
                    return rms < threshold
    except Exception:
        pass
    return False


def create_wav_header(pcm_data: bytes, sample_rate: int = 16000) -> bytes:
    num_channels = 1
    bytes_per_sample = 2
    byte_rate = sample_rate * num_channels * bytes_per_sample
    
    header = b'RIFF'
    header += struct.pack('<L', 36 + len(pcm_data))
    header += b'WAVE'
    header += b'fmt '
    header += struct.pack('<L', 16)
    header += struct.pack('<H', 1)
    header += struct.pack('<H', num_channels)
    header += struct.pack('<L', sample_rate)
    header += struct.pack('<L', byte_rate)
    header += struct.pack('<H', num_channels * bytes_per_sample)
    header += struct.pack('<H', bytes_per_sample * 8)
    header += b'data'
    header += struct.pack('<L', len(pcm_data))
    
    return header + pcm_data

# Pre-computed STT phonetic replacement dictionary
def _strip_harakat_fn(t: str) -> str:
    t = re.sub(r'[\u064B-\u065F\u0670\u0640]', '', t)
    return re.sub(r'\s+', ' ', t).strip()

GLOBAL_MAPPINGS = []
for day_id, word_list in DAILY_VOCABULARY.items():
    for item in word_list:
        ar = item.get("target_arabic", "").strip()
        trans = item.get("transliteration", "").strip().lower()
        if not ar: continue
        
        variants = []
        if trans:
            variants.append(trans)
            clean_trans = re.sub(r'[37]', '', trans)
            if clean_trans and clean_trans not in variants:
                variants.append(clean_trans)

        clean_ar = _strip_harakat_fn(ar)
        if 'مرحبا' in clean_ar:
            variants.extend(['merhaban', 'merhaba', 'mer7aba', 'merhabah', 'merhabaa', 'madhuban', 'mahuban', 'mahaban', 'madhaban', 'mudhaban', 'marhaban', 'marhaba', 'mar7aba', 'marhabah', 'marhabaa', 'medhaban'])
        elif 'مرحبتين' in clean_ar:
            variants.extend(['merhabatayn', 'merhabten', 'mer7abtyn', 'mehabatain', 'mehabadein', 'mehabaten', 'mahabadain', 'mahabadein', 'mahabaten', 'mahabatin', 'madhabadain', 'madhabadein', 'mahabatain', 'mahabatein', 'marhabatayn', 'marhabten', 'mar7abtyn', 'medhabitain'])
        elif 'السلام عليكم' in clean_ar and 'وعليكم' not in clean_ar:
            variants.extend(['assalamu alaykum', 'assalaamu 3alaykom', 'assalamu alaikum', 'assalam alaykum', 'alsalam alaykum', 'salamu alaykum', 'salam alaykum', 'es salam'])
        elif 'وعليكم' in clean_ar:
            variants.extend(['while i come was salam', 'while i come', 'wale como salaam', 'wale como', 'waleco musselam', 'waleco muselam', 'waleco mussalam', 'waleico musselam', 'waleco', 'musselam', 'wa alaykum assalam', 'wa 3alaykom assalaam', 'wa alaikum salam', 'w alaykom assalam', 'waleikum was salam', 'walaikum was salaam', 'waleikum'])
        elif 'يعطيك' in clean_ar:
            variants.extend(['yahtzee kalafia', 'yahtzee', 'kalafia', 'yateek al afia', 'yateek al afiya', 'yatika lafia', 'yatika alafia', 'yateek al afiyeh', 'ya3teek il 3aafyeh', 'ya3teek el afyeh', 'yateeki al afia', 'yateeki al afiya', 'yatiki lafia', 'yatiki alafia', 'yatika', 'yatiki', 'yetika', 'yetiki'])
        elif 'الله يعافيك' in clean_ar:
            variants.extend(['allah y3aafeek', 'allah yafeek', 'allah ya3feek', 'allah yfika', 'allah yafika', 'allah yafik', 'allah y3aafeeki', 'allah yafeeki', 'allah yfiki'])

        unique_variants = sorted(list(set(variants)), key=len, reverse=True)
        GLOBAL_MAPPINGS.append((ar, unique_variants))


def build_system_prompt(vocab_list: list) -> str:
    """Build the Gemini system prompt with the vocabulary list and usage contexts embedded."""
    words_text = "\n".join([
        f"{i + 1}. {w.get('english_intro', 'Word:')} {w['target_arabic']}"
        for i, w in enumerate(vocab_list)
    ])

    return f"""You are a warm, encouraging Levantine Arabic pronunciation coach for School of Yalla.

Your job today is to teach the student these words one by one, clearly explaining what each word is used for (e.g. casual greeting, formal response, to a male, to a female) before asking them to repeat:
{words_text}

SESSION FLOW — CRITICAL:
1. Greet the student in English, state what the first word is used for (e.g. "First, the casual greeting:"), say "Repeat after me:", AND pronounce the FIRST Arabic word ALL TOGETHER IN ONE SINGLE CONTINUOUS SPOKEN SENTENCE without pausing or ending your turn early.
2. Listen to the student repeat it.
3. Evaluate their attempt:
   - CORRECT: Say a brief English compliment (e.g. "Great job!"), state what the NEXT word is used for (e.g. "Now the casual response:"), then say "Repeat after me:" followed immediately by the NEXT Arabic word in the SAME continuous turn.
   - INCORRECT: Give a brief 1-sentence English correction, then say "Let me model it again for you:" followed immediately by the target Arabic word.
4. After all words in the lesson are completed, warmly congratulate the student in English, say goodbye clearly, and state that the lesson is now complete.

CRITICAL SCRIPT & PRONUNCIATION RULES:
- ALWAYS explain what each word is used for (casual, formal, response, male/female) exactly as listed in the School of Yalla lesson guide.
- ALWAYS write target Arabic words ONLY in actual Arabic script (e.g. مَرْحَبًا, مَرْحَبَتيْن, السَّلَامُ عَلَيْكُم, وَعَلَيْكُمُ السَّلَام, يَعْطِيكَ الْعَافِيَة, الله يَعَافِيك).
- ABSOLUTELY NEVER write or output English transliterations under any circumstances.
- Speak Arabic words slowly, clearly, with correct Levantine dialect pronunciation.

STYLE RULES - ABSOLUTELY MANDATORY:
- NEVER output internal thoughts, stage directions, or narration.
- Speak directly and naturally to the user as if on a voice call. ONLY output the exact words you want to say out loud.
- Keep explanations very SHORT and clear — maximum 2 short sentences per turn.

START NOW — greet the student in English, explain the usage of the first word, and say the first Arabic word in ONE continuous turn."""


async def run_live_session(websocket: WebSocket, vocab_list: list):
    """
    Opens a Gemini Live session and proxies bidirectional audio between
    the browser WebSocket and the Gemini Live API.

    Browser → binary PCM Int16 @ 16kHz → Gemini Live
    Gemini Live → binary PCM @ 24kHz → Browser (as base64 JSON chunks)
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        await websocket.send_json({"type": "error", "message": "Gemini API Key is missing."})
        return

    client = genai.Client(api_key=gemini_key)
    system_prompt = build_system_prompt(vocab_list)

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=system_prompt,
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
            )
        ),
    )

    safe_print(f"[Live] Starting Gemini Live session with {len(vocab_list)} words...")

    try:
        async with client.aio.live.connect(
            model="gemini-2.5-flash-native-audio-latest",
            config=config
        ) as session:
            safe_print("[Live] Gemini Live connected.")
            await websocket.send_json({"type": "session_started"})

            # Kick off Gemini's opening turn — explicitly pass the first target word
            first_word = vocab_list[0]['target_arabic'] if vocab_list else "مَرْحَبًا"
            await session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part(text=f"Hi! I'm ready to practice. Please greet me in English and say 'Let's begin! Repeat after me:' followed clearly by the first Arabic word: {first_word}")]
                ),
                turn_complete=True
            )

            # Track whether the frontend has muted the mic (while Gemini speaks)
            mic_muted = False
            
            # --- Azure Streaming STT Setup ---
            loop = asyncio.get_running_loop()
            azure_key = os.getenv("AZURE_SPEECH_KEY")
            azure_region = os.getenv("AZURE_SPEECH_REGION", "eastus")
            
            ai_bubble_id = str(uuid.uuid4())
            user_bubble_id = str(uuid.uuid4())
            ai_recognizer = None
            user_recognizer = None
            ai_push_stream = None
            user_push_stream = None

            if azure_key:
                ai_stream_format = speechsdk.audio.AudioStreamFormat(samples_per_second=24000, bits_per_sample=16, channels=1)
                ai_push_stream = speechsdk.audio.PushAudioInputStream(stream_format=ai_stream_format)
                ai_audio_config = speechsdk.audio.AudioConfig(stream=ai_push_stream)
                ai_speech_config = speechsdk.SpeechConfig(subscription=azure_key, region=azure_region)
                ai_auto_detect = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(languages=["en-US", "ar-JO"])
                ai_recognizer = speechsdk.SpeechRecognizer(
                    speech_config=ai_speech_config,
                    auto_detect_source_language_config=ai_auto_detect,
                    audio_config=ai_audio_config
                )
                def post_process_transcript(text: str) -> str:
                    """Strictly enforce proper Arabic script for any target Arabic word or phonetic STT mistranscription."""
                    if not text: return text
                    # 1. Marhabatayn variants (ending with tain, tein, tyn, dain, dein, ten, taine, etc.)
                    text = re.sub(r'\b[Mm][a-z0-9]{1,7}b[a-z]{0,3}[td][aie]{1,2}n?e?\b', 'مَرْحَبَتيْن', text, flags=re.IGNORECASE)
                    # 2. Marhaba variants (ending with ban, ban., ba, a, an)
                    text = re.sub(r'\b[Mm][a-z0-9]{1,6}b[a-z]{0,3}n?\b', 'مَرْحَبًا', text, flags=re.IGNORECASE)
                    # 3. Wa 3alaykom assalaam variants (including Hua halei como Salam, Wale comus Salam, while I come was Salam, etc.)
                    text = re.sub(r'\b(?:hua\s+)?(?:[a-z]{2,7}\s+){1,3}(?:was\s+)?(?:sala+m|musselam|muselam)\b|\bwhile\s+i\s+come\s+(?:was\s+)?sala+m\b|\bwaleco\b|\bmusselam\b', 'وَعَلَيْكُمُ السَّلَام', text, flags=re.IGNORECASE)
                    # 4. Assalamu alaykum variants
                    text = re.sub(r'\bas?sala?amu?\s*3?ala?yk?um?\b', 'السَّلَامُ عَلَيْكُم', text, flags=re.IGNORECASE)
                    # 5. Ya3teek il 3afyeh variants (including Yahtzee Kalafia, Yahtzee, Kalafia)
                    text = re.sub(r'\byahtzee\s*k?a?la?fi?a?\b|\bya?3?t[eeika]{1,3}k[ai]?\s*(?:il|el|al)?\s*3?a?fi?y?e?a?h?\b|\byatika?\s*l?a?fi?a?\b', 'يَعْطِيكَ الْعَافِيَة', text, flags=re.IGNORECASE)
                    # 6. Allah y3afeek variants (including Allah Yafiki, Allah yafeeki, Allah yafik)
                    text = re.sub(r'\ballah\s*(?:y3?a?a?fee?k[ai]?|ya?fi?e?e?k[ai]?|yfi?k[ai]?)\b', 'الله يَعَافِيك', text, flags=re.IGNORECASE)

                    # Dynamic dictionary fallback for Days 2-6
                    for arabic_target, mistakes in GLOBAL_MAPPINGS:
                        for mistake in mistakes:
                            pattern = r'\b' + re.escape(mistake) + r'(?=[.,?!]|\b)'
                            text = re.sub(pattern, arabic_target, text, flags=re.IGNORECASE)

                    # Smart Context-Aware Arabic Target Insertion:
                    # Maps English lesson context phrases directly to the exact target Arabic word if Azure STT dropped it or output standalone 'Salam.'
                    context_map = [
                        (r'sympathetic\s+greeting\s+(?:to\s+a\s+)?male|greeting\s+to\s+a\s+male', 'يَعْطِيكَ الْعَافِيَة'),
                        (r'sympathetic\s+greeting\s+(?:to\s+a\s+)?female|greeting\s+to\s+a\s+female', 'يَعْطِيكِ الْعَافِيَة'),
                        (r'response\s+to\s+a\s+male', 'الله يَعَافِيك'),
                        (r'response\s+to\s+a\s+female', 'الله يَعَافِيكِ'),
                        (r'formal\s+response', 'وَعَلَيْكُمُ السَّلَام'),
                        (r'formal\s+greeting', 'السَّلَامُ عَلَيْكُم'),
                        (r'casual\s+response|double\s+hello', 'مَرْحَبَتيْن'),
                        (r'casual\s+greeting', 'مَرْحَبًا')
                    ]

                    for pattern, ar_word in context_map:
                        if re.search(pattern, text, flags=re.IGNORECASE):
                            if re.search(r'\bsalam[.]?$', text, flags=re.IGNORECASE):
                                text = re.sub(r'\bsalam[.]?$', ar_word + '.', text, flags=re.IGNORECASE)
                            elif not re.search(r'[\u0600-\u06FF]', text):
                                text = text.rstrip('.!? ') + ' ' + ar_word + '.'
                            break

                    return text

                def ai_recognizing_cb(evt):
                    if not evt.result.text: return
                    text = post_process_transcript(evt.result.text)
                    msg = {"type": "transcript_partial", "text": text, "id": ai_bubble_id, "role": "ai"}
                    asyncio.run_coroutine_threadsafe(websocket.send_json(msg), loop)
                    safe_print(f"[Live] AI partial transcript: {text}")
                    
                def ai_recognized_cb(evt):
                    nonlocal ai_bubble_id
                    if not evt.result.text: return
                    text = post_process_transcript(evt.result.text)
                    msg = {"type": "transcript", "text": text, "id": ai_bubble_id, "role": "ai"}
                    asyncio.run_coroutine_threadsafe(websocket.send_json(msg), loop)
                    safe_print(f"[Live] AI final transcript: {text}")
                    ai_bubble_id = str(uuid.uuid4())

                    # Check if the AI completed the final message (saying goodbye / lesson complete / congratulations)
                    if re.search(r'lesson\s+is\s+now\s+complete|congratulat|lesson\s+complete|goodbye', text, flags=re.IGNORECASE):
                        safe_print("[Live] Lesson completed — sending session_ended to browser")
                        asyncio.run_coroutine_threadsafe(websocket.send_json({"type": "session_ended"}), loop)
                    
                ai_recognizer.recognizing.connect(ai_recognizing_cb)
                ai_recognizer.recognized.connect(ai_recognized_cb)
                ai_recognizer.start_continuous_recognition_async()
                
                user_stream_format = speechsdk.audio.AudioStreamFormat(samples_per_second=16000, bits_per_sample=16, channels=1)
                user_push_stream = speechsdk.audio.PushAudioInputStream(stream_format=user_stream_format)
                user_audio_config = speechsdk.audio.AudioConfig(stream=user_push_stream)
                user_speech_config = speechsdk.SpeechConfig(subscription=azure_key, region=azure_region)
                user_speech_config.speech_recognition_language = "ar-JO"
                user_recognizer = speechsdk.SpeechRecognizer(speech_config=user_speech_config, audio_config=user_audio_config)
                
                def user_recognizing_cb(evt):
                    if not evt.result.text: return
                    text = post_process_transcript(evt.result.text)
                    msg = {"type": "transcript_partial", "text": text, "id": user_bubble_id, "role": "user"}
                    asyncio.run_coroutine_threadsafe(websocket.send_json(msg), loop)
                    safe_print(f"[Live] User partial transcript: {text}")
                    
                def user_recognized_cb(evt):
                    nonlocal user_bubble_id
                    if not evt.result.text: return
                    text = post_process_transcript(evt.result.text)
                    msg = {"type": "transcript", "text": text, "id": user_bubble_id, "role": "user"}
                    asyncio.run_coroutine_threadsafe(websocket.send_json(msg), loop)
                    safe_print(f"[Live] User final transcript: {text}")
                    user_bubble_id = str(uuid.uuid4())
                    
                    # User turn complete
                    safe_print(f"[Live] End of user audio turn for: {text}")
                    
                user_recognizer.recognizing.connect(user_recognizing_cb)
                user_recognizer.recognized.connect(user_recognized_cb)
                
                # Biasing Azure STT to the specific Arabic target words
                ai_phrase_list = speechsdk.PhraseListGrammar.from_recognizer(ai_recognizer)
                user_phrase_list = speechsdk.PhraseListGrammar.from_recognizer(user_recognizer)

                # Add core dialect phrases for STT recognizer phrase biasing
                common_phrases = [
                    # Day 3 Pronouns
                    "أنا", "انت", "انتي", "هو", "هوه", "هي", "هيه", "احنا", "انتو", "هم", "همه", "هما", 
                    "إِنْتَ", "إِنْتِ", "أَنَا", "هُوَّه", "هِيَّه", "إِحْنَا", "إِنْتُو", "هُمَّه",
                    # Day 1 Greetings & Responses (from PDF)
                    "مرحبا", "مرحبتين", "مَرْحَبًا", "مَرْحَبَتيْن",
                    "السلام عليكم", "السَّلَامُ عَلَيْكُم",
                    "وعليكم السلام", "وَعَلَيْكُمُ السَّلَام",
                    "يعطيك العافية", "يَعْطِيكَ الْعَافِيَة", "يَعْطِيكِ الْعَافِيَة",
                    "الله يعافيك", "الله يَعَافِيك", "الله يَعَافِيكِ"
                ]
                for phrase in common_phrases:
                    user_phrase_list.addPhrase(phrase)

                for vocab in vocab_list:
                    arabic_word = vocab.get("target_arabic", "").strip()
                    if arabic_word:
                        # Strip harakat to match Azure STT base output
                        clean_word = re.sub(r'[\u064B-\u065F\u0670]', '', arabic_word)
                        ai_phrase_list.addPhrase(clean_word)
                        user_phrase_list.addPhrase(clean_word)
                        # Optional: also add the alif normalized version
                        normalized_word = re.sub(r'[أإآ]', 'ا', clean_word)
                        if normalized_word != clean_word:
                            ai_phrase_list.addPhrase(normalized_word)
                            user_phrase_list.addPhrase(normalized_word)
                
                user_recognizer.start_continuous_recognition_async()

            async def forward_mic_to_gemini():
                """Forward browser binary PCM chunks to Gemini Live in real-time.
                Chunks are dropped server-side when the frontend signals mic_muted."""
                nonlocal mic_muted
                nonlocal user_bubble_id
                try:
                    while True:
                        message = await websocket.receive()
                        if message.get("type") == "websocket.disconnect":
                            break
                        if "bytes" in message and message["bytes"]:
                            if not mic_muted:
                                if azure_key:
                                    user_push_stream.write(message["bytes"])
                                await session.send_realtime_input(
                                    audio=types.Blob(
                                        data=message["bytes"],
                                        mime_type="audio/pcm;rate=16000"
                                    )
                                )
                        elif "text" in message:
                            try:
                                data = json.loads(message["text"])
                                if data.get("type") == "mic_muted":
                                    mic_muted = True
                                    if azure_key:
                                        # Inject 1 second of silence to segment the utterance
                                        user_push_stream.write(b'\x00' * (16000 * 2))
                                elif data.get("type") == "mic_unmuted":
                                    mic_muted = False
                            except Exception:
                                pass
                except WebSocketDisconnect:
                    safe_print("[Live] forward_mic: WebSocketDisconnect")
                except Exception as e:
                    safe_print(f"[Live] forward_mic error: {e}")
                finally:
                    safe_print("[Live] forward_gemini exiting")
                    if ai_recognizer:
                        ai_recognizer.stop_continuous_recognition_async()
                    if user_recognizer:
                        user_recognizer.stop_continuous_recognition_async()

            current_ai_text = ""

            async def forward_gemini_to_browser():
                """Forward Gemini Live audio/text responses to the browser."""
                nonlocal ai_bubble_id, current_ai_text
                try:
                    while True:
                        async for response in session.receive():
                            # Audio chunk (raw PCM bytes, 24kHz) → tell browser to mute mic
                            if response.data:
                                if azure_key and ai_push_stream:
                                    ai_push_stream.write(response.data)
                                b64 = base64.b64encode(response.data).decode("utf-8")
                                await websocket.send_json({
                                    "type": "audio_chunk",
                                    "data": b64
                                })

                            # Direct Gemini Native Text Stream (Live Chat Bubbles)
                            if response.server_content and response.server_content.model_turn:
                                for part in response.server_content.model_turn.parts:
                                    text_chunk = ""
                                    if hasattr(part, "text") and part.text:
                                        text_chunk = part.text
                                    elif isinstance(part, dict) and part.get("text"):
                                        text_chunk = part.get("text")

                                    if text_chunk:
                                        current_ai_text += text_chunk
                                        processed = post_process_transcript(current_ai_text)
                                        await websocket.send_json({
                                            "type": "transcript_partial",
                                            "text": processed,
                                            "id": ai_bubble_id,
                                            "role": "ai"
                                        })

                            # Turn complete — Gemini finished speaking; unmute mic
                            if response.server_content and response.server_content.turn_complete:
                                safe_print("[Live] Gemini turn complete — unmuting mic")
                                if current_ai_text:
                                    final_processed = post_process_transcript(current_ai_text)
                                    await websocket.send_json({
                                        "type": "transcript",
                                        "text": final_processed,
                                        "id": ai_bubble_id,
                                        "role": "ai"
                                    })
                                    current_ai_text = ""
                                    ai_bubble_id = str(uuid.uuid4())

                                await websocket.send_json({"type": "turn_complete"})
                                if azure_key and ai_push_stream:
                                    # Inject 1 second of silence to segment the utterance
                                    ai_push_stream.write(b'\x00' * (24000 * 2))

                except WebSocketDisconnect:
                    safe_print("[Live] forward_gemini: WebSocketDisconnect")
                except Exception as e:
                    safe_print(f"[Live] forward_gemini error: {e}")
                finally:
                    safe_print("[Live] forward_gemini_to_browser exiting")

            mic_task = asyncio.create_task(forward_mic_to_gemini(), name="mic_task")
            gemini_task = asyncio.create_task(forward_gemini_to_browser(), name="gemini_task")

            done, pending = await asyncio.wait(
                [mic_task, gemini_task],
                return_when=asyncio.ALL_COMPLETED
            )
            
            for task in done:
                safe_print(f"[Live] Task finished: {task.get_name()}")
                if task.exception():
                    safe_print(f"[Live] Task exception: {task.exception()}")

            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    except WebSocketDisconnect:
        safe_print("[Live] Browser disconnected cleanly.")
    except Exception as e:
        safe_print(f"[Live] Fatal session error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
