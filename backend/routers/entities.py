from fastapi import APIRouter, Query, HTTPException
from database import get_db
from models import EntityResponse, EntityCreate, EntityUpdate, EntityGraphResponse, EntryResponse, TaskResponse, IdeaResponse, EntityRelationResponse, NetworkResponse, NetworkNode, NetworkLink, KnowledgeScores
from scoring.engine import fetch_scores
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/entities", tags=["entities"])

@router.post("", response_model=EntityResponse, status_code=201)
async def create_entity(entity: EntityCreate):
    """Create a new entity manually."""
    entity_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat() + "Z"
    
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO entities (id, type, name, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (entity_id, entity.type, entity.name, created_at)
        )
        await db.commit()
        
        cursor = await db.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
        row = await cursor.fetchone()
        
    return EntityResponse(
        id=row["id"],
        type=row["type"],
        name=row["name"],
        aliases=[],
        metadata={},
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )

@router.get("/network", response_model=NetworkResponse)
async def get_network():
    """Get the full network graph of all entities and relations, bridging relational + semantic edges."""
    async with get_db() as db:
        nodes = []
        
        # 1. Fetch ALL structural entities
        cursor = await db.execute("SELECT id, name, type, confidence FROM entities")
        entity_rows = await cursor.fetchall()
        entity_ids = {r["id"] for r in entity_rows}
        for r in entity_rows:
            nodes.append(NetworkNode(id=r["id"], name=r["name"], type=r["type"], confidence=r["confidence"] or 1.0))
            
        # 2. Fetch Tasks as Nodes
        cursor = await db.execute("SELECT id, description, confidence FROM tasks")
        for r in await cursor.fetchall():
            nodes.append(NetworkNode(id=r["id"], name=r["description"], type="Task", confidence=r["confidence"] or 1.0))
            
        # 3. Fetch Ideas as Nodes
        cursor = await db.execute("SELECT id, description, confidence FROM ideas")
        for r in await cursor.fetchall():
            nodes.append(NetworkNode(id=r["id"], name=r["description"], type="Idea", confidence=r["confidence"] or 1.0))
        
        links = []
        
        # A. Semantic Edges (Source of truth for knowledge graph links)
        cursor = await db.execute("SELECT from_entity_id, to_entity_id, relationship, confidence FROM entity_relations")
        for r in await cursor.fetchall():
            if r["from_entity_id"] in entity_ids and r["to_entity_id"] in entity_ids:
                links.append(NetworkLink(
                    source=r["from_entity_id"], 
                    target=r["to_entity_id"], 
                    label=r["relationship"], 
                    weight=1, 
                    confidence=r["confidence"] or 1.0
                ))
                
        # B. Structured Relational Edges (Tasks -> Projects/Assignees)
        cursor = await db.execute("SELECT id, assignee_id, project_id FROM tasks")
        for r in await cursor.fetchall():
            task_id = r["id"]
            if r["assignee_id"] in entity_ids:
                links.append(NetworkLink(source=task_id, target=r["assignee_id"], label="assigned_to", weight=1, confidence=1.0))
            if r["project_id"] in entity_ids:
                links.append(NetworkLink(source=task_id, target=r["project_id"], label="belongs_to", weight=1, confidence=1.0))
                
        # C. Structured Relational Edges (Ideas -> Projects)
        cursor = await db.execute("SELECT id, project_id FROM ideas")
        for r in await cursor.fetchall():
            idea_id = r["id"]
            if r["project_id"] in entity_ids:
                links.append(NetworkLink(source=idea_id, target=r["project_id"], label="belongs_to", weight=1, confidence=1.0))
                
    return NetworkResponse(nodes=nodes, links=links)

@router.get("", response_model=list[EntityResponse])
async def list_entities(type: str | None = None):
    """List entities, optionally filtered by type (e.g. 'project')."""
    async with get_db() as db:
        if type:
            cursor = await db.execute(
                "SELECT * FROM entities WHERE type = ? ORDER BY name ASC", 
                (type,)
            )
        else:
            cursor = await db.execute("SELECT * FROM entities ORDER BY name ASC")
            
        rows = await cursor.fetchall()
        scores_map = await fetch_scores(db, [row["id"] for row in rows])
        
    return [
        EntityResponse(
            id=row["id"],
            type=row["type"],
            name=row["name"],
            aliases=[], # simplification for now
            metadata={},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            scores=KnowledgeScores(**scores_map.get(row["id"], {})) if row["id"] in scores_map else None
        ) for row in rows
    ]
    
@router.put("/{entity_id}", response_model=EntityResponse)
async def update_entity(entity_id: str, update: EntityUpdate):
    """Update an entity."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Entity not found")
            
        new_name = update.name if update.name is not None else row["name"]
        new_type = update.type if update.type is not None else row["type"]
        updated_at = datetime.utcnow().isoformat() + "Z"
        
        await db.execute(
            "UPDATE entities SET name = ?, type = ?, updated_at = ? WHERE id = ?",
            (new_name, new_type, updated_at, entity_id)
        )
        await db.commit()
        
        cursor = await db.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
        updated_row = await cursor.fetchone()
        
    return EntityResponse(
        id=updated_row["id"],
        type=updated_row["type"],
        name=updated_row["name"],
        aliases=[],
        metadata={},
        created_at=updated_row["created_at"],
        updated_at=updated_row["updated_at"]
    )

@router.delete("/{entity_id}", status_code=204)
async def delete_entity(entity_id: str):
    """Delete an entity."""
    async with get_db() as db:
        await db.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
        await db.commit()
    return None

@router.get("/{entity_id}", response_model=EntityResponse)
async def get_entity(entity_id: str):
    """Get a single entity by ID."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Entity not found")
            
    return EntityResponse(
        id=row["id"],
        type=row["type"],
        name=row["name"],
        aliases=[],
        metadata={},
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )

@router.get("/{entity_id}/graph", response_model=EntityGraphResponse)
async def get_entity_graph(entity_id: str):
    """Get the full graph context for an entity."""
    import json
    async with get_db() as db:
        # 1. Get Entity
        cursor = await db.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
        ent_row = await cursor.fetchone()
        
        if not ent_row:
            # Fallback to checking if it's an idea
            cursor = await db.execute("SELECT * FROM ideas WHERE id = ?", (entity_id,))
            idea_row = await cursor.fetchone()
            if not idea_row:
                raise HTTPException(status_code=404, detail="Entity or Idea not found")
                
            entity = EntityResponse(
                id=idea_row["id"], type="idea", name=idea_row["description"],
                aliases=[], metadata={"project_id": idea_row["project_id"], "source_entry_id": idea_row["source_entry_id"]},
                created_at=idea_row["created_at"], updated_at=None
            )
        else:
            entity = EntityResponse(
                id=ent_row["id"], type=ent_row["type"], name=ent_row["name"],
                aliases=json.loads(ent_row["aliases"]), metadata=json.loads(ent_row["metadata"]),
                created_at=ent_row["created_at"], updated_at=ent_row["updated_at"]
            )
        
        # 2. Get Entries
        cursor = await db.execute(
            """
            SELECT DISTINCT e.* FROM entries e
            LEFT JOIN entry_entities ee ON e.id = ee.entry_id
            WHERE ee.entity_id = ? OR e.id = (SELECT source_entry_id FROM ideas WHERE id = ?)
            ORDER BY e.created_at DESC
            """, (entity_id, entity_id)
        )
        entry_rows = await cursor.fetchall()
        entries = [
            EntryResponse(
                id=er["id"], content=er["content"], created_at=er["created_at"],
                updated_at=er["updated_at"], source_type=er["source_type"],
                extraction_status=er["extraction_status"], entities=[]
            ) for er in entry_rows
        ]
        
        # Fetch related ideas
        cursor = await db.execute(
            """SELECT * FROM ideas 
               WHERE project_id = ? OR source_entry_id IN 
                 (SELECT entry_id FROM entry_entities WHERE entity_id = ?)
               ORDER BY created_at DESC""",
            (entity_id, entity_id)
        )
        ideas = [
            IdeaResponse(
                id=r["id"],
                description=r["description"],
                project_id=r["project_id"],
                source_entry_id=r["source_entry_id"],
                created_at=r["created_at"]
            ) for r in await cursor.fetchall()
        ]
        
        # 3. Get Tasks
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE assignee_id = ? OR project_id = ? ORDER BY created_at DESC", 
            (entity_id, entity_id)
        )
        task_rows = await cursor.fetchall()
        tasks = [TaskResponse(**dict(tr)) for tr in task_rows]
        
        # 5. Get Relations
        cursor = await db.execute(
            "SELECT * FROM entity_relations WHERE from_entity_id = ? OR to_entity_id = ? ORDER BY created_at DESC", 
            (entity_id, entity_id)
        )
        rel_rows = await cursor.fetchall()
        relations = [EntityRelationResponse(**dict(rr)) for rr in rel_rows]
        
        # 6. Get Decisions
        cursor = await db.execute(
            "SELECT * FROM decisions WHERE project_id = ? ORDER BY created_at DESC",
            (entity_id,)
        )
        dec_rows = await cursor.fetchall()
        decisions = [DecisionResponse(**dict(dr)) for dr in dec_rows]
        # Fetch Scores for ALL objects
        all_ids = [entity.id] + [e.id for e in entries] + [t.id for t in tasks] + [i.id for i in ideas] + [d.id for d in decisions]
        scores_map = await fetch_scores(db, all_ids)
        
        if entity.id in scores_map:
            entity.scores = KnowledgeScores(**scores_map[entity.id])
        for e in entries:
            if e.id in scores_map: e.scores = KnowledgeScores(**scores_map[e.id])
        for t in tasks:
            if t.id in scores_map: t.scores = KnowledgeScores(**scores_map[t.id])
        for i in ideas:
            if i.id in scores_map: i.scores = KnowledgeScores(**scores_map[i.id])
        for d in decisions:
            if d.id in scores_map: d.scores = KnowledgeScores(**scores_map[d.id])

    return EntityGraphResponse(
        entity=entity,
        entries=entries,
        tasks=tasks,
        ideas=ideas,
        decisions=decisions,
        relations=relations
    )
