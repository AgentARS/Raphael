from fastapi import APIRouter, HTTPException
from database import get_db
import datetime
import json
import calendar_service

router = APIRouter(prefix="/api/briefing", tags=["briefing"])

@router.get("/today")
async def get_daily_briefing():
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    
    async with get_db() as db:
        cursor = await db.execute("SELECT content_json, last_updated FROM daily_briefings WHERE date = ?", (today,))
        row = await cursor.fetchone()
        
        if not row:
            # Return a skeleton indicating it is generating or missing
            return {
                "date": today,
                "status": "generating",
                "overview": { "title": "Overview", "items": [{"content": "Your briefing is currently being generated..."}] },
                "current_state": { "title": "Current State", "items": [] },
                "needs_attention": { "title": "Needs Attention", "items": [] },
                "suggested_plan": { "title": "Suggested Plan", "items": [] },
                "open_loops": { "title": "Open Loops", "items": [] },
                "insight": { "title": "Insight", "items": [] },
                "upcoming": { "title": "Upcoming", "items": [] }
            }
            
        briefing = json.loads(row['content_json'])
        briefing['date'] = today
        briefing['status'] = 'ready'
        briefing['last_updated'] = row['last_updated']
        
        # Ensure all standard sections exist just in case the LLM dropped one
        for section in ["overview", "current_state", "needs_attention", "suggested_plan", "open_loops", "insight"]:
            if section not in briefing:
                briefing[section] = { "title": section.replace('_', ' ').title(), "items": [] }
            else:
                # Normalize items: if the LLM output an array of strings instead of objects, fix it
                items = briefing[section].get("items", [])
                normalized_items = []
                for item in items:
                    if isinstance(item, str):
                        normalized_items.append({"content": item})
                    elif isinstance(item, dict):
                        normalized_items.append(item)
                briefing[section]["items"] = normalized_items
                
        # Dynamically inject upcoming events from the calendar
        briefing['upcoming'] = { "title": "Upcoming", "items": [] }
        try:
            events = calendar_service.get_upcoming_events(max_results=5)
            for e in events:
                start_raw = e['start'].get('dateTime', e['start'].get('date'))
                summary = e.get('summary', 'No Title')
                
                # Format date nicely
                try:
                    # Parse ISO format (handling Z or timezone offsets)
                    dt = datetime.datetime.fromisoformat(start_raw.replace('Z', '+00:00'))
                    
                    # Add ordinal suffix to day
                    day = dt.day
                    suffix = 'th' if 11 <= day <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
                    
                    if 'T' in start_raw: # Has time
                        formatted = f"{dt.strftime('%B')} {day}{suffix} at {dt.strftime('%I:%M %p').lstrip('0')}"
                    else: # Date only
                        formatted = f"{dt.strftime('%B')} {day}{suffix}"
                except ValueError:
                    formatted = start_raw
                    
                briefing['upcoming']['items'].append({
                    "content": f"{formatted}: {summary}"
                })
        except Exception as e:
            briefing['upcoming']['items'].append({"content": "Could not fetch calendar events."})
            
        # Dynamically inject high-priority active tasks into needs_attention
        try:
            t_cursor = await db.execute("SELECT description FROM tasks WHERE status != 'done' AND status != 'deleted' AND priority = 'high' LIMIT 5")
            high_tasks = await t_cursor.fetchall()
            for t in high_tasks:
                briefing['needs_attention']['items'].append({
                    "content": f"[Active Task] {t['description']}"
                })
        except Exception:
            pass
            
        return briefing

@router.post("/generate")
async def force_generate_briefing():
    """Forces regeneration of today's briefing."""
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    async with get_db() as db:
        await db.execute("DELETE FROM daily_briefings WHERE date = ?", (today,))
        await db.commit()
        
        from autonomous.tasks import generate_daily_briefing
        await generate_daily_briefing(db)
        
    return {"status": "regenerated"}

from pydantic import BaseModel
from typing import Optional

class UpdateBriefingItemRequest(BaseModel):
    date: str
    section_key: str
    item_index: int
    action: str
    new_content: Optional[str] = None

@router.post("/update_item")
async def update_briefing_item(request: UpdateBriefingItemRequest):
    async with get_db() as db:
        cursor = await db.execute("SELECT content_json FROM daily_briefings WHERE date = ?", (request.date,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Briefing not found")
            
        data = json.loads(row["content_json"])
        if request.section_key not in data:
            raise HTTPException(status_code=400, detail="Invalid section key")
            
        section = data[request.section_key]
        if "items" not in section or request.item_index < 0 or request.item_index >= len(section["items"]):
            raise HTTPException(status_code=400, detail="Invalid item index")
            
        if request.action == "DELETE":
            section["items"].pop(request.item_index)
        elif request.action == "EDIT" and request.new_content is not None:
            item = section["items"][request.item_index]
            if isinstance(item, str):
                section["items"][request.item_index] = {"content": request.new_content}
            else:
                section["items"][request.item_index]["content"] = request.new_content
            
        # Save back
        await db.execute("UPDATE daily_briefings SET content_json = ?, last_updated = CURRENT_TIMESTAMP WHERE date = ?", 
                         (json.dumps(data), request.date))
        await db.commit()
        return {"status": "success"}
