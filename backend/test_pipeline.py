import asyncio
import os
import uuid
import traceback
from extraction.pipeline import process_entry
from database import get_db

async def run():
    entry_id = str(uuid.uuid4())
    content = "I built a nice game in the coding language that my friend developed. He seems to be really happy about that. That project of mine is completed. I am not touching that language for a while now"
    
    # insert entry to db first
    async with get_db() as db:
        await db.execute(
            "INSERT INTO entries (id, content, source_type) VALUES (?, ?, ?)",
            (entry_id, content, "manual")
        )
        await db.commit()
    
    print("Running process_entry...")
    try:
        await process_entry(entry_id, content)
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())
