import json
import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks
from models import InteractionEventCreate
from database import get_db

router = APIRouter(prefix="/api/events", tags=["events"])

async def log_event_to_db(event: InteractionEventCreate):
    """Asynchronously log the event to the database to avoid blocking the main thread."""
    try:
        async with get_db() as db:
            event_id = str(uuid.uuid4())
            metadata_json = json.dumps(event.metadata) if event.metadata else "{}"
            
            await db.execute(
                """
                INSERT INTO interaction_events (id, event_type, object_type, object_id, session_id, metadata, duration_ms, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id, 
                    event.event_type, 
                    event.object_type, 
                    event.object_id, 
                    event.session_id, 
                    metadata_json, 
                    event.duration_ms, 
                    event.source
                )
            )
            await db.commit()
    except Exception as e:
        # We swallow errors here because passive logging should never break the application
        print(f"Failed to log event {event.event_type}: {e}")


@router.post("")
async def create_event(event: InteractionEventCreate, background_tasks: BackgroundTasks):
    """
    Log an interaction event. Uses BackgroundTasks to return immediately.
    """
    background_tasks.add_task(log_event_to_db, event)
    return {"status": "success", "message": "Event queued for logging"}
