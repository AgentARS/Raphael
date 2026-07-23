"""
Pydantic models for Raphael API request/response schemas.
"""

from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel
# --- Score models ---
class KnowledgeScores(BaseModel):
    relevance: float = 50.0
    significance: float = 50.0
    trend: float = 0.0
    explanation: Optional[str] = None

# --- Experience models ---
class InteractionEventCreate(BaseModel):
    event_type: str
    object_type: Optional[str] = None
    object_id: Optional[str] = None
    session_id: str
    metadata: dict = {}
    duration_ms: Optional[int] = None
    source: str = "frontend"

# --- Entry models ---

class EntryCreate(BaseModel):
    content: str
    source_type: str = "manual"
    context_project_id: str | None = None


class EntryUpdate(BaseModel):
    content: Optional[str] = None


class EntryResponse(BaseModel):
    id: str
    content: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    source_type: str = "manual"
    extraction_status: str = "pending"
    entities: list['EntityResponse'] = []
    scores: Optional[KnowledgeScores] = None


# --- Entity models ---

class EntityCreate(BaseModel):
    name: str
    type: str = "project"

class EntityUpdate(BaseModel):
    name: str | None = None
    type: str | None = None

class EntityResponse(BaseModel):
    id: str
    type: str
    name: str
    aliases: list[str] = []
    metadata: dict = {}
    confidence: float = 1.0
    created_at: str
    updated_at: str | None = None
    scores: Optional[KnowledgeScores] = None


# --- Task & Decision models ---

class TaskCreate(BaseModel):
    description: str
    project_id: str | None = None
    due_date: str | None = None
    priority: str = "medium"

class TaskUpdate(BaseModel):
    description: Optional[str] = None
    due_date: Optional[date] = None
    project_id: Optional[str] = None

class SemanticTaskUpdate(BaseModel):
    semantic_description: str
    action: str

class PendingTaskUpdateResponse(BaseModel):
    id: str
    task_id: str
    task_description: str  # We need to know what task this is about
    action: str
    source_entry_id: Optional[str] = None
    created_at: str


class TaskResponse(BaseModel):
    id: str
    description: str
    status: str
    priority: str
    assignee_id: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    due_date: Optional[date] = None
    source_entry_id: Optional[str] = None
    confidence: float = 1.0
    created_at: datetime
    completed_at: Optional[datetime] = None
    scores: Optional[KnowledgeScores] = None

class IdeaCreate(BaseModel):
    description: str
    project_id: Optional[str] = None

class IdeaUpdate(BaseModel):
    description: Optional[str] = None
    project_id: Optional[str] = None

# --- Idea models ---

class IdeaResponse(BaseModel):
    id: str
    description: str
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    source_entry_id: Optional[str] = None
    confidence: float = 1.0
    created_at: datetime
    scores: Optional[KnowledgeScores] = None


# --- Search models ---

class SearchResult(BaseModel):
    entry: EntryResponse
    snippet: Optional[str] = None
    rank: Optional[float] = None

class EntityRelationResponse(BaseModel):
    id: str
    from_entity_id: str
    to_entity_id: str
    relationship: str
    confidence: float = 1.0
    source_entry_id: Optional[str] = None
    created_at: datetime

class DecisionResponse(BaseModel):
    id: str
    title: str
    status: str
    supersedes: str | None = None
    reason: str | None = None
    evidence: str | None = None
    project_id: str | None = None
    source_entry_id: str | None = None
    created_at: str
    scores: Optional[KnowledgeScores] = None

class EntityGraphResponse(BaseModel):
    entity: EntityResponse
    entries: list[EntryResponse]
    tasks: list[TaskResponse]
    ideas: list[IdeaResponse]
    decisions: list[DecisionResponse] = []
    relations: list[EntityRelationResponse]

class NetworkNode(BaseModel):
    id: str
    name: str
    type: str
    confidence: float = 1.0

class NetworkLink(BaseModel):
    source: str
    target: str
    label: str
    weight: int = 1
    confidence: float = 1.0

class NetworkResponse(BaseModel):
    nodes: list[NetworkNode]
    links: list[NetworkLink]

class CalendarEventResponse(BaseModel):
    id: str
    summary: str
    description: Optional[str] = None
    start_time: str
    end_time: str
    html_link: str
