import os
import json
import uuid
import datetime
import asyncio
import numpy as np
import ollama
import calendar_service
from aiosqlite import Connection
from .prompts import get_extraction_prompt
from .embeddings import generate_embedding
from .validator import Validator, resolve_canonical_entity
from scoring.engine import update_object_scores

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EXTRACTION_MODEL = os.getenv("EXTRACTION_MODEL", "qwen3:8b")

client = ollama.AsyncClient(host=OLLAMA_BASE_URL)

async def resolve_task(db, description: str, include_completed: bool = False) -> str | None:
    """Uses LLM to find the closest matching open task by description."""
    if include_completed:
        cursor = await db.execute("SELECT id, description FROM tasks")
    else:
        cursor = await db.execute("SELECT id, description FROM tasks WHERE status != 'done'")
    tasks = await cursor.fetchall()
    if not tasks: return None
    
    prompt = "Given the following list of tasks:\n"
    for t in tasks:
        prompt += f"ID: {t['id']} | Desc: {t['description']}\n"
    prompt += f"\nWhich task ID best matches this description: '{description}'? Respond ONLY with the exact task ID, or 'NONE' if no task matches."
    
    response = await client.chat(
        model=EXTRACTION_MODEL, 
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.0}
    )
    result = response.get('message', {}).get('content', '').strip()
    
    # Clean up result (sometimes LLMs add quotes or periods)
    result = result.replace('"', '').replace("'", "").strip('.')
    
    if result and result != "NONE" and any(t['id'] == result for t in tasks):
        return result
    return None

async def process_entry(entry_id: str, content: str, context_project_id: str | None = None):
    """
    The main extraction pipeline.
    1. Generates and stores the embedding for semantic search.
    2. Runs LLM extraction to get structured JSON.
    3. Validates and resolves entities/relationships via Validator.
    4. Saves to DB.
    """
    from database import get_db
    try:
        # 1. Generate and store embedding (outside main DB lock)
        embedding_vector = await generate_embedding(content)
        if embedding_vector:
            embedding_bytes = np.array(embedding_vector, dtype=np.float32).tobytes()
            async with get_db() as db:
                await db.execute(
                    "UPDATE entries SET embedding = ? WHERE id = ?",
                    (embedding_bytes, entry_id)
                )
                await db.commit()
                
        # 2. Extract structured data using LLM (takes 10-20 seconds, DO NOT hold DB lock)
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        prompt = get_extraction_prompt(current_date)
        
        response = await client.chat(
            model=EXTRACTION_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": content}
            ],
            options={
                "temperature": 0.0,
                "num_ctx": 4096
            }
        )
        
        result_text = response.get('message', {}).get('content', '{}')
        print("LLM OUTPUT:", result_text)
        try:
            # LLM can sometimes return invalid JSON if the prompt isn't strictly followed
            json.loads(result_text)
        except json.JSONDecodeError:
            print(f"Failed to decode JSON from LLM: {result_text}")
            async with get_db() as db:
                await db.execute("UPDATE entries SET extraction_status = 'failed' WHERE id = ?", (entry_id,))
                await db.commit()
            return
            
        async with get_db() as db:
            # 3. Route through Validator
            validator = Validator(db, entry_id)
            cleaned_data = await validator.validate_and_resolve(result_text)
            
            # 4. Save to DB
            name_to_id = cleaned_data.get("name_to_id", {})
            
            # Link Entities to the Entry
            if context_project_id:
                await db.execute(
                    "INSERT OR IGNORE INTO entry_entities (entry_id, entity_id, relationship) VALUES (?, ?, ?)",
                    (entry_id, context_project_id, 'mentions')
                )

            for ent in cleaned_data.get('entities', []):
                eid = ent.get('id')
                if eid:
                    await db.execute(
                        "INSERT OR IGNORE INTO entry_entities (entry_id, entity_id, relationship) VALUES (?, ?, ?)",
                        (entry_id, eid, 'mentions')
                    )
                    
            # Process Tasks
            for task in cleaned_data.get('tasks', []):
                desc = task.get('description')
                if not desc: continue
                
                assignee_name = task.get('assignee_name')
                project_name = task.get('project_name')
                due_date = task.get('due_date')
                conf = task.get('confidence', 1.0)
                if conf is None: conf = 1.0
                
                assignee_id = name_to_id.get(assignee_name) if assignee_name else None
                if not assignee_id and assignee_name:
                    assignee_id = await resolve_canonical_entity(db, {"name": assignee_name, "type": "Person"}, entry_id)
                    
                if context_project_id:
                    project_id = context_project_id
                else:
                    project_id = name_to_id.get(project_name) if project_name else None
                    if not project_id and project_name:
                        project_id = await resolve_canonical_entity(db, {"name": project_name, "type": "Project"}, entry_id)
                
                if assignee_id:
                    await db.execute(
                        "INSERT OR IGNORE INTO entry_entities (entry_id, entity_id, relationship) VALUES (?, ?, ?)",
                        (entry_id, assignee_id, 'mentions')
                    )
                if project_id:
                    await db.execute(
                        "INSERT OR IGNORE INTO entry_entities (entry_id, entity_id, relationship) VALUES (?, ?, ?)",
                        (entry_id, project_id, 'mentions')
                    )
                
                f_conf = float(conf)
                status = 'open' if f_conf >= 0.8 else 'suggested'
                
                google_task_id = None
                if status == 'open':
                    google_task_id = await asyncio.to_thread(calendar_service.create_google_task, desc, due_date if due_date else None)

                task_id = str(uuid.uuid4())
                sync_status = 'synced' if google_task_id else 'pending_create'
                await db.execute(
                    """INSERT INTO tasks (id, description, status, assignee_id, project_id, due_date, source_entry_id, confidence, google_task_id, sync_status) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (task_id, desc, status, assignee_id, project_id, due_date, entry_id, f_conf, google_task_id, sync_status)
                )
                
                rel_est = task.get("relevance_estimate")
                sig_est = task.get("significance_estimate")
                if rel_est is not None or sig_est is not None:
                    await update_object_scores(db, task_id, "tasks", baseline_rel=rel_est, baseline_sig=sig_est)

                
            # Process Ideas
            for idea in cleaned_data.get('ideas', []):
                description = idea.get('description')
                if not description: continue
                
                project_name = idea.get('project_name')
                conf = idea.get('confidence', 1.0)
                if conf is None: conf = 1.0
                
                if context_project_id:
                    project_id = context_project_id
                else:
                    project_id = name_to_id.get(project_name) if project_name else None
                    if not project_id and project_name:
                        project_id = await resolve_canonical_entity(db, {"name": project_name, "type": "Project"}, entry_id)
                
                if project_id:
                    await db.execute(
                        "INSERT OR IGNORE INTO entry_entities (entry_id, entity_id, relationship) VALUES (?, ?, ?)",
                        (entry_id, project_id, 'mentions')
                    )

                idea_id = str(uuid.uuid4())
                await db.execute(
                    """INSERT INTO ideas (id, description, project_id, source_entry_id, confidence)
                       VALUES (?, ?, ?, ?, ?)""",
                    (idea_id, description, project_id, entry_id, float(conf))
                )
                
                rel_est = idea.get("relevance_estimate")
                sig_est = idea.get("significance_estimate")
                if rel_est is not None or sig_est is not None:
                    await update_object_scores(db, idea_id, "ideas", baseline_rel=rel_est, baseline_sig=sig_est)

                
            # Process Task Updates
            for t_update in cleaned_data.get('task_updates', []):
                semantic_desc = t_update.get('semantic_description')
                action = t_update.get('action')
                if not semantic_desc or action not in ['mark_done', 'delete']: continue
                
                matched_task_id = await resolve_task(db, semantic_desc, include_completed=(action == 'delete'))
                if matched_task_id:
                    await db.execute(
                        """INSERT INTO pending_task_updates (id, task_id, action, source_entry_id)
                           VALUES (?, ?, ?, ?)""",
                        (str(uuid.uuid4()), matched_task_id, action, entry_id)
                    )
            # Process Decisions
            for decision in cleaned_data.get('decisions', []):
                title = decision.get('title')
                if not title: continue
                
                status = decision.get('status', 'Active')
                supersedes = decision.get('supersedes')
                reason = decision.get('reason')
                evidence = decision.get('evidence')
                project_name = decision.get('project_name')
                
                project_id = None
                if context_project_id:
                    project_id = context_project_id
                else:
                    project_id = name_to_id.get(project_name) if project_name else None
                    if not project_id and project_name:
                        project_id = await resolve_canonical_entity(db, {"name": project_name, "type": "Project"}, entry_id)
                
                if project_id:
                    await db.execute(
                        "INSERT OR IGNORE INTO entry_entities (entry_id, entity_id, relationship) VALUES (?, ?, ?)",
                        (entry_id, project_id, 'mentions')
                    )

                decision_id = str(uuid.uuid4())
                await db.execute(
                    """INSERT INTO decisions (id, title, status, supersedes, reason, evidence, project_id, source_entry_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (decision_id, title, status, supersedes, reason, evidence, project_id, entry_id)
                )
                
                rel_est = decision.get("relevance_estimate")
                sig_est = decision.get("significance_estimate")
                if rel_est is not None or sig_est is not None:
                    await update_object_scores(db, decision_id, "decisions", baseline_rel=rel_est, baseline_sig=sig_est)

            # Process Relationships
            for rel in cleaned_data.get('relationships', []):
                src_name = rel.get('source_entity')
                src_type = rel.get('source_type', 'Topic')
                tgt_name = rel.get('target_entity')
                tgt_type = rel.get('target_type', 'Topic')
                rel_type = rel.get('relationship_type')
                conf = rel.get('confidence', 1.0)
                if conf is None: conf = 1.0
                
                if not src_name or not tgt_name or not rel_type: continue
                
                src_id = name_to_id.get(src_name)
                if not src_id:
                    src_id = await resolve_canonical_entity(db, {"name": src_name, "type": src_type}, entry_id)
                    
                tgt_id = name_to_id.get(tgt_name)
                if not tgt_id:
                    tgt_id = await resolve_canonical_entity(db, {"name": tgt_name, "type": tgt_type}, entry_id)
                
                if src_id and tgt_id and src_id != tgt_id:
                    await db.execute(
                        """INSERT OR IGNORE INTO entity_relations (id, from_entity_id, to_entity_id, relationship, source_entry_id, confidence)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (str(uuid.uuid4()), src_id, tgt_id, rel_type, entry_id, float(conf))
                    )

            # Mark as done
            await db.execute("UPDATE entries SET extraction_status = 'done' WHERE id = ?", (entry_id,))
            
            # Compute score for the entry itself (using heuristics since LLM didn't estimate it directly)
            await update_object_scores(db, entry_id, "entries")
            
            await db.commit()
            
    except Exception as e:
        print(f"Error in extraction pipeline for entry {entry_id}: {e}")
        # Need a new connection for the error fallback since the `with get_db()` context might be broken or closed
        from database import get_db
        async with get_db() as error_db:
            await error_db.execute("UPDATE entries SET extraction_status = 'failed' WHERE id = ?", (entry_id,))
            await error_db.commit()
