import os
import asyncio
import json
import base64
import requests
import functools
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv

# Azure Speech SDK
import azure.cognitiveservices.speech as speechsdk

# OpenAI
from openai import OpenAI

# Local modules
from vocabulary import get_vocabulary_for_day
from gemini_pronunciation import evaluate_pronunciation_gemini
from gemini_live import run_live_session

load_dotenv()

app = FastAPI(title="Jordanian Arabic Vocal Coach API")

# Toggle this to True to force OpenAI (ChatGPT) voices for EVERYTHING
USE_OPENAI_TTS = True

def safe_print(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"))

# --- Azure TTS Helper ---
def synthesize_azure_tts(text: str, is_arabic: bool = False) -> bytes:
    """
    Synthesizes speech using Azure Neural TTS with alternative expressive voices.
    Returns MP3 audio buffer bytes.
    """
    speech_key = os.getenv("AZURE_SPEECH_KEY")
    speech_region = os.getenv("AZURE_SPEECH_REGION", "eastus")
    
    if not speech_key:
        print("[Warning] Azure Speech Key not found. Returning empty audio bytes.")
        return b""

    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
    speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3)
    
    pull_stream = speechsdk.audio.PullAudioOutputStream()
    audio_config = speechsdk.audio.AudioOutputConfig(stream=pull_stream)
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    if is_arabic:
        # We use Syrian (Laith) because it is a Levantine dialect nearly identical to Jordanian,
        # but the AI model is trained on much more data so it sounds far more natural and less robotic than Taim.
        ssml = f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="ar-SY">
            <voice name="ar-SY-LaithNeural">
                <prosody rate="-10%" pitch="+5%">
                    {text}
                </prosody>
            </voice>
        </speak>"""
        result = synthesizer.speak_ssml_async(ssml).get()
    else:
        # Force Azure to use the "cheerful" emotion style which makes it sound much more human
        ssml = f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US">
            <voice name="en-US-GuyNeural">
                <mstts:express-as style="cheerful" styledegree="1.5">
                    <prosody rate="+5%">
                        {text}
                    </prosody>
                </mstts:express-as>
            </voice>
        </speak>"""
        result = synthesizer.speak_ssml_async(ssml).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        return result.audio_data
    else:
        print(f"Speech synthesis canceled: {result.cancellation_details.reason}")
        return b""

# --- OpenAI TTS Helper ---
def synthesize_openai_tts(text: str, is_arabic: bool = False) -> bytes:
    """
    Synthesizes speech using OpenAI's TTS-1 model.
    Returns MP3 audio buffer bytes.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("[Warning] OpenAI API Key not found. Returning empty audio bytes.")
        return b""
        
    client = OpenAI(api_key=openai_key)
    
    # Use 'echo' for a friendly, expressive male voice to match the Jordanian male voice
    voice = "echo" 
    
    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text
        )
        return response.read()
    except Exception as e:
        print(f"OpenAI TTS Error: {e}")
        return b""

# --- ElevenLabs TTS Helper ---
def synthesize_elevenlabs_tts(text: str, is_arabic: bool = False) -> bytes:
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    if not elevenlabs_key:
        return b""
        
    # We pull the Voice ID from the .env file. If not set, it defaults to Adam (pNInz6obpgDQGcFmaJcg)
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJcg")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": elevenlabs_key
    }
    
    data = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.content
        else:
            print(f"ElevenLabs Error: {response.text}")
            return b""
    except Exception as e:
        print(f"ElevenLabs Request Exception: {e}")
        return b""

@functools.lru_cache(maxsize=128)
def synthesize_tts(text: str, is_arabic: bool = False) -> bytes:
    """Master TTS Wrapper: Prioritizes ElevenLabs if configured, else Hybrid."""
    
    if os.getenv("ELEVENLABS_API_KEY"):
        audio = synthesize_elevenlabs_tts(text, is_arabic)
        if audio:
            return audio
        print("[Fallback] ElevenLabs failed, using fallback TTS...")
        
    if USE_OPENAI_TTS:
        return synthesize_openai_tts(text, is_arabic)
    else:
        return synthesize_azure_tts(text, is_arabic)

# --- Gemini Live WebSocket Endpoint (low-latency, real-time audio) ---
@app.websocket("/ws/live/{day_id}")
async def live_session(websocket: WebSocket, day_id: str):
    await websocket.accept()
    vocab_list = get_vocabulary_for_day(day_id)
    if not vocab_list:
        await websocket.send_json({"type": "error", "message": f"No vocabulary found for day: {day_id}"})
        await websocket.close()
        return
    await run_live_session(websocket, vocab_list)


# --- Legacy WebSocket Endpoint (kept for compatibility) ---
@app.websocket("/ws/practice/{day_id}")
async def practice_session(websocket: WebSocket, day_id: str):
    await websocket.accept()
    
    # Load vocabulary for the specific day
    vocab_list = get_vocabulary_for_day(day_id)
    if not vocab_list:
        await websocket.send_json({"type": "error", "message": f"No vocabulary found for day: {day_id}"})
        await websocket.close()
        return

    current_index = 0
    audio_buffer = bytearray()

    # --- Keepalive Helpers ---
    # These run a blocking Azure call in a background thread while pinging the browser
    # every second to prevent the WebSocket from timing out during long API calls.

    async def tts_with_keepalive(text: str, is_arabic: bool, status_label: str) -> bytes:
        """Run TTS synthesis while sending keepalive pings so the WebSocket stays alive."""
        task = asyncio.create_task(asyncio.to_thread(synthesize_tts, text, is_arabic))
        while not task.done():
            try:
                await websocket.send_json({"type": "keepalive", "statusText": status_label})
            except Exception as e:
                import traceback
                print(f"[Keepalive] WebSocket closed during TTS. Exception type: {type(e).__name__}, error: {e}")
                traceback.print_exc()
                task.cancel()
                raise WebSocketDisconnect()
            await asyncio.sleep(1)
        return await task

    from gemini_pronunciation import evaluate_pronunciation_openai_stream
    import websockets

    async def handle_evaluation_stream(audio_bytes: bytes, target: str, dialect_rules: str = ""):
        elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJcg")
        
        gen = evaluate_pronunciation_openai_stream(audio_bytes, target, dialect_rules)
        
        metadata = None
        full_text = ""
        fallback_required = False
        eleven_ws = None
        forward_task = None
        
        # Pre-connect to ElevenLabs if key exists
        if elevenlabs_key:
            ws_url = f"wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input?model_id=eleven_turbo_v2_5&output_format=pcm_16000"
            try:
                # We use connect without context manager so we can close it later manually if needed
                eleven_ws = await websockets.connect(ws_url)
                await eleven_ws.send(json.dumps({
                    "text": " ",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                    "xi-api-key": elevenlabs_key
                }))
                
                async def forward_audio():
                    try:
                        async for message in eleven_ws:
                            res = json.loads(message)
                            if res.get("audio"):
                                await websocket.send_json({
                                    "type": "audio_stream_chunk",
                                    "audioBase64": res["audio"]
                                })
                            if res.get("isFinal"):
                                break
                    except Exception as e:
                        print(f"ElevenLabs WS read error: {e}")
                
                forward_task = asyncio.create_task(forward_audio())
            except Exception as e:
                print(f"[Streaming Error] {e}. Falling back to standard TTS.")
                fallback_required = True
                eleven_ws = None
        else:
            fallback_required = True

        async for chunk in gen:
            if chunk["type"] == "metadata":
                metadata = chunk
                await websocket.send_json({
                    "type": "feedback_stream_start",
                    "passed": metadata["passed"],
                    "studentTranscription": metadata["recognized_text"]
                })
                # If it's a fast-match, we don't want to use ElevenLabs stream because standard TTS is cached
                if metadata.get("fast_match"):
                    fallback_required = True
                    
            elif chunk["type"] == "feedback_chunk":
                full_text += chunk["text"]
                if eleven_ws and not fallback_required:
                    try:
                        await eleven_ws.send(json.dumps({"text": chunk["text"]}))
                    except Exception:
                        pass
                else:
                    await websocket.send_json({"type": "feedback_text_chunk", "text": chunk["text"]})
                    
        # Wrap up ElevenLabs connection
        if eleven_ws and not fallback_required:
            try:
                await eleven_ws.send(json.dumps({"text": ""}))
                if forward_task is not None:
                    try:
                        await asyncio.wait_for(forward_task, timeout=3.0)
                    except asyncio.TimeoutError:
                        print("ElevenLabs forward_task timeout")
                    except asyncio.CancelledError:
                        print("ElevenLabs forward_task cancelled")
                await eleven_ws.close()
            except Exception as e:
                print(f"Error closing ElevenLabs: {e}")
                fallback_required = True
            finally:
                if forward_task is not None and not forward_task.done():
                    forward_task.cancel()
        elif eleven_ws:
            # We opened it but ended up using fallback (e.g. fast-match)
            if forward_task is not None and not forward_task.done():
                forward_task.cancel()
            await eleven_ws.close()
            
        if fallback_required:
            # Fallback standard TTS
            feedback_audio = await asyncio.to_thread(synthesize_tts, full_text, False)
            await websocket.send_json({
                "type": "audio_stream_complete_b64",
                "audioBase64": base64.b64encode(feedback_audio).decode("utf-8") if feedback_audio else ""
            })
            
        return metadata

    async def play_current_step():
        nonlocal current_index
        try:
            if current_index >= len(vocab_list):
                congrats_text = "Congratulations, you finished the lesson!"
                congrats_audio = await asyncio.to_thread(synthesize_tts, congrats_text, False)
                await websocket.send_json({"type": "status", "statusText": "Lesson Complete!"})
                await websocket.send_json({
                    "type": "lesson_complete", 
                    "text": congrats_text,
                    "audioBase64": base64.b64encode(congrats_audio).decode("utf-8") if congrats_audio else ""
                })
                return

            current_word = vocab_list[current_index]
            safe_print(f"[Session] Word {current_index + 1}: {current_word['target_arabic']}")

            # 1 & 2. Synthesize & Send English Intro and Arabic Target in Parallel
            print(f"[Debug] Synthesizing intro & target for word {current_index + 1} in parallel...")
            intro_task = asyncio.create_task(asyncio.to_thread(synthesize_tts, current_word["english_intro"], False))
            target_task = asyncio.create_task(asyncio.to_thread(synthesize_tts, current_word["target_arabic"], True))
            
            intro_audio, target_audio = await asyncio.gather(intro_task, target_task)

            print(f"[Debug] Sending intro_audio and target_audio...")
            await websocket.send_json({
                "type": "instruction_audio",
                "text": current_word["english_intro"],
                "audioBase64": base64.b64encode(intro_audio).decode("utf-8") if intro_audio else ""
            })

            await websocket.send_json({
                "type": "target_audio",
                "text": current_word["target_arabic"],
                "transliteration": current_word["transliteration"],
                "audioBase64": base64.b64encode(target_audio).decode("utf-8") if target_audio else ""
            })

            # 3. Prompt User to Speak
            await websocket.send_json({
                "type": "prompt_user_speech",
                "message": "Microphone is open! Repeat the Arabic word now."
            })
        except WebSocketDisconnect:
            raise
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[play_current_step] Unexpected error: {e}")
            try:
                await websocket.send_json({"type": "error", "message": f"Internal server error: {e}"})
            except Exception:
                pass
            raise WebSocketDisconnect()

    try:
        # Start the first step
        print("[Debug] Sending session_started...")
        await websocket.send_json({"type": "session_started", "totalWords": len(vocab_list)})
        
        # Welcome Intro
        welcome_text = "Welcome to your vocal coach! Let's get started."
        welcome_audio = await asyncio.to_thread(synthesize_tts, welcome_text, False)
        await websocket.send_json({
            "type": "instruction_audio",
            "text": welcome_text,
            "audioBase64": base64.b64encode(welcome_audio).decode("utf-8") if welcome_audio else ""
        })
        
        print("[Debug] Calling play_current_step...")
        await play_current_step()
        print("[Debug] Started while loop...")

        while True:
            # Wait for incoming messages (binary audio chunks or JSON commands)
            message = await websocket.receive()
            
            if message.get("type") == "websocket.disconnect":
                print(f"[WebSocket] Client disconnected abruptly.")
                break
                
            
            if "bytes" in message:
                # Append binary audio chunks
                audio_buffer.extend(message["bytes"])
                
            elif "text" in message:
                data = json.loads(message["text"])
                
                if data.get("type") == "inactivity_timeout":
                    print("[Session] User inactive for 6 seconds. Pinging...")
                    timeout_msg = "Are you still there? Try saying the word!"
                    timeout_audio = await asyncio.to_thread(synthesize_tts, timeout_msg, False)
                    await websocket.send_json({
                        "type": "instruction_audio",
                        "text": timeout_msg,
                        "audioBase64": base64.b64encode(timeout_audio).decode("utf-8") if timeout_audio else ""
                    })
                    await websocket.send_json({
                        "type": "prompt_user_speech",
                        "message": "Microphone is open! Let's try again."
                    })
                    continue
                
                if data.get("type") == "speech_finished":
                    try:
                        if len(audio_buffer) == 0:
                            await websocket.send_json({
                                "type": "feedback_audio",
                                "passed": False,
                                "text": "I didn't hear anything. Let's move to the next word.",
                                "audioBase64": ""
                            })
                            current_index += 1
                            await play_current_step()
                            continue
                            
                        # Evaluate Pronunciation using Gemini
                        display_target = vocab_list[current_index]["target_arabic"]
                        eval_target = vocab_list[current_index].get("evaluation_target", display_target)
                        dialect_rules = vocab_list[current_index].get("dialect_rules", "")
                        safe_print(f"Streaming Evaluation for {len(audio_buffer)} bytes against target: {eval_target}")
                        
                        evaluation = await handle_evaluation_stream(bytes(audio_buffer), eval_target, dialect_rules)
                        
                        audio_buffer.clear() # Reset buffer for next word

                        # Signal frontend to advance
                        await websocket.send_json({"type": "evaluation_complete"})

                        current_index += 1
                        await play_current_step()
                        
                    except WebSocketDisconnect:
                        raise
                    except Exception as e:
                        print(f"[Error processing speech]: {e}")
                        try:
                            await websocket.send_json({"type": "status", "statusText": "Error during evaluation. Try again."})
                        except Exception:
                            pass

    except WebSocketDisconnect:
        print(f"[WebSocket] Client disconnected from session {day_id}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
