import os
from dotenv import load_dotenv
load_dotenv()
from google import genai
from google.genai import types

import tempfile
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

audio_buffer = create_dummy_wav()
temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
temp_wav.write(audio_buffer)
temp_wav.close()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
uploaded_file = client.files.upload(file=temp_wav.name, config={'mime_type': 'audio/wav'})

prompt = "Is this audio silence? Return {\"silence\": true} if it is."
response = client.models.generate_content(
    model='gemini-flash-latest',
    contents=[uploaded_file, prompt],
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
    )
)
print(response.text)
client.files.delete(name=uploaded_file.name)
