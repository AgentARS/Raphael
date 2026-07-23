import asyncio
import sys
from fastapi.testclient import TestClient
sys.path.append('.')
from main import app

client = TestClient(app)
response = client.post("/api/entries/b5de9b08-ca4d-44c7-a565-a63feee1db8c/reprocess")
print(response.status_code)
print(response.text)
