import sqlite3
import os

db_path = 'data/raphael.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE tasks ADD COLUMN last_modified_locally TIMESTAMP")
    print("Added last_modified_locally column")
    
    # Backfill with current time for existing rows
    cursor.execute("UPDATE tasks SET last_modified_locally = CURRENT_TIMESTAMP")
    print("Backfilled last_modified_locally")
except sqlite3.OperationalError as e:
    print(f"Column last_modified_locally might already exist: {e}")

conn.commit()
conn.close()
print("Migration complete")
