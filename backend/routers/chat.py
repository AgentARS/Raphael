import json
import datetime
import asyncio
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import ollama

from database import get_db
from extraction.embeddings import generate_embedding, OLLAMA_BASE_URL
from extraction.pipeline import EXTRACTION_MODEL
from scoring.engine import fetch_scores
import calendar_service

router = APIRouter(prefix="/api/chat", tags=["chat"])

client = ollama.AsyncClient(host=OLLAMA_BASE_URL)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    stream: bool = True

def cosine_similarity(v1, v2):
    dot_product = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0
    return float(dot_product / (norm1 * norm2))

async def search_context(query: str, db, limit: int = 5) -> str:
    """Retrieve relevant entries using both vector search and FTS."""
    query_emb = await generate_embedding(query)
    
    # 1. Vector Search
    vector_results = []
    if query_emb:
        q_vec = np.array(query_emb, dtype=np.float32)
        cursor = await db.execute("SELECT id, content, created_at, embedding FROM entries WHERE embedding IS NOT NULL")
        rows = await cursor.fetchall()
        for row in rows:
            entry_vec = np.frombuffer(row["embedding"], dtype=np.float32)
            score = cosine_similarity(q_vec, entry_vec)
            vector_results.append({
                "id": row["id"],
                "content": row["content"],
                "created_at": row["created_at"],
                "score": score
            })
        
        # Sort by score descending and take top N
        vector_results.sort(key=lambda x: x["score"], reverse=True)
        vector_results = vector_results[:limit]
        
    # 2. FTS Search
    fts_results = []
    # Clean query for FTS (basic: just use words)
    words = [w for w in query.split() if w.isalnum()]
    if words:
        fts_query = " OR ".join(words)
        try:
            cursor = await db.execute(
                """
                SELECT e.id, e.content, e.created_at
                FROM entries_fts fts
                JOIN entries e ON fts.rowid = e.rowid
                WHERE entries_fts MATCH ?
                LIMIT ?
                """, (fts_query, limit)
            )
            rows = await cursor.fetchall()
            for row in rows:
                fts_results.append({
                    "id": row["id"],
                    "content": row["content"],
                    "created_at": row["created_at"],
                    "score": 1.0 # arbitrary high score for FTS
                })
        except Exception as e:
            print(f"FTS Search error: {e}")

    # Combine and deduplicate
    combined = {r["id"]: r for r in vector_results + fts_results}
    
    # Sort combined by date or score (we'll just use the raw list)
    final_list = list(combined.values())
    
    if not final_list:
        return "No relevant notes found in the database."
        
    # Fetch Knowledge Scores and Re-rank
    scores_map = await fetch_scores(db, [item["id"] for item in final_list])
    
    for item in final_list:
        score_data = scores_map.get(item["id"], {"relevance": 50.0, "significance": 50.0})
        item["relevance"] = score_data.get("relevance", 50.0)
        item["significance"] = score_data.get("significance", 50.0)
        # Rerank formula: original score + relevance weighting
        item["score"] = item["score"] + (item["relevance"] / 100 * 2)

    # Re-sort after applying relevance
    final_list.sort(key=lambda x: x["score"], reverse=True)
        
    context_str = "Relevant context from user's notes:\n\n"
    for item in final_list[:limit * 2]:
        rel = round(item["relevance"])
        sig = round(item["significance"])
        context_str += f"[{item['created_at']}] (Rel: {rel}, Sig: {sig}) {item['content']}\n---\n"
        
    return context_str

@router.post("")
async def chat_endpoint(request: ChatRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="Messages list cannot be empty")
        
    # The last message is the current user query
    user_query = request.messages[-1].content
    
    async with get_db() as db:
        context = await search_context(user_query, db)
        
    # Get upcoming calendar events
    try:
        events = await asyncio.to_thread(calendar_service.get_upcoming_events, 15)
        schedule_context = "Upcoming Calendar Schedule:\n"
        if not events:
            schedule_context += "Your schedule is completely clear for the next two weeks.\n"
        for e in events:
            start = e['start'].get('dateTime', e['start'].get('date'))
            end = e['end'].get('dateTime', e['end'].get('date'))
            summary = e.get('summary', 'Untitled Event')
            event_id = e['id']
            schedule_context += f"- [ID: {event_id}] {summary} (from {start} to {end})\n"
    except Exception as e:
        schedule_context = f"Note: Calendar could not be fetched ({str(e)})."
        
    # Build system prompt
    system_prompt = f"""You are Raphael, an AI personal knowledge assistant and secretary.
You help the user recall information, synthesize their notes, and execute actions.
Use the provided context to answer the user's latest message.
If the context doesn't contain the answer, acknowledge that you don't know based on their notes, but you can provide general knowledge if appropriate.
Keep your answers concise, Markdown-formatted, and helpful.
When referencing dates in natural language, format them in a readable, compressed format like "July 10" or "Aug 5" instead of "YYYY-MM-DD".
IMPORTANT: Understand that second-person pronouns (e.g., "you", "your", "yourself") used by the user typically refer to YOU (Raphael), unless the context clearly indicates otherwise. When the user says "I built you to...", they mean they built YOU, Raphael.

SECRETARY MODE:
You are fully authorized and capable of managing the user's Google Calendar, tasks, and notes through the provided JSON commands. NEVER claim that you cannot access external applications or lack permissions.
If the user explicitly asks you to create, update, or delete a task, project, note, or calendar event, you must BOTH:
1. Confirm to the user in natural language that you will execute their request.
2. Append a JSON block at the VERY END of your response with the exact commands to execute.

FORMAT FOR COMMANDS (must be at the very end):
Notes on Calendar:
- `recurrence` should be a list of RRULE strings, e.g. `["RRULE:FREQ=WEEKLY;COUNT=5"]`.
- `color_id` maps to colors: 1=Lavender, 2=Sage, 3=Grape, 4=Flamingo, 5=Banana, 6=Tangerine, 7=Peacock, 8=Graphite, 9=Blueberry, 10=Basil, 11=Tomato.
- IMPORTANT: You MUST use the exact `ID` provided in the SCHEDULE context. DO NOT make up event IDs (like "all"). If an event is not in the SCHEDULE context, tell the user you cannot see it.

```json
{{
  "commands": [
    {{ "type": "create_task", "description": "Task description" }},
    {{ "type": "create_project", "name": "Project Name" }},
    {{ "type": "create_note", "content": "Note content" }},
    {{ "type": "create_calendar_event", "summary": "Meeting Name", "description": "Optional details", "start_time": "2026-07-11T14:00:00", "end_time": "2026-07-11T15:00:00", "recurrence": ["RRULE:FREQ=WEEKLY;COUNT=10"], "color_id": "11" }},
    {{ "type": "update_calendar_event", "id": "event_id", "summary": "New Meeting Name", "start_time": "2026-07-11T15:00:00", "end_time": "2026-07-11T16:00:00", "recurrence": ["RRULE:FREQ=DAILY"], "color_id": "5" }},
    {{ "type": "delete_calendar_event", "id": "event_id" }},
    {{ "type": "task_update", "semantic_description": "Description of the task to update", "action": "mark_done" }},
    {{ "type": "task_update", "semantic_description": "Description of the task to update", "action": "delete" }}
  ]
}}
```

Current Date/Time: {datetime.datetime.now().isoformat()}

SCHEDULE:
{schedule_context}

CONTEXT:
{context}
"""
    
    # Prepare messages for Ollama
    ollama_messages = [{"role": "system", "content": system_prompt}]
    for msg in request.messages:
        ollama_messages.append({"role": msg.role, "content": msg.content})
        
    if request.stream:
        async def generate():
            try:
                # Use async client for streaming
                async for chunk in await client.chat(model=EXTRACTION_MODEL, messages=ollama_messages, stream=True):
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
            except Exception as e:
                yield f"\n\nError connecting to LLM: {str(e)}"
                
        return StreamingResponse(generate(), media_type="text/plain")
    else:
        response = await client.chat(model=EXTRACTION_MODEL, messages=ollama_messages, stream=False)
        return {"role": "assistant", "content": response.get("message", {}).get("content", "")}
