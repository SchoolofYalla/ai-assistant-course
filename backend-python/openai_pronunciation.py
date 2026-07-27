import os
import json
import tempfile
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def evaluate_pronunciation_openai(audio_buffer: bytes, target_arabic: str) -> dict:
    """
    Two-pass Arabic pronunciation evaluator using OpenAI:
      Pass 1 — Whisper STT: Transcribe the audio exactly.
      Pass 2 — GPT-4o Evaluation: Grade the user's pronunciation.
    """
    if not client.api_key:
        return {"passed": False, "accuracy": 0.0, "feedback": "OpenAI API Key is missing. Please add it to your .env file.", "recognized_text": ""}

    # Save buffer to a temporary WAV file
    temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    temp_wav.write(audio_buffer)
    temp_wav.close()

    try:
        # Pass 1: Whisper Transcription
        print(f"[OpenAI Pass 1] Whisper STT for target: {target_arabic}...")
        with open(temp_wav.name, "rb") as audio_file:
            transcript_response = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file,
                language="ar"
            )
        
        recognized_text = transcript_response.text.strip()
        print(f"[OpenAI Pass 1] Recognized text: '{recognized_text}' | Target: '{target_arabic}'")
        
        if not recognized_text:
            return {
                "passed": False,
                "accuracy": 0.0,
                "feedback": "I didn't hear anything clearly. Speak louder and try again!",
                "recognized_text": ""
            }

        # Pass 2: GPT-4o Evaluation
        print(f"[OpenAI Pass 2] GPT-4o Evaluation...")
        system_prompt = """You are an expert, friendly Arabic vocal coach for an app called School of Yalla.
Your task is to evaluate if a student correctly pronounced an Arabic target word.
You need to be very strict about male vs female forms (e.g., إِنْتَ "Inta" vs إِنْتِ "Inti").
You will be given the Target Word and the Student's Speech (transcribed text).
Return your evaluation strictly as a JSON object with the following keys:
- "passed" (boolean): True if they said the correct word/form, False otherwise.
- "accuracy" (integer): A score from 0 to 100 representing how close they were.
- "feedback" (string): A short, friendly, and encouraging piece of feedback (max 2 sentences). If they used the wrong gender form, point it out gently.
"""
        
        user_prompt = f"Target Word: {target_arabic}\nStudent's Speech: {recognized_text}"
        
        evaluation_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        result_json = evaluation_response.choices[0].message.content
        print(f"[OpenAI Pass 2] Evaluation Result: {result_json}")
        
        evaluation = json.loads(result_json)
        
        return {
            "passed": evaluation.get("passed", False),
            "accuracy": float(evaluation.get("accuracy", 0.0)),
            "feedback": evaluation.get("feedback", "No feedback provided."),
            "recognized_text": recognized_text
        }

    except Exception as e:
        print(f"[OpenAI Exception] {e}")
        return {"passed": False, "accuracy": 0.0, "feedback": "Server error during OpenAI evaluation.", "recognized_text": ""}

    finally:
        if os.path.exists(temp_wav.name):
            try:
                os.remove(temp_wav.name)
            except Exception as e:
                print(f"[Warning] Could not delete temp file: {e}")
