import sys
import asyncio
from fastapi.testclient import TestClient
from main import app
import traceback
import time
import httpx

async def test_concurrent():
    print("Testing concurrency with HTTPX ASyncClient against ASGI...")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Trigger multiple requests simultaneously
        reqs = [
            client.get("/api/tasks"),
            client.get("/api/ideas"),
            client.get("/api/calendar/events"),
            client.post("/api/tasks/sync")
        ]
        results = await asyncio.gather(*reqs, return_exceptions=True)
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                print(f"Request {i} Exception:", res)
            else:
                print(f"Request {i} Status:", res.status_code)

try:
    asyncio.run(test_concurrent())
except Exception as e:
    traceback.print_exc()
    sys.exit(1)
