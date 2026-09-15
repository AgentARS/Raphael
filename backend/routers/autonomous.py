from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from database import get_db
from autonomous.scheduler import scheduler

router = APIRouter(prefix="/api/autonomous", tags=["autonomous"])

class ModeUpdate(BaseModel):
    mode: str

@router.get("/status")
async def get_status():
    async with get_db() as db:
        # Get settings
        cursor = await db.execute("SELECT key, value FROM autonomous_settings")
        settings_rows = await cursor.fetchall()
        settings = {r['key']: r['value'] for r in settings_rows}
        
        # Get pending tasks count
        cursor = await db.execute("SELECT COUNT(*) as count FROM autonomous_tasks WHERE enabled = 1 AND next_eligible_run <= CURRENT_TIMESTAMP")
        pending_count = (await cursor.fetchone())['count']
        
        # Get next wake (min next_eligible_run)
        cursor = await db.execute("SELECT MIN(next_eligible_run) as next_wake, MAX(last_run) as last_maintenance FROM autonomous_tasks WHERE enabled = 1")
        time_row = await cursor.fetchone()
        
    return {
        "mode": settings.get("mode", "manual"),
        "is_running": scheduler.is_running,
        "current_task": scheduler.current_task,
        "pending_tasks": pending_count,
        "next_wake": time_row['next_wake'] if time_row else None,
        "last_maintenance": time_row['last_maintenance'] if time_row else None,
        "cpu_max": settings.get("max_cpu_percent"),
        "ram_max": settings.get("max_ram_percent")
    }

@router.post("/mode")
async def update_mode(data: ModeUpdate):
    if data.mode not in ['manual', 'autonomous']:
        raise HTTPException(status_code=400, detail="Invalid mode")
        
    async with get_db() as db:
        await db.execute("UPDATE autonomous_settings SET value = ? WHERE key = 'mode'", (data.mode,))
        await db.commit()
        
    return {"status": "ok", "mode": data.mode}

@router.post("/run-now")
async def run_now():
    """Forces all enabled tasks to become eligible immediately."""
    async with get_db() as db:
        # Set next_eligible_run to now
        await db.execute("UPDATE autonomous_tasks SET next_eligible_run = CURRENT_TIMESTAMP WHERE enabled = 1")
        await db.commit()
    return {"status": "ok", "message": "Maintenance triggered"}

@router.post("/pause")
async def pause_processing():
    """Sets mode to manual."""
    async with get_db() as db:
        await db.execute("UPDATE autonomous_settings SET value = 'manual' WHERE key = 'mode'")
        await db.commit()
    return {"status": "ok", "mode": "manual"}
