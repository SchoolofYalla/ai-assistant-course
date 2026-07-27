import os
import requests
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("SPEECHMATICS_API_KEY", "nunNXyRii1G4i2Ooq4UNnCVLWZKlH4mw")
url = 'https://asr.api.speechmatics.com/v2/jobs'
headers = {
    'Authorization': f'Bearer {key}'
}
data = {
    'config': '{"type": "transcription", "transcription_config": {"language": "ar", "operating_point": "enhanced"}}'
}
with open('debug_audio/last_recording.wav', 'rb') as f:
    files = {'data_file': f}
    response = requests.post(url, headers=headers, data=data, files=files)
    print(response.json())
