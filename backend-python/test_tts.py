import asyncio
import traceback
from main import synthesize_azure_tts

async def test():
    try:
        print("Testing TTS...")
        result = await asyncio.to_thread(synthesize_azure_tts, 'hello', False)
        print("Length of result:", len(result))
    except Exception as e:
        print("Error!")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
