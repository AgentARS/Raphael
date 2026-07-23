import sqlite3
import os

db_path = 'data/raphael.db'
if not os.path.exists(db_path):
    print("DB not found")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active',
            supersedes TEXT,
            reason TEXT,
            evidence TEXT,
            project_id TEXT REFERENCES entities(id) ON DELETE SET NULL,
            source_entry_id TEXT REFERENCES entries(id) ON DELETE SET NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("Created decisions table")
except Exception as e:
    print(f"Error creating table: {e}")

conn.commit()
conn.close()
print("Migration complete")
