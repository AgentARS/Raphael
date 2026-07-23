from fastapi import APIRouter, Query, HTTPException
from database import get_db
from models import TaskResponse, TaskUpdate, TaskCreate, PendingTaskUpdateResponse, SemanticTaskUpdate
import uuid
from datetime import datetime
import asyncio
import calendar_service
from extraction.pipeline import resolve_task

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(task: TaskCreate):
    """Create a task manually."""
    task_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat() + "Z"
    
    google_task_id = None
    sync_status = 'synced'
    try:
        google_task_id = await asyncio.to_thread(calendar_service.create_google_task, task.description)
    except Exception as e:
        print(f"Offline or network error during create_task: {e}")
        sync_status = 'pending_create'
    
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO tasks (id, description, status, priority, project_id, google_task_id, sync_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, task.description, "todo", task.priority, task.project_id, google_task_id, sync_status, created_at)
        )
        await db.commit()
        
        # Fetch the created task to return
        cursor = await db.execute("""
            SELECT tasks.*, entities.name as project_name 
            FROM tasks 
            LEFT JOIN entities ON tasks.project_id = entities.id 
            WHERE tasks.id = ?
        """, (task_id,))
        row = await cursor.fetchone()
        
    return TaskResponse(
        id=row["id"],
        description=row["description"],
        status=row["status"],
        priority=row["priority"],
        assignee_id=row["assignee_id"],
        project_id=row["project_id"],
        project_name=row["project_name"],
        due_date=row["due_date"],
        source_entry_id=row["source_entry_id"],
        created_at=row["created_at"],
        completed_at=row["completed_at"]
    )

@router.post("/sync")
async def sync_tasks():
    """Sync tasks with Google Tasks."""
    async with get_db() as db:
        # --- PUSH PHASE ---
        cursor = await db.execute("SELECT * FROM tasks WHERE sync_status != 'synced'")
        pending_tasks = await cursor.fetchall()
        
        for ptask in pending_tasks:
            try:
                if ptask['sync_status'] == 'pending_create':
                    gid = await asyncio.to_thread(calendar_service.create_google_task, ptask['description'], ptask['due_date'])
                    if gid:
                        await db.execute("UPDATE tasks SET google_task_id = ?, sync_status = 'synced' WHERE id = ?", (gid, ptask['id']))
                elif ptask['sync_status'] == 'pending_update':
                    if ptask['google_task_id']:
                        success = await asyncio.to_thread(calendar_service.update_google_task, ptask['google_task_id'], title=ptask['description'], due_date=ptask['due_date'], status=ptask['status'])
                        if success:
                            await db.execute("UPDATE tasks SET sync_status = 'synced' WHERE id = ?", (ptask['id'],))
                elif ptask['sync_status'] == 'pending_delete':
                    if ptask['google_task_id']:
                        await asyncio.to_thread(calendar_service.delete_google_task, ptask['google_task_id'])
                    await db.execute("DELETE FROM tasks WHERE id = ?", (ptask['id'],))
            except Exception as e:
                print(f"Failed to push task {ptask['id']}: {e}")
                
        await db.commit()
        
        # --- PULL PHASE ---
        google_tasks = await asyncio.to_thread(calendar_service.get_all_google_tasks)
        if google_tasks is None:
            return {"status": "error", "message": "Failed to fetch google tasks", "synced": 0}
            
        cursor = await db.execute("SELECT id, google_task_id, status, description, sync_status, last_modified_locally FROM tasks WHERE google_task_id IS NOT NULL")
        local_tasks = await cursor.fetchall()
        local_gtask_ids = {t["google_task_id"]: t for t in local_tasks}
        
        synced_count = 0
        from datetime import datetime
        
        for gid, gtask in google_tasks.items():
            is_deleted = gtask.get("deleted") == True
            
            if gid not in local_gtask_ids:
                if is_deleted:
                    continue # don't import deleted tasks
                
                # Import new task
                import uuid
                task_id = str(uuid.uuid4())
                desc = gtask.get("title", "Untitled Task")
                status = 'done' if gtask.get("status") == 'completed' else 'open'
                created_at = datetime.utcnow().isoformat() + "Z"
                
                due = gtask.get("due")
                if due and len(due) >= 10:
                    due = due[:10] # extract YYYY-MM-DD
                else:
                    due = None
                    
                await db.execute(
                    "INSERT INTO tasks (id, description, status, priority, google_task_id, due_date, sync_status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'synced', ?)",
                    (task_id, desc, status, "medium", gid, due, created_at)
                )
                synced_count += 1
            else:
                # Update existing task
                local_task = local_gtask_ids[gid]
                
                g_updated_str = gtask.get("updated", "")
                l_updated_str = local_task["last_modified_locally"] if "last_modified_locally" in local_task.keys() else ""
                
                g_time = None
                l_time = None
                try:
                    if g_updated_str:
                        g_time = datetime.fromisoformat(g_updated_str.replace("Z", "+00:00"))
                    if l_updated_str:
                        if not l_updated_str.endswith("Z") and "+" not in l_updated_str:
                            l_updated_str += "+00:00"
                        elif l_updated_str.endswith("Z"):
                            l_updated_str = l_updated_str.replace("Z", "+00:00")
                        l_time = datetime.fromisoformat(l_updated_str)
                except Exception as e:
                    print(f"Error parsing dates: {e}")
                
                local_is_newer = False
                if g_time and l_time:
                    local_is_newer = (l_time > g_time)
                elif l_time and not g_time:
                    local_is_newer = True
                    
                if local_is_newer and local_task['sync_status'] != 'synced':
                    continue # Local changes win
                
                if is_deleted:
                    await db.execute("DELETE FROM tasks WHERE id = ?", (local_task["id"],))
                    synced_count += 1
                else:
                    updates = []
                    params = []
                    
                    gstatus = gtask.get("status")
                    is_done_google = (gstatus == 'completed')
                    is_done_local = (local_task["status"] == 'done')
                    
                    if is_done_google and not is_done_local:
                        updates.append("status = 'done'")
                    elif not is_done_google and is_done_local:
                        updates.append("status = 'open'")
                        
                    gdesc = gtask.get("title", "")
                    if gdesc and gdesc != local_task["description"]:
                        updates.append("description = ?")
                        params.append(gdesc)
                        
                    if updates:
                        params.append(local_task["id"])
                        query = f"UPDATE tasks SET {', '.join(updates)}, sync_status = 'synced' WHERE id = ?"
                        await db.execute(query, params)
                        synced_count += 1
                        
        await db.commit()
    return {"status": "ok", "synced": synced_count}

@router.get("/suggested", response_model=list[TaskResponse])
async def list_suggested_tasks():
    """List tasks that were suggested by the AI but not yet approved."""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT tasks.*, entities.name as project_name 
            FROM tasks 
            LEFT JOIN entities ON tasks.project_id = entities.id 
            WHERE tasks.status = 'suggested' AND tasks.sync_status != 'pending_delete'
            ORDER BY tasks.created_at DESC
        """)
        rows = await cursor.fetchall()
        
    return [
        TaskResponse(
            id=row["id"],
            description=row["description"],
            status=row["status"],
            priority=row["priority"],
            assignee_id=row["assignee_id"],
            project_id=row["project_id"],
            project_name=row["project_name"],
            due_date=row["due_date"],
            source_entry_id=row["source_entry_id"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        ) for row in rows
    ]

@router.get("", response_model=list[TaskResponse])
async def list_tasks(project_id: str | None = None):
    """List tasks, optionally filtered by project."""
    async with get_db() as db:
        if project_id:
            cursor = await db.execute("""
                SELECT tasks.*, entities.name as project_name 
                FROM tasks 
                LEFT JOIN entities ON tasks.project_id = entities.id 
                WHERE tasks.project_id = ? AND tasks.sync_status != 'pending_delete'
                ORDER BY tasks.created_at DESC
            """, (project_id,))
        else:
            cursor = await db.execute("""
                SELECT tasks.*, entities.name as project_name 
                FROM tasks 
                LEFT JOIN entities ON tasks.project_id = entities.id 
                WHERE tasks.sync_status != 'pending_delete'
                ORDER BY tasks.created_at DESC
            """)
        
        rows = await cursor.fetchall()
        
    return [
        TaskResponse(
            id=row["id"],
            description=row["description"],
            status=row["status"],
            priority=row["priority"],
            assignee_id=row["assignee_id"],
            project_id=row["project_id"],
            project_name=row["project_name"],
            due_date=row["due_date"],
            source_entry_id=row["source_entry_id"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        ) for row in rows
    ]

@router.put("/{task_id}/status", response_model=TaskResponse)
async def update_task_status(task_id: str, status: str = Query(...)):
    """Update task status (e.g., 'done')."""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT tasks.*, entities.name as project_name 
            FROM tasks 
            LEFT JOIN entities ON tasks.project_id = entities.id 
            WHERE tasks.id = ?
        """, (task_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
            
        old_status = row['status']
        google_task_id = row['google_task_id']
        
        if status == 'open' and old_status == 'suggested':
            sync_status = 'synced'
            try:
                google_task_id = await asyncio.to_thread(calendar_service.create_google_task, row['description'], row['due_date'])
            except Exception as e:
                print(f"Offline or network error: {e}")
                google_task_id = None
                sync_status = 'pending_create'
            
            await db.execute("UPDATE tasks SET status = ?, google_task_id = ?, sync_status = ?, last_modified_locally = CURRENT_TIMESTAMP WHERE id = ?", (status, google_task_id, sync_status, task_id))
        else:
            sync_status = 'synced'
            if google_task_id and status in ['done', 'todo', 'open']:
                try:
                    await asyncio.to_thread(calendar_service.update_google_task, google_task_id, status=status)
                except Exception as e:
                    print(f"Offline or network error: {e}")
                    sync_status = 'pending_update'
            await db.execute("UPDATE tasks SET status = ?, sync_status = ?, last_modified_locally = CURRENT_TIMESTAMP WHERE id = ?", (status, sync_status, task_id))
            
        await db.commit()
        
        cursor = await db.execute("""
            SELECT tasks.*, entities.name as project_name 
            FROM tasks 
            LEFT JOIN entities ON tasks.project_id = entities.id 
            WHERE tasks.id = ?
        """, (task_id,))
        row = await cursor.fetchone()
        
    return TaskResponse(
        id=row["id"],
        description=row["description"],
        status=row["status"],
        priority=row["priority"],
        assignee_id=row["assignee_id"],
        project_id=row["project_id"],
        project_name=row["project_name"],
        due_date=row["due_date"],
        source_entry_id=row["source_entry_id"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: str, updates: TaskUpdate):
    """Update task details."""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT tasks.*, entities.name as project_name 
            FROM tasks 
            LEFT JOIN entities ON tasks.project_id = entities.id 
            WHERE tasks.id = ?
        """, (task_id,))
        row = await cursor.fetchone()
        
        updates_dict = updates.model_dump(exclude_unset=True)
        if updates_dict:
            set_clause = ", ".join([f"{k} = ?" for k in updates_dict.keys()])
            values = list(updates_dict.values())
            
            sync_status = row['sync_status'] if row and 'sync_status' in row.keys() else 'synced'
            
            if row and row['google_task_id']:
                try:
                    due_date_str = None
                    if 'due_date' in updates_dict:
                        if updates_dict['due_date']:
                            due_date_str = str(updates_dict['due_date'])
                        else:
                            due_date_str = "" # Clear it
                            
                    await asyncio.to_thread(
                        calendar_service.update_google_task, 
                        row['google_task_id'], 
                        title=updates_dict.get('description'),
                        due_date=due_date_str
                    )
                    sync_status = 'synced'
                except Exception as e:
                    print(f"Offline or network error: {e}")
                    sync_status = 'pending_update'
                    
            set_clause += ", sync_status = ?, last_modified_locally = CURRENT_TIMESTAMP"
            values.append(sync_status)
            values.append(task_id)
            
            await db.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
            await db.commit()
            
        cursor = await db.execute("""
            SELECT tasks.*, entities.name as project_name 
            FROM tasks 
            LEFT JOIN entities ON tasks.project_id = entities.id 
            WHERE tasks.id = ?
        """, (task_id,))
        row = await cursor.fetchone()
        
    return TaskResponse(
        id=row["id"],
        description=row["description"],
        status=row["status"],
        priority=row["priority"],
        assignee_id=row["assignee_id"],
        project_id=row["project_id"],
        project_name=row["project_name"],
        due_date=row["due_date"],
        source_entry_id=row["source_entry_id"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )

@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str):
    """Delete a task."""
    async with get_db() as db:
        cursor = await db.execute("SELECT google_task_id FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        
        if row and row['google_task_id']:
            try:
                await asyncio.to_thread(calendar_service.delete_google_task, row['google_task_id'])
                await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            except Exception as e:
                print(f"Offline or network error during delete: {e}")
                await db.execute("UPDATE tasks SET sync_status = 'pending_delete', last_modified_locally = CURRENT_TIMESTAMP WHERE id = ?", (task_id,))
        else:
            await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            
        await db.commit()

# --- Pending Task Updates ---

@router.get("/pending-updates", response_model=list[PendingTaskUpdateResponse])
async def list_pending_updates():
    """List pending AI-proposed task updates."""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT p.id, p.task_id, p.action, p.source_entry_id, p.created_at, t.description as task_description
            FROM pending_task_updates p
            JOIN tasks t ON p.task_id = t.id
            ORDER BY p.created_at DESC
        """)
        rows = await cursor.fetchall()
        
    return [
        PendingTaskUpdateResponse(
            id=row["id"],
            task_id=row["task_id"],
            task_description=row["task_description"],
            action=row["action"],
            source_entry_id=row["source_entry_id"],
            created_at=row["created_at"]
        ) for row in rows
    ]

@router.post("/pending-updates/{update_id}/approve", status_code=204)
async def approve_pending_update(update_id: str):
    """Approve a pending task update and execute it."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM pending_task_updates WHERE id = ?", (update_id,))
        update = await cursor.fetchone()
        if not update:
            raise HTTPException(status_code=404, detail="Pending update not found")
            
        task_id = update["task_id"]
        action = update["action"]
        
        if action == "mark_done":
            await db.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (task_id,))
            cursor = await db.execute("SELECT google_task_id FROM tasks WHERE id = ?", (task_id,))
            row = await cursor.fetchone()
            if row and row['google_task_id']:
                await asyncio.to_thread(calendar_service.update_google_task, row['google_task_id'], status='done')
        elif action == "delete":
            cursor = await db.execute("SELECT google_task_id FROM tasks WHERE id = ?", (task_id,))
            row = await cursor.fetchone()
            await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            if row and row['google_task_id']:
                await asyncio.to_thread(calendar_service.delete_google_task, row['google_task_id'])
            
        # Delete the pending update record
        await db.execute("DELETE FROM pending_task_updates WHERE id = ?", (update_id,))
        await db.commit()

@router.delete("/pending-updates/{update_id}/reject", status_code=204)
async def reject_pending_update(update_id: str):
    """Reject and delete a pending task update."""
    async with get_db() as db:
        await db.execute("DELETE FROM pending_task_updates WHERE id = ?", (update_id,))
        await db.commit()

@router.post("/semantic-update", status_code=202)
async def semantic_update_task(update: SemanticTaskUpdate):
    """Resolve a task via semantic description and create a pending update."""
    async with get_db() as db:
        matched_task_id = await resolve_task(db, update.semantic_description, include_completed=(update.action == 'delete'))
        if matched_task_id:
            await db.execute(
                """INSERT INTO pending_task_updates (id, task_id, action)
                   VALUES (?, ?, ?)""",
                (str(uuid.uuid4()), matched_task_id, update.action)
            )
            await db.commit()
            return {"status": "pending_created"}
        else:
            raise HTTPException(status_code=404, detail="No matching task found")
    return None
