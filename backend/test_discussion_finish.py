import sys
from fastapi.testclient import TestClient
from main import app
import traceback
import json

try:
    with TestClient(app) as client:
        payload = {
            "context": {
                "object_type": "briefing_item",
                "section": "Suggested Plan",
                "content": "Work on the backend."
            },
            "messages": [
                {"role": "user", "content": "I don't want to work on the backend."}
            ]
        }
        response = client.post("/api/discussions/finish", json=payload)
        print("Status:", response.status_code)
        print("Response:", response.text)
except Exception as e:
    traceback.print_exc()
    sys.exit(1)
