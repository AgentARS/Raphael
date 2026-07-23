"""
Entry CRUD router for Raphael.

Provides endpoints for creating, listing, reading, updating, and deleting entries.
"""

from uuid import uuid4
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
import json

from database import get_db
from models import EntryCreate, EntryUpdate, EntryResponse, EntityResponse
from extraction.pipeline import process_entry
from models import KnowledgeScores

router = APIRouter(prefix="/api/entries", tags=["entries"])

async def _row_to_entry_response(db, row) -> EntryResponse:
    """Convert a database row to an EntryResponse, fetching entities."""
    entry_id = row["id"]
    cursor = await db.execute(
        """
        SELECT e.* FROM entities e
        JOIN entry_entities ee ON e.id = ee.entity_id
        WHERE ee.entry_id = ?
        """,
        (entry_id,)
    )
    entity_rows = await cursor.fetchall()
    entities = [
        EntityResponse(
            id=er["id"], type=er["type"], name=er["name"], 
            aliases=json.loads(er["aliases"]), metadata=json.loads(er["metadata"]),
            created_at=er["created_at"], updated_at=er["updated_at"]
        ) for er in entity_rows
    ]

    cursor = await db.execute("SELECT * FROM knowledge_scores WHERE object_id = ?", (entry_id,))
    score_row = await cursor.fetchone()
    scores = None
    if score_row:
        scores = KnowledgeScores(
            relevance=score_row["relevance"],
            significance=score_row["significance"],
            trend=score_row["relevance"] - score_row["previous_relevance"],
            explanation=score_row["explanation"]
        )

    return EntryResponse(
        id=entry_id,
        content=row["content"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        source_type=row["source_type"],
        extraction_status=row["extraction_status"],
        entities=entities,
        scores=scores,
    )

@router.post("", response_model=EntryResponse, status_code=201)
async def create_entry(entry: EntryCreate, background_tasks: BackgroundTasks):
    """Create a new entry with a generated UUID."""
    entry_id = str(uuid4())
    created_at = datetime.utcnow().isoformat() + "Z"

    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO entries (id, content, created_at, source_type)
            VALUES (?, ?, ?, ?)
            """,
            (entry_id, entry.content, created_at, entry.source_type),
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        )
        row = await cursor.fetchone()
        response = await _row_to_entry_response(db, row)

    background_tasks.add_task(process_entry, entry_id, entry.content, entry.context_project_id)
    return response


@router.get("", response_model=list[EntryResponse])
async def list_entries(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    entity_id: str | None = None,
    source_type: str | None = None,
):
    """List entries ordered by created_at descending, with pagination."""
    async with get_db() as db:
        query = "SELECT e.* FROM entries e"
        params = []
        conditions = []
        
        if entity_id:
            query += " JOIN entry_entities ee ON e.id = ee.entry_id"
            conditions.append("ee.entity_id = ?")
            params.append(entity_id)
            
        if source_type:
            conditions.append("e.source_type = ?")
            params.append(source_type)
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        query += " ORDER BY e.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = await db.execute(query, tuple(params))
        rows = await cursor.fetchall()
        
        responses = []
        for row in rows:
            responses.append(await _row_to_entry_response(db, row))

    return responses


@router.get("/{entry_id}", response_model=EntryResponse)
async def get_entry(entry_id: str):
    """Get a single entry by ID."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        )
        row = await cursor.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Entry not found")

        return await _row_to_entry_response(db, row)


@router.put("/{entry_id}", response_model=EntryResponse)
async def update_entry(entry_id: str, entry: EntryUpdate):
    """Update an entry's content and set updated_at timestamp."""
    async with get_db() as db:
        # Verify entry exists
        cursor = await db.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        )
        existing = await cursor.fetchone()

        if existing is None:
            raise HTTPException(status_code=404, detail="Entry not found")

        if entry.content is not None:
            updated_at = datetime.utcnow().isoformat() + "Z"
            await db.execute(
                """
                UPDATE entries SET content = ?, updated_at = ? WHERE id = ?
                """,
                (entry.content, updated_at, entry_id),
            )
            await db.commit()

        # Re-fetch the updated row
        cursor = await db.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        )
        row = await cursor.fetchone()
        
        return await _row_to_entry_response(db, row)


@router.delete("/{entry_id}", status_code=204)
async def delete_entry(entry_id: str):
    """Delete an entry by ID."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM entries WHERE id = ?", (entry_id,)
        )
        existing = await cursor.fetchone()

        if existing is None:
            raise HTTPException(status_code=404, detail="Entry not found")

        await db.execute("DELETE FROM tasks WHERE source_entry_id = ?", (entry_id,))
        await db.execute("DELETE FROM ideas WHERE source_entry_id = ?", (entry_id,))
        await db.execute("DELETE FROM entity_relations WHERE source_entry_id = ?", (entry_id,))
        await db.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        await db.commit()

    return None

@router.post("/{entry_id}/reprocess", response_model=EntryResponse)
async def reprocess_entry_data(entry_id: str, background_tasks: BackgroundTasks):
    """Force the entry to be re-processed by the LLM."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM entries WHERE id = ?", (entry_id,))
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Entry not found")
            
        # Delete existing associated tasks, ideas, entity_relations, entry_entities
        await db.execute("DELETE FROM tasks WHERE source_entry_id = ?", (entry_id,))
        await db.execute("DELETE FROM ideas WHERE source_entry_id = ?", (entry_id,))
        await db.execute("DELETE FROM entity_relations WHERE source_entry_id = ?", (entry_id,))
        await db.execute("DELETE FROM entry_entities WHERE entry_id = ?", (entry_id,))
            
        await db.execute(
            "UPDATE entries SET extraction_status = 'pending' WHERE id = ?", 
            (entry_id,)
        )
        await db.commit()
        
        response = await _row_to_entry_response(db, dict(row) | {"extraction_status": "pending"})

    background_tasks.add_task(process_entry, entry_id, row["content"])
    return response

@router.post("/{entry_id}/entities/{entity_id}", status_code=201)
async def link_entity_to_entry(entry_id: str, entity_id: str):
    """Manually link an entity to an entry."""
    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO entry_entities (entry_id, entity_id, relationship) VALUES (?, ?, ?)",
            (entry_id, entity_id, 'mentions')
        )
        await db.commit()
    return {"status": "success"}

@router.delete("/{entry_id}/entities/{entity_id}", status_code=204)
async def unlink_entity_from_entry(entry_id: str, entity_id: str):
    """Manually unlink an entity from an entry."""
    async with get_db() as db:
        await db.execute(
            "DELETE FROM entry_entities WHERE entry_id = ? AND entity_id = ? AND relationship = ?",
            (entry_id, entity_id, 'mentions')
        )
        await db.commit()
    return None
