import os
import json
import uuid
import re
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from llm_manager import generate_chat, SystemMemoryOverloadError

from database import get_db

router = APIRouter(prefix="/api/discussions", tags=["discussions"])

class Message(BaseModel):
    role: str
    content: str

class DiscussionContext(BaseModel):
    object_type: str
    section: Optional[str] = None
    content: str
    evidence: Optional[List[Dict[str, Any]]] = None

class ChatRequest(BaseModel):
    context: DiscussionContext
    messages: List[Message]

class FinishResponse(BaseModel):
    summary: str
    proposal_text: str
    briefing_action: str
    new_content: Optional[str] = None

@router.post("/chat")
async def chat_discussion(request: ChatRequest):
    from llm_manager import LIGHT_MODEL
    model = LIGHT_MODEL
    
    # Build system prompt
    sys_prompt = f"""You are Raphael, an AI assistant collaboratively refining your own knowledge with the user.
The user is discussing a specific piece of knowledge you generated.
OBJECT TYPE: {request.context.object_type}
SECTION: {request.context.section or 'N/A'}
CURRENT TEXT: {request.context.content}
EVIDENCE: {json.dumps(request.context.evidence) if request.context.evidence else 'None'}

Goal: Be conversational. If the user corrects a fact, ask clarifying questions if needed, or acknowledge the correction. Discuss implications for their tasks or projects. Do not output JSON. Just chat naturally."""

    messages = [{"role": "system", "content": sys_prompt}]
    for msg in request.messages:
        messages.append({"role": msg.role, "content": msg.content})
        
    try:
        response = await generate_chat(model=model, messages=messages, stream=False, options={"num_ctx": 8192})
        return {"reply": response['message']['content']}
    except SystemMemoryOverloadError:
        raise HTTPException(status_code=503, detail="System Memory Overloaded. AI paused.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/finish", response_model=FinishResponse)
async def finish_discussion(request: ChatRequest):
    from llm_manager import LIGHT_MODEL
    model = LIGHT_MODEL
    
    sys_prompt = f"""You are Raphael. The user has finished discussing a knowledge item with you.
OBJECT TYPE: {request.context.object_type}
SECTION: {request.context.section or 'N/A'}
CURRENT TEXT: {request.context.content}
EVIDENCE: {json.dumps(request.context.evidence) if request.context.evidence else 'None'}

You must evaluate the discussion and output a strict JSON decision.
The JSON must have this exact structure:
{{
  "summary": "A highly concise bulleted summary of the knowledge changes or new facts learned from the discussion. Do not mention UI elements.",
  "proposal_text": "A user-facing text starting with 'I will:' explaining what changes will be made, followed by 'Reason:'.",
  "briefing_action": "KEEP, EDIT, or DELETE",
  "new_content": "If action is EDIT, provide the revised text for the item here. Otherwise null."
}}"""

    messages = [{"role": "system", "content": sys_prompt}]
    for msg in request.messages:
        messages.append({"role": msg.role, "content": msg.content})
        
    # Append final instruction
    messages.append({"role": "user", "content": "The discussion is finished. Please output the required JSON decision."})
    
    try:
        response = await generate_chat(model=model, messages=messages, format="json", stream=False, options={"num_ctx": 8192})
        raw_content = response['message']['content'].strip()
        
        # Robust JSON extraction
        import re
        json_match = re.search(r'\{.*\}', raw_content, re.DOTALL)
        if json_match:
            raw_content = json_match.group(0)
        
        try:
            result = json.loads(raw_content)
        except json.JSONDecodeError:
            print(f"Failed to parse JSON from Ollama: {raw_content}")
            result = {
                "summary": "Could not parse summary.",
                "proposal_text": "Failed to generate a valid proposal.",
                "briefing_action": "KEEP",
                "new_content": None
            }
        
        # Save summary to DB as a new Entry
        summary = result.get("summary", "")
        if summary:
            entry_id = f"ent_{uuid.uuid4().hex[:12]}"
            async with get_db() as db:
                await db.execute(
                    "INSERT INTO entries (id, content, source_type) VALUES (?, ?, ?)",
                    (entry_id, f"Discussion Summary:\n{summary}", "briefing_discussion")
                )
                await db.commit()
                
        return FinishResponse(
            summary=summary,
            proposal_text=result.get("proposal_text", "No changes proposed."),
            briefing_action=result.get("briefing_action", "KEEP"),
            new_content=result.get("new_content")
        )
    except SystemMemoryOverloadError:
        raise HTTPException(status_code=503, detail="System Memory Overloaded. AI paused.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
