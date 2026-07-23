from fastapi import APIRouter, HTTPException
from models import CalendarEventResponse
from pydantic import BaseModel
import calendar_service

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

class CreateEventRequest(BaseModel):
    summary: str
    description: str = ""
    start_time: str
    end_time: str
    recurrence: list[str] | None = None
    color_id: str | None = None

class UpdateEventRequest(BaseModel):
    summary: str | None = None
    description: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    recurrence: list[str] | None = None
    color_id: str | None = None

@router.get("/events", response_model=list[CalendarEventResponse])
async def list_events(max_results: int = 10):
    try:
        events = calendar_service.get_upcoming_events(max_results=max_results)
        
        parsed_events = []
        for e in events:
            # Handle whole-day vs timed events
            start = e['start'].get('dateTime', e['start'].get('date'))
            end = e['end'].get('dateTime', e['end'].get('date'))
            
            parsed_events.append(CalendarEventResponse(
                id=e['id'],
                summary=e.get('summary', 'No Title'),
                description=e.get('description'),
                start_time=start,
                end_time=end,
                html_link=e.get('htmlLink', '')
            ))
            
        return parsed_events
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/events", response_model=CalendarEventResponse)
async def create_event(req: CreateEventRequest):
    try:
        e = calendar_service.create_event(
            summary=req.summary,
            description=req.description,
            start_time=req.start_time,
            end_time=req.end_time,
            recurrence=req.recurrence,
            color_id=req.color_id
        )
        
        start = e['start'].get('dateTime', e['start'].get('date'))
        end = e['end'].get('dateTime', e['end'].get('date'))
        
        return CalendarEventResponse(
            id=e['id'],
            summary=e.get('summary', 'No Title'),
            description=e.get('description'),
            start_time=start,
            end_time=end,
            html_link=e.get('htmlLink', '')
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/events/{event_id}", response_model=CalendarEventResponse)
async def update_event(event_id: str, req: UpdateEventRequest):
    try:
        e = calendar_service.update_event(
            event_id=event_id,
            summary=req.summary,
            description=req.description,
            start_time=req.start_time,
            end_time=req.end_time,
            recurrence=req.recurrence,
            color_id=req.color_id
        )
        
        start = e['start'].get('dateTime', e['start'].get('date'))
        end = e['end'].get('dateTime', e['end'].get('date'))
        
        return CalendarEventResponse(
            id=e['id'],
            summary=e.get('summary', 'No Title'),
            description=e.get('description'),
            start_time=start,
            end_time=end,
            html_link=e.get('htmlLink', '')
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/events/{event_id}")
async def delete_event(event_id: str):
    try:
        calendar_service.delete_event(event_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
