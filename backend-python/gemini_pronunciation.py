import os
import json
import tempfile
import wave
import io
import struct
import re
from openai import OpenAI, AsyncOpenAI
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

def safe_print(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"))

import math

def is_audio_silent(wav_bytes: bytes, threshold: int = 10) -> bool:
    try:
        with wave.open(io.BytesIO(wav_bytes), 'rb') as w:
            frames = w.readframes(w.getnframes())
            if w.getsampwidth() == 2: # 16-bit
                samples = struct.unpack(f"<{len(frames)//2}h", frames)
                if not samples:
                    return True
                sum_sq = sum(float(s) * float(s) for s in samples)
                rms = math.sqrt(sum_sq / len(samples))
                safe_print(f"[Audio Check] RMS amplitude: {rms:.2f}")
                return rms < threshold
    except Exception as e:
        safe_print(f"[Warning] Silence check failed: {e}")
    return False

def evaluate_pronunciation_gemini(audio_buffer: bytes, target_arabic: str, dialect_rules: str = "") -> dict:

    if not os.getenv("GEMINI_API_KEY") or "PASTE_YOUR" in os.getenv("GEMINI_API_KEY"):
        return {"passed": False, "accuracy": 0.0, "feedback": "Gemini API Key is missing. Please add it to your .env file.", "recognized_text": ""}

    if is_audio_silent(audio_buffer):
        return {"passed": False, "accuracy": 0.0, "feedback": "I didn't hear anything clearly. Please try speaking a bit louder.", "recognized_text": ""}

    # 1. Fast STT with OpenAI Whisper
    openai_key = os.getenv("OPENAI_API_KEY")
    stt_text = ""
    if openai_key:
        try:
            openai_client = OpenAI(api_key=openai_key)
            audio_file = io.BytesIO(audio_buffer)
            audio_file.name = "audio.wav"
            safe_print("[STT] Transcribing audio with OpenAI Whisper...")
            transcription = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ar"
            )
            stt_text = transcription.text.strip()
            safe_print(f"[STT] Result: {stt_text}")
            
            # Fast-Match Bypass
            clean_target = re.sub(r'[\u064B-\u065F\u0670]', '', target_arabic).strip()
            clean_stt = re.sub(r'[\u064B-\u065F\u0670]', '', stt_text).strip()
            
            # OpenAI sometimes adds punctuation
            clean_stt = re.sub(r'[^\w\s]', '', clean_stt)
            clean_target = re.sub(r'[^\w\s]', '', clean_target)
            
            if clean_stt and clean_target and (clean_stt == clean_target or clean_stt in clean_target or clean_target in clean_stt):
                safe_print("[Fast-Match] Perfect match detected via STT! Bypassing Gemini.")
                return {
                    "passed": True,
                    "accuracy": 100.0,
                    "feedback": "Perfect! You said the word correctly.",
                    "recognized_text": stt_text
                }
                
        except Exception as e:
            safe_print(f"[STT Error] Whisper failed: {e}")
            stt_text = ""

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    try:
        if not stt_text:
            safe_print(f"[Gemini] Evaluating audio inline with Gemini Flash Latest...")
            content_part = types.Part.from_bytes(data=audio_buffer, mime_type="audio/wav")
        else:
            safe_print(f"[Gemini] Fast Text Evaluation with Gemini Flash Latest...")
            content_part = f"The user's speech was automatically transcribed as: '{stt_text}'. Note: STT often strips diacritics."

        prompt = f"""You are a VERY STRICT, expert Arabic vocal coach for an app called School of Yalla.
Your task is to evaluate if a student correctly pronounced the Arabic target word: "{target_arabic}".

{"The speech-to-text engine stripped the vowel marks (Tashkeel). You must determine if they passed based solely on the base letters they said." if stt_text else "You must listen to the audio carefully."}

CRITICAL RULES FOR EVALUATION:
1. NO BENEFIT OF THE DOUBT: If the audio is gibberish, unclear, or a completely different Arabic word, you MUST fail them.
2. EXACT MATCH ONLY: If they say "Marhaba" but the target is "Ana", they fail. If they say a different sentence, they fail.
3. GENDER STRICTNESS: Be strict about male vs female forms if you can detect them.

JORDANIAN DIALECT RULES:
The target word is in colloquial Jordanian Arabic. You MUST grade them based on Jordanian pronunciation, not formal MSA (Fusha).
- 'Qaf' (ق) is usually pronounced as a glottal stop / Hamza (ء), or sometimes a hard 'G'.
- Word endings are generally softer.
- 'Jim' (ج) is pronounced normally as 'J' (not the Egyptian 'G').
{f"SPECIFIC DIALECT RULE FOR THIS WORD: {dialect_rules}" if dialect_rules else ""}

Return your evaluation strictly as a raw text string on a single line in the following exact format:
PASS|recognized_arabic_text|Your feedback here
or
FAIL|recognized_arabic_text|Your feedback here

Rules for the output format:
- The first word MUST be exactly "PASS" or "FAIL".
- The second part MUST be what you heard them say, written in Arabic script.
- The third part is a short, encouraging piece of feedback (max 2 sentences). 
- CRITICAL LANGUAGE RULE: The feedback sentences MUST BE 100% IN ENGLISH! Do NOT write the feedback in Arabic.
- CRITICAL PRONUNCIATION RULE: However, whenever you quote the Arabic target word or the word the user said INSIDE the English feedback, you MUST write those specific words in actual Arabic script WITH FULL TASHKEEL (e.g. إِنْتَ). The TTS engine is multilingual and needs the Arabic script to pronounce it in a native Jordanian accent! Do NOT use English transliterations for Arabic words.
"""
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=[content_part, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="text/plain",
                temperature=0.0,
            )
        )
        
        result_text = response.text.strip()
        safe_print(f"[Gemini] Evaluation Result: {result_text}")
        
        parts = result_text.split("|", 2)
        passed = parts[0].strip() == "PASS"
        recognized = parts[1].strip() if len(parts) > 1 else ""
        feedback = parts[2].strip() if len(parts) > 2 else "No feedback."
        
        return {
            "passed": passed,
            "accuracy": 100.0 if passed else 0.0,
            "feedback": feedback,
            "recognized_text": recognized
        }

    except Exception as e:
        safe_print(f"[Gemini Exception] {e}")
        error_msg = f"Server error during Gemini evaluation: {str(e)}"
        
        if "API key not valid" in str(e) or "API_KEY_INVALID" in str(e):
            error_msg = "Your Gemini API Key is invalid. Please check your .env file."
        elif "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            error_msg = "We're testing too fast! Google's Free Tier needs a moment to catch up. Wait a few seconds and try again."
            
        return {"passed": False, "accuracy": 0.0, "feedback": error_msg, "recognized_text": ""}


async def evaluate_pronunciation_openai_stream(audio_buffer: bytes, target_arabic: str, dialect_rules: str = ""):
    """
    Two-step evaluation:
    1. Whisper STT -> exact fast-match (instant PASS, no LLM cost)
    2. Whisper text -> GPT-4o-mini streaming evaluation with strong diacritic-awareness prompt
    """
    if is_audio_silent(audio_buffer):
        yield {"type": "metadata", "passed": False, "accuracy": 0.0, "recognized_text": ""}
        yield {"type": "feedback_chunk", "text": "I didn't hear anything clearly. Please try speaking a bit louder."}
        return

    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        yield {"type": "metadata", "passed": False, "accuracy": 0.0, "recognized_text": ""}
        yield {"type": "feedback_chunk", "text": "OpenAI API Key is missing."}
        return

    import asyncio

    # ── Step 1: Whisper STT ─────────────────────────────────────────────────
    stt_text = ""
    try:
        sync_client = OpenAI(api_key=openai_key)
        audio_file = io.BytesIO(audio_buffer)
        audio_file.name = "audio.wav"
        safe_print("[STT] Transcribing with Whisper...")

        def run_whisper():
            return sync_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ar",
                prompt="\u0627\u0644\u0643\u0644\u0627\u0645 \u0628\u0627\u0644\u0644\u0647\u062c\u0629 \u0627\u0644\u0623\u0631\u062f\u0646\u064a\u0629 \u0627\u0644\u0639\u0627\u0645\u064a\u0629"
            )

        result = await asyncio.to_thread(run_whisper)
        stt_text = result.text.strip()
        safe_print(f"[STT] Result: {stt_text}")

        # Fast-Match: exact match (retaining diacritics) -> instant PASS
        def normalize(s):
            s = re.sub(r'[^\w\s\u064B-\u065F\u0670]', '', s) # Strip punctuation but KEEP tashkeel
            s = re.sub(r'[\u0623\u0625\u0622]', '\u0627', s)  # normalize Alifs
            s = re.sub(r'\u0629', '\u0647', s)              # normalize Taa Marbuta
            return s.strip()

        if normalize(stt_text) == normalize(target_arabic):
            safe_print("[Fast-Match] Exact match! Bypassing LLM.")
            yield {"type": "metadata", "passed": True, "accuracy": 100.0, "recognized_text": stt_text, "fast_match": True}
            yield {"type": "feedback_chunk", "text": "\u0645\u0645\u062a\u0627\u0632! You said the word perfectly!"}
            return

    except Exception as e:
        safe_print(f"[STT Error] {e}")

    # ── Fast-Fail: Deterministic Catch for Gender Mismatches ────────────────
    try:
        target_stripped = re.sub(r'[\u064B-\u065F\u0670]', '', target_arabic).strip()
        stt_stripped = re.sub(r'[\u064B-\u065F\u0670]', '', stt_text).strip()
        
        t_base = re.sub(r'[\u0623\u0625\u0622]', '\u0627', target_stripped)
        s_base = re.sub(r'[\u0623\u0625\u0622]', '\u0627', stt_stripped)
        
        # If the base word matches exactly, or with an added Yaa (for female)
        if s_base == t_base or s_base == t_base + '\u064A' or s_base == t_base + '\u0649':
            target_ends_fatha = target_arabic.strip().endswith('\u064E')
            target_ends_kasra = target_arabic.strip().endswith('\u0650')
            
            stt_ends_yaa = stt_text.strip().endswith('\u064A') or stt_text.strip().endswith('\u0649')
            stt_ends_kasra = '\u0650' in stt_text[-2:]
            
            stt_is_female = stt_ends_yaa or stt_ends_kasra
            stt_is_male = not stt_is_female
            
            if target_ends_fatha and stt_is_female:
                safe_print("[Fast-Fail] Gender mismatch: Female STT for Male Target.")
                yield {"type": "metadata", "passed": False, "accuracy": 0.0, "recognized_text": stt_text, "fast_match": False}
                yield {"type": "feedback_chunk", "text": "Oops! You used the female form (Inti), but the target is male (Inta)."}
                return
                
            if target_ends_kasra and stt_is_male:
                safe_print("[Fast-Fail] Gender mismatch: Male STT for Female Target.")
                yield {"type": "metadata", "passed": False, "accuracy": 0.0, "recognized_text": stt_text, "fast_match": False}
                yield {"type": "feedback_chunk", "text": "Oops! You used the male form (Inta), but the target is female (Inti)."}
                return
    except Exception as e:
        safe_print(f"[Fast-Fail Error] {e}")


        # ── Fast-Fail: Deterministic Catch for Truncated/Incomplete Answers ────

        
    try:
        target_bare_check = re.sub(r'[\u064B-\u065F\u0670]', '', target_arabic).strip()
        stt_bare_check = re.sub(r'[\u064B-\u065F\u0670]', '', stt_text).strip()

        def bare_norm(s):
            s = re.sub(r'[\u0623\u0625\u0622]', '\u0627', s)
            s = re.sub(r'\s+', '', s)
            return s

        t_norm = bare_norm(target_bare_check)
        s_norm = bare_norm(stt_bare_check)

        if s_norm and t_norm and s_norm != t_norm:
            if t_norm.startswith(s_norm) and len(t_norm) - len(s_norm) >= 1:
                safe_print("[Fast-Fail] Truncated/incomplete answer detected.")
                yield {"type": "metadata", "passed": False, "accuracy": 0.0, "recognized_text": stt_text, "fast_match": False}
                yield {"type": "feedback_chunk", "text": "Close, but you missed part of it — make sure to say the whole phrase, all the way to the end."}
                return
    except Exception as e:
        safe_print(f"[Fast-Fail Truncation Error] {e}")

    # ── Step 2: Gemini Flash text evaluation ─────────────────────────────────
    try:
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            yield {"type": "metadata", "passed": False, "accuracy": 0.0, "recognized_text": ""}
            yield {"type": "feedback_chunk", "text": "Gemini API Key is missing."}
            return
            
        aclient = genai.Client(api_key=gemini_key).aio
        safe_print("[Eval] Sending to Gemini Flash Latest...")

        target_bare = re.sub(r'[\u064B-\u065F\u0670]', '', target_arabic).strip()

        prompt = f"""You are a strict Arabic pronunciation coach evaluating a student.

Target word (with diacritics): {target_arabic}
Target word (bare consonants):  {target_bare}
Whisper transcription of what the student said: '{stt_text}'

IMPORTANT - HOW WHISPER WORKS:
Whisper cannot write short vowels (harakat / tashkeel). It replaces them with full letters:
- A Kasra at the end of a word becomes Yaa: so "intI" becomes "inti" written as "انتي"
- A Fatha is often silent/dropped: so "inta" stays "انت"
- A Damma can become Waw
You MUST mentally re-add the diacritics before judging.

EVALUATION RULES:
1. Compare the PHONEMES the student said (reconstructed from Whisper text) against the target with diacritics.
2. GENDER is critical: male Fatha-ending != female Kasra-ending. 
   - If target is FEMALE (ends in Kasra ِ  or ي), STT "انتي" or "أنتِ" = PASS. STT "انت" or "أنتَ" = FAIL.
   - If target is MALE (ends in Fatha َ ), STT "انت" or "أنتَ" = PASS. STT "انتي" or "أنتِ" = FAIL.
3. Complete gibberish from Whisper (e.g. a completely unrelated sentence) = FAIL.
4. Empty or very short stt_text = FAIL.
5. COMPLETENESS IS MANDATORY: The student must say the ENTIRE phrase, including every word and suffix. If they drop a word, a suffix (like ـكم), or stop early, that is a FAIL — regardless of how correct the part they did say sounds. Do not give credit for a partial or "close enough" phrase.
{f"DIALECT NOTE: {dialect_rules}" if dialect_rules else ""}

RESPOND on a single line in exactly this format:
PASS|arabic_of_what_you_heard_with_tashkeel|English feedback (max 2 sentences, Arabic words quoted inside must have tashkeel)
or
FAIL|arabic_of_what_you_heard_with_tashkeel|English feedback (max 2 sentences, Arabic words quoted inside must have tashkeel)
"""

        # Collect full response (avoids mid-stream truncation of Arabic tashkeel).
        # Then fake-stream feedback word-by-word so ElevenLabs TTS still starts quickly.
        response = await aclient.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=600,
            )
        )

        raw = (response.text or "").strip()
        safe_print(f"[Eval] Gemini raw: {raw!r}")

        # Strip markdown fences/quotes Gemini sometimes wraps around the answer
        clean = re.sub(r'```[^\n]*\n?', '', raw).strip('`"\' \n')

        # Robust parse: find first PASS/FAIL|...|... line anywhere in the output
        match = re.search(r'\b(PASS|FAIL)\s*\|([^|\n]*)\|(.+)', clean, re.IGNORECASE | re.DOTALL)

        if match:
            passed = match.group(1).strip().upper() == "PASS"
            recognized = match.group(2).strip()
            feedback = match.group(3).strip()
            yield {"type": "metadata", "passed": passed, "accuracy": 100.0 if passed else 0.0,
                   "recognized_text": recognized, "fast_match": False}
            # Fake-stream feedback word-by-word so ElevenLabs TTS starts fast
            words = feedback.split(" ")
            for i, word in enumerate(words):
                chunk_text = word if i == 0 else " " + word
                yield {"type": "feedback_chunk", "text": chunk_text}
                await asyncio.sleep(0)  # yield control so chunks flow through
        else:
            safe_print(f"[Eval] Could not parse Gemini response. Raw: {raw!r}")
            yield {"type": "metadata", "passed": False, "accuracy": 0.0, "recognized_text": stt_text}
            yield {"type": "feedback_chunk", "text": "Could not evaluate clearly. Please try again."}

    except Exception as e:
        safe_print(f"[Eval Error] {e}")
        yield {"type": "metadata", "passed": False, "accuracy": 0.0, "recognized_text": ""}
        yield {"type": "feedback_chunk", "text": "Evaluation error. Please try again."}
