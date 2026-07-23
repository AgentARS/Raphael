import re

with open('backend/routers/tasks.py', 'r') as f:
    content = f.read()

new_sync = """@router.post("/sync")
async def sync_tasks():
    \"\"\"Sync tasks with Google Tasks.\"\"\"
    async with get_db() as db:
        google_tasks = await asyncio.to_thread(calendar_service.get_all_google_tasks)
        if google_tasks is None:
            return {"status": "error", "message": "Failed to fetch google tasks", "synced": 0}
            
        cursor = await db.execute("SELECT id, google_task_id, status FROM tasks WHERE google_task_id IS NOT NULL")
        local_tasks = await cursor.fetchall()
        local_gtask_ids = {t["google_task_id"]: t for t in local_tasks}
        
        synced_count = 0
        
        # 1. Sync from Google to Local (Imports & Updates)
        for gid, gtask in google_tasks.items():
            is_deleted = gtask.get("deleted") == True or gtask.get("hidden") == True
            
            if gid not in local_gtask_ids:
                if is_deleted:
                    continue # don't import deleted tasks
                
                # Import new task
                import uuid
                from datetime import datetime
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
                    "INSERT INTO tasks (id, description, status, priority, google_task_id, due_date, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (task_id, desc, status, "medium", gid, due, created_at)
                )
                synced_count += 1
            else:
                # Update existing task
                local_task = local_gtask_ids[gid]
                if is_deleted:
                    await db.execute("DELETE FROM tasks WHERE id = ?", (local_task["id"],))
                    synced_count += 1
                else:
                    gstatus = gtask.get("status")
                    is_done_google = (gstatus == 'completed')
                    is_done_local = (local_task["status"] == 'done')
                    
                    if is_done_google and not is_done_local:
                        await db.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (local_task["id"],))
                        synced_count += 1
                    elif not is_done_google and is_done_local:
                        await db.execute("UPDATE tasks SET status = 'open' WHERE id = ?", (local_task["id"],))
                        synced_count += 1
                        
        await db.commit()
    return {"status": "ok", "synced": synced_count}
"""

pattern = re.compile(r'@router\.post\("/sync"\)\s*async def sync_tasks\(\):.*?(?=@router\.get\("/suggested")', re.DOTALL)
content = pattern.sub(new_sync + '\n', content)

with open('backend/routers/tasks.py', 'w') as f:
    f.write(content)
