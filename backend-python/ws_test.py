import asyncio
import websockets
import json

async def test_ws():
    uri = "ws://localhost:8000/ws/practice/day_1_greetings"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")
            while True:
                message = await websocket.recv()
                print(f"Received: {message[:100]}...") # print first 100 chars
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_ws())
