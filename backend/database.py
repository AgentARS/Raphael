"""
Database module for Raphael.

Handles SQLite initialization with WAL mode, schema creation (6 tables + FTS5),
and provides an async context manager for database access.
"""

import os
import aiosqlite
from dotenv import load_dotenv
from contextlib import asynccontextmanager

load_dotenv()

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/raphael.db")


async def init_db():
    """Initialize the database: create directories, enable WAL, create all tables."""
    # Ensure the data directory exists
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Enable WAL mode for better concurrent access
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

        # --- Core tables ---

        await db.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                source_type TEXT NOT NULL DEFAULT 'manual',
                embedding BLOB,
                extraction_status TEXT NOT NULL DEFAULT 'pending'
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                aliases TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                embedding BLOB,
                confidence REAL DEFAULT 1.0,
                last_seen TIMESTAMP,
                mention_count INTEGER DEFAULT 1,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                UNIQUE(type, name)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                priority TEXT NOT NULL DEFAULT 'medium',
                confidence REAL DEFAULT 1.0,
                assignee_id TEXT REFERENCES entities(id) ON DELETE SET NULL,
                project_id TEXT REFERENCES entities(id) ON DELETE SET NULL,
                due_date DATE,
                source_entry_id TEXT REFERENCES entries(id) ON DELETE SET NULL,
                google_task_id TEXT,
                sync_status TEXT NOT NULL DEFAULT 'synced',
                last_modified_locally TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS ideas (
                id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                project_id TEXT REFERENCES entities(id) ON DELETE SET NULL,
                source_entry_id TEXT REFERENCES entries(id) ON DELETE SET NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
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

        await db.execute("""
            CREATE TABLE IF NOT EXISTS entry_entities (
                entry_id TEXT REFERENCES entries(id) ON DELETE CASCADE,
                entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
                relationship TEXT NOT NULL DEFAULT 'mentions',
                PRIMARY KEY (entry_id, entity_id, relationship)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS entity_relations (
                id TEXT PRIMARY KEY,
                from_entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
                to_entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
                relationship TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                source_entry_id TEXT REFERENCES entries(id) ON DELETE SET NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(from_entity_id, to_entity_id, relationship)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_task_updates (
                id TEXT PRIMARY KEY,
                task_id TEXT REFERENCES tasks(id) ON DELETE CASCADE,
                action TEXT NOT NULL,
                source_entry_id TEXT REFERENCES entries(id) ON DELETE CASCADE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
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

        await db.execute("""
            CREATE TABLE IF NOT EXISTS interaction_events (
                id TEXT PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                event_type TEXT NOT NULL,
                object_type TEXT,
                object_id TEXT,
                session_id TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                duration_ms INTEGER,
                source TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS autonomous_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_briefings (
                date TEXT PRIMARY KEY,
                content_json TEXT NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS autonomous_tasks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                priority INTEGER DEFAULT 5,
                estimated_cost_ms INTEGER DEFAULT 1000,
                max_runtime_ms INTEGER DEFAULT 300000,
                retry_policy TEXT DEFAULT 'exponential_backoff',
                last_run TIMESTAMP,
                next_eligible_run TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                enabled BOOLEAN DEFAULT 1
            )
        """)
        
        # Insert default settings
        await db.execute("INSERT OR IGNORE INTO autonomous_settings (key, value) VALUES ('mode', 'manual')")
        await db.execute("INSERT OR IGNORE INTO autonomous_settings (key, value) VALUES ('wake_interval_seconds', '300')")
        await db.execute("INSERT OR IGNORE INTO autonomous_settings (key, value) VALUES ('max_runtime_per_cycle_seconds', '300')")
        await db.execute("INSERT OR IGNORE INTO autonomous_settings (key, value) VALUES ('max_cpu_percent', '80.0')")
        await db.execute("INSERT OR IGNORE INTO autonomous_settings (key, value) VALUES ('max_ram_percent', '85.0')")

        # Seed initial tasks
        initial_tasks = [
            ("generate_daily_briefing", 15),
            ("refresh_relevance_scores", 10),
            ("refresh_significance_scores", 9),
            ("detect_stale_projects", 8),
            ("detect_open_loops", 7),
            ("merge_duplicate_entities", 6),
            ("validate_graph_consistency", 5),
            ("remove_invalid_relationships", 4),
            ("refresh_cached_dashboard", 3)
        ]
        for task_name, priority in initial_tasks:
            import uuid
            await db.execute("""
                INSERT OR IGNORE INTO autonomous_tasks (id, name, priority)
                VALUES (?, ?, ?)
            """, (str(uuid.uuid4()), task_name, priority))

        # --- FTS5 virtual table for full-text search on entries ---

        await db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
                content,
                content=entries,
                content_rowid=rowid
            )
        """)

        # --- Triggers to keep FTS5 in sync ---

        await db.execute("""
            CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
                INSERT INTO entries_fts(rowid, content) VALUES (new.rowid, new.content);
            END
        """)

        await db.execute("""
            CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
                INSERT INTO entries_fts(entries_fts, rowid, content) VALUES('delete', old.rowid, old.content);
            END
        """)

        await db.execute("""
            CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
                INSERT INTO entries_fts(entries_fts, rowid, content) VALUES('delete', old.rowid, old.content);
                INSERT INTO entries_fts(rowid, content) VALUES (new.rowid, new.content);
            END
        """)

        await db.commit()


@asynccontextmanager
async def get_db():
    """Async context manager that yields a database connection with foreign keys enabled."""
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
    finally:
        await db.close()
