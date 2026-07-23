import asyncio
import sys
import uuid
import sqlite3

# Hack to allow importing from backend directory
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv()

from extraction.pipeline import process_entry
from database import get_db

async def test_decision_extraction():
    content = "I have been evaluating graph databases and relational databases for my side project Apollo. I chose to use PostgreSQL because it has excellent JSON support and is easier to host. It will supersede Neo4j."
    entry_id = str(uuid.uuid4())
    
    # 1. Insert fake entry
    db = sqlite3.connect('data/raphael.db')
    db.execute("INSERT INTO entries (id, content) VALUES (?, ?)", (entry_id, content))
    db.commit()
    db.close()
    
    # 2. Process
    print("Processing entry...")
    await process_entry(entry_id, content)
    
    # 3. Check db for decision
    db = sqlite3.connect('data/raphael.db')
    cursor = db.cursor()
    cursor.execute("SELECT * FROM decisions WHERE source_entry_id = ?", (entry_id,))
    row = cursor.fetchone()
    
    if row:
        print("\nSUCCESS! Decision extracted:")
        print(f"Title: {row[1]}")
        print(f"Supersedes: {row[3]}")
        print(f"Reason: {row[4]}")
        print(f"Evidence: {row[5]}")
        print(f"Project ID: {row[6]}")
    else:
        print("\nFAILURE! No decision extracted.")
        
    db.close()

if __name__ == "__main__":
    asyncio.run(test_decision_extraction())
