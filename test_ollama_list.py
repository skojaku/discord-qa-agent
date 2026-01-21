import asyncio
from ollama import AsyncClient
import json

async def test():
    r = await AsyncClient().list()
    print(f"Type: {type(r)}")
    print(f"Response: {r}")
    if hasattr(r, 'models'):
        print(f"\nModels: {r.models}")
        if r.models:
            print(f"\nFirst model: {r.models[0]}")
            print(f"First model type: {type(r.models[0])}")

asyncio.run(test())
