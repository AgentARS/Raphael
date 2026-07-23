import asyncio
import sqlite3
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

def migrate():
    db_path = os.path.join(os.path.dirname(__file__), '../backend/data/raphael.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create knowledge_scores table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_scores (
            object_id TEXT PRIMARY KEY,
            object_type TEXT NOT NULL,
            relevance REAL DEFAULT 50.0,
            significance REAL DEFAULT 50.0,
            previous_relevance REAL DEFAULT 50.0,
            explanation TEXT,
            last_computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
