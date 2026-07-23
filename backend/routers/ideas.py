from fastapi import APIRouter, Query, HTTPException
import json
import uuid
from database import get_db
from models import IdeaResponse, IdeaCreate, IdeaUpdate

router = APIRouter(prefix="/api/ideas", tags=["ideas"])

@router.get("", response_model=list[IdeaResponse])
async def list_ideas(project_id: str | None = None):
    """List ideas, optionally filtered by project."""
    async with get_db() as db:
        if project_id:
            cursor = await db.execute("""
                SELECT ideas.*, entities.name as project_name 
                FROM ideas 
                LEFT JOIN entities ON ideas.project_id = entities.id 
                WHERE ideas.project_id = ? 
                ORDER BY ideas.created_at DESC
            """, (project_id,))
        else:
            cursor = await db.execute("""
                SELECT ideas.*, entities.name as project_name 
                FROM ideas 
                LEFT JOIN entities ON ideas.project_id = entities.id 
                ORDER BY ideas.created_at DESC
            """)
        
        rows = await cursor.fetchall()
        
    return [
        IdeaResponse(
            id=row["id"],
            description=row["description"],
            project_id=row["project_id"],
            project_name=row["project_name"],
            source_entry_id=row["source_entry_id"],
            created_at=row["created_at"],
        ) for row in rows
    ]

@router.post("", response_model=IdeaResponse, status_code=201)
async def create_idea(idea: IdeaCreate):
    """Create a new idea."""
    idea_id = str(uuid.uuid4())
    async with get_db() as db:
        await db.execute(
            """INSERT INTO ideas (id, description, project_id) 
               VALUES (?, ?, ?)""",
            (idea_id, idea.description, idea.project_id)
        )
        await db.commit()
        
        cursor = await db.execute("""
            SELECT ideas.*, entities.name as project_name 
            FROM ideas 
            LEFT JOIN entities ON ideas.project_id = entities.id 
            WHERE ideas.id = ?
        """, (idea_id,))
        row = await cursor.fetchone()
        
    return IdeaResponse(
        id=row["id"],
        description=row["description"],
        project_id=row["project_id"],
            project_name=row["project_name"],
        source_entry_id=row["source_entry_id"],
        created_at=row["created_at"],
    )

@router.put("/{idea_id}", response_model=IdeaResponse)
async def update_idea(idea_id: str, updates: IdeaUpdate):
    """Update an idea."""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT ideas.*, entities.name as project_name 
            FROM ideas 
            LEFT JOIN entities ON ideas.project_id = entities.id 
            WHERE ideas.id = ?
        """, (idea_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Idea not found")
            
        fields = []
        values = []
        for key, value in updates.model_dump(exclude_unset=True).items():
            fields.append(f"{key} = ?")
            values.append(value)
                
        if fields:
            values.append(idea_id)
            query = f"UPDATE ideas SET {', '.join(fields)} WHERE id = ?"
            await db.execute(query, values)
            await db.commit()
            
        cursor = await db.execute("""
            SELECT ideas.*, entities.name as project_name 
            FROM ideas 
            LEFT JOIN entities ON ideas.project_id = entities.id 
            WHERE ideas.id = ?
        """, (idea_id,))
        row = await cursor.fetchone()
        
    return IdeaResponse(
        id=row["id"],
        description=row["description"],
        project_id=row["project_id"],
            project_name=row["project_name"],
        source_entry_id=row["source_entry_id"],
        created_at=row["created_at"],
    )

@router.delete("/{idea_id}", status_code=204)
async def delete_idea(idea_id: str):
    """Delete an idea."""
    async with get_db() as db:
        await db.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))
        await db.commit()
