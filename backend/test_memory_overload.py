import asyncio
import psutil
from unittest.mock import patch
from llm_manager import generate_chat, SystemMemoryOverloadError
import os

async def main():
    print("Testing Memory Overload Protection...")
    
    class MockSwap:
        def __init__(self, used):
            self.used = used

    print("\n--- Test 1: Normal Memory (4GB swap used) ---")
    with patch('psutil.swap_memory', return_value=MockSwap(4 * 1024 * 1024 * 1024)):
        try:
            with patch('ollama.AsyncClient.chat', return_value={"message": {"content": "Success!"}}):
                response = await generate_chat("test-model", [{"role": "user", "content": "hi"}])
                print("Result:", response['message']['content'])
        except SystemMemoryOverloadError as e:
            print("FAILED: Raised overload error unexpectedly:", e)

    print("\n--- Test 2: Overloaded Memory (9GB swap used) ---")
    with patch('psutil.swap_memory', return_value=MockSwap(9 * 1024 * 1024 * 1024)):
        with patch('ollama.AsyncClient.generate') as mock_generate:
            # We also need to mock ollama.AsyncClient.ps() to return some models to unload
            with patch('ollama.AsyncClient.ps', return_value={"models": [{"name": "model1"}, {"name": "model2"}]}):
                try:
                    await generate_chat("test-model", [{"role": "user", "content": "hi"}])
                    print("FAILED: Did NOT raise overload error!")
                except SystemMemoryOverloadError as e:
                    print("SUCCESS: Raised overload error correctly:", e)
                    if mock_generate.call_count == 2:
                        print("SUCCESS: Model unload was triggered for both models.")
                    else:
                        print(f"FAILED: Model unload was NOT triggered correctly. Calls: {mock_generate.call_count}")

if __name__ == "__main__":
    asyncio.run(main())
