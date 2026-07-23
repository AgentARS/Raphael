import asyncio
import os
import sys

# Add backend directory to path so imports work
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from database import get_db
from scoring.engine import update_object_scores

async def migrate_all_scores():
    print("Migrating Knowledge Scores for all existing objects...")
    
    async with get_db() as db:
        # Get all entries
        cursor = await db.execute("SELECT id FROM entries")
        entries = await cursor.fetchall()
        print(f"Scoring {len(entries)} entries...")
        for row in entries:
            await update_object_scores(db, row['id'], "entries")
            
        # Get all entities
        cursor = await db.execute("SELECT id FROM entities")
        entities = await cursor.fetchall()
        print(f"Scoring {len(entities)} entities...")
        for row in entities:
            await update_object_scores(db, row['id'], "entities")
            
        # Get all tasks
        cursor = await db.execute("SELECT id FROM tasks")
        tasks = await cursor.fetchall()
        print(f"Scoring {len(tasks)} tasks...")
        for row in tasks:
            await update_object_scores(db, row['id'], "tasks")
            
        # Get all ideas
        cursor = await db.execute("SELECT id FROM ideas")
        ideas = await cursor.fetchall()
        print(f"Scoring {len(ideas)} ideas...")
        for row in ideas:
            await update_object_scores(db, row['id'], "ideas")
            
        # Get all decisions
        cursor = await db.execute("SELECT id FROM decisions")
        decisions = await cursor.fetchall()
        print(f"Scoring {len(decisions)} decisions...")
        for row in decisions:
            await update_object_scores(db, row['id'], "decisions")
            
        await db.commit()
    print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate_all_scores())
