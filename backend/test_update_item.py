import sys
import json
import asyncio
import traceback
from datetime import datetime
from fastapi.testclient import TestClient
from main import app
from database import get_db

async def setup_db():
    today = datetime.now().strftime('%Y-%m-%d')
    async with get_db() as db:
        fake_briefing = {
            "suggested_plan": {
                "title": "Suggested Plan",
                "items": [
                    "This is a string item, not an object!"
                ]
            }
        }
        await db.execute("INSERT OR REPLACE INTO daily_briefings (date, content_json) VALUES (?, ?)", 
                         (today, json.dumps(fake_briefing)))
        await db.commit()

async def run_test():
    await setup_db()
    
    try:
        with TestClient(app) as client:
            payload = {
                "date": datetime.now().strftime('%Y-%m-%d'),
                "section_key": "suggested_plan",
                "item_index": 0,
                "action": "EDIT",
                "new_content": "This is new content."
            }
            response = client.post("/api/briefing/update_item", json=payload)
            print("Status:", response.status_code)
            print("Response:", response.text)
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_test())
