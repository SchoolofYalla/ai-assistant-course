import os
import asyncio
from google import genai
from google.genai import types

async def main():
    gemini_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=gemini_key)
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction="You must use your thought process ONLY to write exactly what you are saying out loud. Do not write any internal reasoning. Just write your spoken words.",
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
            )
        ),
    )
    async with client.aio.live.connect(model="gemini-2.5-flash-native-audio-latest", config=config) as session:
        await session.send_client_content(
            turns=types.Content(
                role="user",
                parts=[types.Part(text="Hello! Please reply with a very short greeting.")]
            ),
            turn_complete=True
        )
        async for response in session.receive():
            print("--- RESPONSE ---")
            if response.server_content and response.server_content.model_turn:
                for p in response.server_content.model_turn.parts:
                    print(f"Part text: {repr(p.text)}")
                    print(f"Part inline_data: {bool(p.inline_data)}")
                    print(f"Part thought: {repr(getattr(p, 'thought', None))}")
                    print(f"Part type: {type(p)}")
            else:
                print("No model turn")
            if response.server_content and response.server_content.turn_complete:
                break

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(main())
