import uuid
from typing import Optional, Dict, Any
from aiosqlite import Connection

async def resolve_entity(db: Connection, name: str, entity_type: str) -> str:
    """
    Resolves an entity by name (case-insensitive exact match).
    First checks for ANY entity with the same name regardless of type.
    If it exists, returns its ID (preventing duplicates like 'EE' as both project and topic).
    If it doesn't exist, creates it and returns the new ID.
    """
    if not name or not name.strip():
        return None
        
    normalized_name = name.strip()
    
    # Check if exists by name alone (case insensitive) to prevent duplicates
    async with db.execute(
        "SELECT id FROM entities WHERE LOWER(name) = LOWER(?) LIMIT 1",
        (normalized_name,)
    ) as cursor:
        row = await cursor.fetchone()
        if row:
            return row[0]
            
    # Doesn't exist, create it
    entity_id = str(uuid.uuid4())
    await db.execute(
        "INSERT INTO entities (id, type, name) VALUES (?, ?, ?)",
        (entity_id, entity_type, normalized_name)
    )
    return entity_id

async def resolve_entity_by_name_only(db: Connection, name: str, default_type: str = "project") -> Optional[str]:
    """
    Finds an entity by name only, prioritizing the first match.
    If it doesn't exist, automatically creates it with the default_type.
    """
    if not name or not name.strip():
        return None
        
    normalized_name = name.strip()
    
    async with db.execute(
        "SELECT id FROM entities WHERE LOWER(name) = LOWER(?) LIMIT 1",
        (normalized_name,)
    ) as cursor:
        row = await cursor.fetchone()
        if row:
            return row[0]
            
    # Auto-create if it was referenced but not defined in the entities block
    entity_id = str(uuid.uuid4())
    await db.execute(
        "INSERT INTO entities (id, type, name) VALUES (?, ?, ?)",
        (entity_id, default_type, normalized_name)
    )
    return entity_id
