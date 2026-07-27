import os
from gemini_pronunciation import evaluate_pronunciation_gemini

# Create a dummy valid wav buffer
import wave
import io

def create_dummy_wav() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(44100)
        wav_file.writeframes(b'\x00' * 44100 * 2) # 1 second of silence
    return buffer.getvalue()

wav_bytes = create_dummy_wav()
print("Testing Gemini...")
result = evaluate_pronunciation_gemini(wav_bytes, "أَنَا")
print("Result:", result)
