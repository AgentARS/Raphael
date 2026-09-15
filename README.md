# Raphael

Raphael is a premium, AI-driven personal knowledge management (PKM) assistant. It automatically transforms unstructured, natural-language notes into a highly structured knowledge database consisting of Tasks, Ideas, Calendar events, and a dynamic Semantic Knowledge Graph.

---

## Architecture Overview

Raphael is built on a **Hybrid Relational-Graph Architecture**, separating concerns into a deterministic relational source of truth and a semantic graph overlay:
1. **SQLite (Source of Truth):** Relational tables manage structured data like Tasks, Projects, People, and Ideas. Foreign keys represent deterministic, one-to-many relationships (e.g., a Task belongs to a Project).
2. **Knowledge Graph (Semantic Overlay):** The `entity_relations` table tracks semantic, inferred, and many-to-many relationships (e.g., "Rahul discussed PostgreSQL").
3. **Graph Generation:** The backend merges both database-relational links and explicit semantic links into a unified node-edge network dynamically queried by the frontend graph.

---

## Technical Stack

- **Backend:** FastAPI (Python)
- **Frontend:** React (Vite + TypeScript)
- **Database:** SQLite (with `aiosqlite` for async execution, WAL mode, and FTS5 for full-text search)
- **AI Interface:** Ollama running `qwen3:8b` (Extraction/Chat) & `nomic-embed-text` (Embeddings)

---

## Backend System Design

### 1. Database Schema (`backend/database.py`)
- **`entries`**: Unstructured notes written by the user. Contains raw content and extraction status (`pending`, `done`, `failed`).
- **`entities`**: The nodes in the graph (types: `Person`, `Project`, `Topic`, `Organization`, `Tool`). Stores embeddings, aliases (JSON array), mention count, last seen timestamps, and confidence scores.
- **`tasks`**: Actionable tasks extracted from notes. Linked relationally to assignee and project entities.
- **`ideas`**: Non-obligatory ideas or future plans. Linked relationally to project entities.
- **`entity_relations`**: Represents explicit, typed semantic edges between two entities. Uses a strict ontology (e.g. Person: `discussed`, `created`, `mentioned`; Project: `contains`, `depends_on`, `completed`) with confidence metrics.
- **`entry_entities`**: Maps note entries to the entities mentioned within them.
- **`pending_task_updates`**: Review queue for task completions or deletions suggested by the AI.
- **`entries_fts`**: FTS5 virtual table for lightning-fast full-text search.

### 2. Async Extraction Pipeline (`backend/extraction/pipeline.py`)
When a note is created, the backend yields an immediate response to the frontend, marking the note as `pending` (yellow dot in UI). FastAPI pushes the extraction pipeline to a background worker to avoid blocking the event loop:
1. **Embedding Generation**: Text is converted to a vector embedding using `nomic-embed-text` and stored.
2. **LLM Extraction (Lock-Free)**: `qwen3:8b` processes the text using a strict JSON format defined in `extraction/prompts.py`. The pipeline explicitly **decouples the SQLite connection** during this 10-20 second LLM call, ensuring that the database remains completely unlocked and responsive to new notes being saved in the UI concurrently.
3. **Validator Filtering**: The raw JSON is processed by `extraction/validator.py`. It drops any extraction with confidence < 0.5 and filters out relationships that violate the hardcoded schema ontology.
4. **Entity Resolution (Canonicalization)**: Ensures names are grouped into single canonical records.

### 3. Five-Stage Entity Resolution (`backend/extraction/validator.py`)
To prevent duplicate entities (e.g., "Rahul", "Dr. Rahul Sharma", "Rahul S."), the Validator runs a robust 5-stage pipeline:
- **Stage 1 (Exact Match):** Checks exact name matches or matching values inside the existing `aliases` JSON list.
- **Stage 2 (Normalization):** Strips titles (Dr., Mr.), punctuation, and whitespaces, checking case-insensitive variations.
- **Stage 3 (Fuzzy Match):** Uses `rapidfuzz.fuzz.token_set_ratio` to check for > 95% similarity.
- **Stage 4 (Semantic Match):** Compares cosine similarities of name embeddings. If similarity > 0.95, they are merged.
- **Stage 5 (LLM Fallback):** If semantic similarity is ambiguous (0.85 to 0.95), the pipeline queries the LLM with surrounding context to ask if they represent the same person or concept.

Upon matching, the validator updates the existing entity's aliases list and increments its `mention_count`.

### 4. Search and RAG (`backend/routers/chat.py` & `search.py`)
- **Hybrid Search**: Combines full-text FTS5 matching with vector cosine similarity.
- **Retrieval-Augmented Generation (RAG)**: The `/api/chat` route performs embedding searches on note entries, pulls upcoming Google Calendar events, extracts current pending tasks, and feeds the merged context to the LLM to provide highly accurate, grounded answers.

### 5. Autonomous Execution System (`backend/autonomous/`)
- A background `asyncio` loop (`scheduler.py`) that performs routine maintenance when Raphael is in "Autonomous Mode".
- **Dynamic Load Monitoring**: Uses `psutil` to verify system CPU and RAM are below configured thresholds before running tasks to remain entirely unobtrusive.
- **Maintenance Checklist (`tasks.py`)**: Includes tasks like `refresh_relevance_scores`, `detect_open_loops`, and `merge_duplicate_entities`. Tasks declare `priority` and `max_runtime_ms` and are stored in SQLite to persist state across reboots.

### 6. Daily Executive Briefing (`backend/routers/briefing.py`)
- **Proactive Synthesis**: Instead of waiting for prompts, Raphael runs the `generate_daily_briefing` autonomous task on the first wake of a new day. It pulls active projects, open tasks, and recent notes, using Ollama to synthesize a 7-section structured JSON briefing.
- **Dynamic Hybrid Rendering**: To save expensive repeated LLM calls, the backend fetches this static JSON but dynamically injects live Calendar upcoming events and high-priority tasks into the response, ensuring the Briefing UI is always perfectly up to date.

---

## Directory Structure

```bash
raphael/
├── package.json
├── backend/
│   ├── main.py                  # API entry point
│   ├── database.py              # Schema definition & connections
│   ├── models.py                # Pydantic response/request schemas
│   ├── requirements.txt         # Python dependencies
│   ├── routers/                 # FastAPI routes (chat, search, tasks, entities...)
│   └── extraction/
│       ├── prompts.py           # LLM extraction system prompts
│       ├── validator.py         # 5-stage entity canonicalization & ontology schema
│       └── pipeline.py          # Background worker coordinating LLM and DB
└── frontend/
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── api/
        │   └── client.ts        # Typed frontend HTTP client
        ├── pages/
        │   ├── Dashboard.tsx    # Recent ideas, tasks, calendar agenda
        │   ├── Timeline.tsx     # Notebook stream view
        │   ├── Projects.tsx     # Project panel (contains tasks/ideas/notes)
        │   ├── Entities.tsx     # Visual force-directed knowledge graph
        │   ├── Chat.tsx         # RAG conversation UI
        │   └── Briefing.tsx     # Daily Executive Briefing dashboard
        └── components/          # Reusable Tailwind/CSS components
```

---

## Setup and Installation

### Backend Setup
1. Navigate to backend:
   ```bash
   cd backend
   ```
2. Create and activate venv:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure `.env`:
   ```ini
   DATABASE_PATH=data/raphael.db
   OLLAMA_BASE_URL=http://localhost:11434
   EXTRACTION_MODEL=qwen3:8b
   EMBEDDING_MODEL=nomic-embed-text
   ```
5. Run migrations (if starting fresh):
   ```bash
   python -c "import database, asyncio; asyncio.run(database.init_db())"
   ```
6. Start backend development server:
   ```bash
   uvicorn main:app --reload
   ```

### Frontend Setup
1. Navigate to frontend:
   ```bash
   cd frontend
   ```
2. Install npm dependencies:
   ```bash
   npm install
   ```
3. Run development build:
   ```bash
   npm run dev
   ```
