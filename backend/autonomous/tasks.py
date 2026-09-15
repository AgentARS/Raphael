import asyncio
import datetime
import os
import json
from database import get_db
from scoring.engine import update_object_scores
from llm_manager import generate_chat, SystemMemoryOverloadError

async def refresh_relevance_scores(db, limit: int = 50):
    """Refreshes scores for objects that haven't been computed recently."""
    cursor = await db.execute(
        "SELECT object_id, object_type, relevance, significance FROM knowledge_scores ORDER BY last_computed_at ASC LIMIT ?", 
        (limit,)
    )
    rows = await cursor.fetchall()
    
    for row in rows:
        await update_object_scores(db, row['object_id'], row['object_type'], row['relevance'], row['significance'])
        await asyncio.sleep(0.01) # Yield to event loop

async def refresh_significance_scores(db):
    """Refreshes significance scores (can be bundled with relevance in our implementation)."""
    # Since update_object_scores updates both, we can just run a smaller batch prioritizing older ones differently,
    # or just use it as an alias for now.
    await refresh_relevance_scores(db, limit=20)

async def detect_stale_projects(db):
    """Generates an AI summary of a project's status if it hasn't been summarized in the last 1 day."""
    now = datetime.datetime.utcnow()
    cursor = await db.execute("SELECT id, name, metadata, updated_at FROM entities WHERE type = 'Project'")
    projects = await cursor.fetchall()
    
    if not projects:
        return
        
    from llm_manager import LIGHT_MODEL
    model = LIGHT_MODEL
    
    for project in projects:
        project_id = project['id']
        project_name = project['name']
        metadata = json.loads(project['metadata'] or '{}')
        
        # Check if we summarized it recently (within 1 day)
        last_summarized_str = metadata.get('last_summarized_at')
        if last_summarized_str:
            last_summarized = datetime.datetime.fromisoformat(last_summarized_str)
            if (now - last_summarized).total_seconds() < 86400: # 1 day in seconds
                continue
            
        # Fetch some context (open tasks)
        t_cursor = await db.execute("SELECT description FROM tasks WHERE project_id = ? AND status != 'done'", (project_id,))
        open_tasks = [t['description'] for t in await t_cursor.fetchall()]
        
        prompt = f"The project '{project_name}' needs a brief status review.\n"
        if open_tasks:
            prompt += f"It has these remaining open tasks: {', '.join(open_tasks)}\n"
        prompt += "Write a very brief 1-2 sentence summary of what this project is about and what is left to do so the user can quickly remember it."
        
        try:
            response = await generate_chat(model=model, messages=[
                {"role": "system", "content": "You are a helpful assistant summarizing a project. Be extremely concise. Max 2 sentences."},
                {"role": "user", "content": prompt}
            ])
            summary = response['message']['content'].strip()
        
            # Update the DB
            metadata['last_summarized_at'] = now.isoformat()
            metadata['stale_summary'] = summary
            
            await db.execute(
                "UPDATE entities SET metadata = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(metadata), project_id)
            )
            await db.commit()
            
            # Also log it
            event_id = "proj_sum_" + datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + project_id[:8]
            await db.execute(
                "INSERT OR IGNORE INTO interaction_events (id, event_type, metadata) VALUES (?, ?, ?)",
                (event_id, 'autonomous_project_summary', json.dumps({"project_id": project_id, "project_name": project_name, "summary": summary}))
            )
            await db.commit()
            
        except Exception as e:
            print(f"Failed to summarize project: {e}")
            
        await asyncio.sleep(1) # Be nice to the LLM and event loop

async def detect_open_loops(db):
    """Finds open tasks that haven't been touched in a long time."""
    # We can just lower their priority or add a tag to their description if we wanted, 
    # but for now we'll just log an interaction event so the user sees it in their timeline.
    cursor = await db.execute("SELECT id, description FROM tasks WHERE status != 'done' AND status != 'deleted' AND created_at < datetime('now', '-30 days') AND sync_status != 'pending_delete'")
    tasks = await cursor.fetchall()
    
    # We'll just generate an event if we find any.
    if tasks:
        event_id = "loop_" + datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        metadata = '{"open_loops_count": ' + str(len(tasks)) + '}'
        await db.execute(
            "INSERT OR IGNORE INTO interaction_events (id, event_type, metadata) VALUES (?, ?, ?)",
            (event_id, 'autonomous_open_loops_detected', metadata)
        )
        await db.commit()

async def merge_duplicate_entities(db):
    """Merges entities that have the exact same name and type."""
    cursor = await db.execute("""
        SELECT type, name, COUNT(*) as c, MIN(id) as keep_id 
        FROM entities 
        GROUP BY type, name COLLATE NOCASE 
        HAVING c > 1
    """)
    duplicates = await cursor.fetchall()
    
    for dup in duplicates:
        keep_id = dup['keep_id']
        name = dup['name']
        type_ = dup['type']
        
        # Find the ones to merge
        cursor2 = await db.execute("SELECT id FROM entities WHERE type = ? AND name COLLATE NOCASE = ? AND id != ?", (type_, name, keep_id))
        merge_rows = await cursor2.fetchall()
        
        for m in merge_rows:
            old_id = m['id']
            # Re-route relations
            await db.execute("UPDATE OR IGNORE entity_relations SET from_entity_id = ? WHERE from_entity_id = ?", (keep_id, old_id))
            await db.execute("UPDATE OR IGNORE entity_relations SET to_entity_id = ? WHERE to_entity_id = ?", (keep_id, old_id))
            await db.execute("DELETE FROM entity_relations WHERE from_entity_id = ? OR to_entity_id = ?", (old_id, old_id))
            
            # Re-route entries
            await db.execute("UPDATE OR IGNORE entry_entities SET entity_id = ? WHERE entity_id = ?", (keep_id, old_id))
            await db.execute("DELETE FROM entry_entities WHERE entity_id = ?", (old_id,))
            
            # Re-route tasks/ideas
            await db.execute("UPDATE tasks SET project_id = ? WHERE project_id = ?", (keep_id, old_id))
            await db.execute("UPDATE tasks SET assignee_id = ? WHERE assignee_id = ?", (keep_id, old_id))
            await db.execute("UPDATE ideas SET project_id = ? WHERE project_id = ?", (keep_id, old_id))
            
            # Delete old entity
            await db.execute("DELETE FROM entities WHERE id = ?", (old_id,))
            
    await db.commit()

async def validate_graph_consistency(db):
    """Validates graph consistency by removing dangling edges."""
    await db.execute("""
        DELETE FROM entity_relations 
        WHERE from_entity_id NOT IN (SELECT id FROM entities) 
           OR to_entity_id NOT IN (SELECT id FROM entities)
    """)
    await db.commit()

async def remove_invalid_relationships(db):
    """Removes invalid relationships like self-loops."""
    await db.execute("DELETE FROM entity_relations WHERE from_entity_id = to_entity_id")
    await db.commit()

async def refresh_cached_dashboard(db):
    """Stub for refreshing dashboard cache."""
    await asyncio.sleep(0.1)

async def _build_recommendation_candidates(db):
    """Scans the database to generate deterministic structured evidence for recommendations."""
    candidates = {}
    
    # 1. Scan Tasks
    cursor = await db.execute("SELECT id, description, priority, due_date FROM tasks WHERE status != 'done' AND status != 'deleted'")
    tasks = await cursor.fetchall()
    
    today_date = datetime.date.today()
    
    for t in tasks:
        task_id = t["id"]
        evidence_list = []
        total_score = 0.0
        
        if t["priority"] == "high":
            evidence_list.append({
                "type": "high_priority", 
                "object_type": "task", 
                "object_id": task_id, 
                "score": 0.7, 
                "reason": "Task is marked as high priority"
            })
            total_score += 0.7
            
        if t["due_date"]:
            try:
                due = datetime.date.fromisoformat(t["due_date"][:10])
                delta = (due - today_date).days
                if delta < 0:
                    evidence_list.append({
                        "type": "overdue", 
                        "object_type": "task", 
                        "object_id": task_id, 
                        "score": 0.9, 
                        "reason": f"Overdue by {abs(delta)} days"
                    })
                    total_score += 0.9
                elif delta <= 3:
                    evidence_list.append({
                        "type": "upcoming_deadline", 
                        "object_type": "task", 
                        "object_id": task_id, 
                        "score": 0.8, 
                        "reason": f"Due in {delta} days"
                    })
                    total_score += 0.8
            except ValueError:
                pass
                
        if evidence_list:
            candidates[task_id] = {
                "object_id": task_id,
                "object_type": "task",
                "description": t["description"],
                "evidence": evidence_list,
                "total_score": total_score
            }
            
    # 2. Scan Projects
    cursor = await db.execute("SELECT id, name, metadata FROM entities WHERE type = 'Project'")
    projects = await cursor.fetchall()
    for p in projects:
        proj_id = p["id"]
        meta = json.loads(p["metadata"] or "{}")
        if meta.get("is_stale"):
            candidates[proj_id] = {
                "object_id": proj_id,
                "object_type": "project",
                "description": p["name"],
                "evidence": [{
                    "type": "stale_project",
                    "object_type": "project",
                    "object_id": proj_id,
                    "score": 0.6,
                    "reason": "Project has been marked as stale due to inactivity"
                }],
                "total_score": 0.6
            }
            
    # Sort by total_score descending and take top 5
    sorted_candidates = sorted(candidates.values(), key=lambda x: x["total_score"], reverse=True)
    return sorted_candidates[:5]


async def generate_daily_briefing(db):
    """Generates the daily briefing JSON for the current day."""
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    
    # Check if we already have a briefing for today
    cursor = await db.execute("SELECT date FROM daily_briefings WHERE date = ?", (today,))
    if await cursor.fetchone():
        return # Already generated
        
    # Gather Context
    # 1. Projects
    cursor = await db.execute("SELECT name, metadata FROM entities WHERE type = 'Project' ORDER BY updated_at DESC LIMIT 5")
    projects = await cursor.fetchall()
    projects_ctx = []
    for p in projects:
        meta = json.loads(p['metadata'] or '{}')
        status = "Stale" if meta.get("is_stale") else "Active"
        projects_ctx.append(f"- {p['name']} ({status})")
        
    # 2. Open Tasks
    cursor = await db.execute("SELECT description, priority FROM tasks WHERE status != 'done' AND status != 'deleted' ORDER BY created_at DESC LIMIT 15")
    tasks = await cursor.fetchall()
    tasks_ctx = [f"- [{t['priority']}] {t['description']}" for t in tasks]
    
    # 3. Recent Notes (last 48 hours)
    cursor = await db.execute("SELECT content FROM entries WHERE created_at > datetime('now', '-2 days') LIMIT 10")
    notes = [row['content'] for row in await cursor.fetchall()]
    
    # 4. Gather deterministic evidence candidates
    candidates = await _build_recommendation_candidates(db)
    candidates_json = json.dumps(candidates, indent=2)
    
    prompt = f"""
You are Raphael, the user's executive AI assistant. Generate a Daily Briefing based on their current context.

CONTEXT:
Active Projects:
{chr(10).join(projects_ctx)}

Open Tasks:
{chr(10).join(tasks_ctx)}

Recent Notes:
{chr(10).join(notes)}

CANDIDATE RECOMMENDATIONS:
(Use this exact evidence to write the 'suggested_plan')
{candidates_json}

INSTRUCTIONS:
Synthesize the context above into the following sections:
- 'overview': A high-level summary of their current focus.
- 'current_state': A factual summary of progress made recently.
- 'needs_attention': Highlight high-priority tasks, stale projects, or urgent items. If none, return an empty array `[]` for items.
- 'suggested_plan': Convert the CANDIDATE RECOMMENDATIONS into the suggested_plan array. For each candidate, write a concise `content` and `explanation` using ONLY the provided evidence. Do not invent additional reasons. You MUST include the exact `evidence` array from the candidate in your output. If there are no candidates, return an empty array `[]` for items.
- 'open_loops': Identify any unresolved questions or dangling threads from recent notes. If none, return an empty array `[]` for items.
- 'insight': Provide a single, unique strategic observation based on their activity.

Return ONLY valid JSON matching this exact structure:
{{
  "overview": {{ "title": "Overview", "items": [{{"content": "actual content here"}}] }},
  "current_state": {{ "title": "Current State", "items": [{{"content": "actual content here"}}] }},
  "needs_attention": {{ "title": "Needs Attention", "items": [{{"content": "actual content here"}}] }},
  "suggested_plan": {{ "title": "Suggested Plan", "items": [{{"content": "...", "explanation": "Why do this?", "evidence": [{{"type": "...", "object_type": "...", "object_id": "...", "score": 0.0, "reason": "..."}}]}}] }},
  "open_loops": {{ "title": "Open Loops", "items": [{{"content": "actual content here"}}] }},
  "insight": {{ "title": "Insight", "items": [{{"content": "actual content here"}}] }}
}}

IMPORTANT: Do not output literal "...", fill in the actual text. If a section has no relevant content, output an empty array for its items like `"items": []`.
"""
    from llm_manager import LIGHT_MODEL
    model = LIGHT_MODEL
    
    try:
        response = await generate_chat(model=model, messages=[
            {"role": "system", "content": "You output strict JSON."},
            {"role": "user", "content": prompt}
        ], format="json")
        
        briefing_json = response['message']['content']
        # Validate it parses
        json.loads(briefing_json)
        
        await db.execute(
            "INSERT INTO daily_briefings (date, content_json) VALUES (?, ?)",
            (today, briefing_json)
        )
        await db.commit()
    except Exception as e:
        print(f"Failed to generate briefing: {e}")

async def process_pending_entries(db):
    """Picks up entries that are stuck in 'pending' extraction status."""
    # Find up to 5 entries that have been pending for more than 5 minutes
    # This prevents picking up entries that were just created and are being processed
    cursor = await db.execute("""
        SELECT id, content FROM entries 
        WHERE extraction_status = 'pending' 
          AND created_at < datetime('now', '-5 minutes')
        LIMIT 5
    """)
    entries = await cursor.fetchall()
    
    if entries:
        from extraction.pipeline import process_entry
        for entry in entries:
            try:
                # Run them synchronously one-by-one so we don't spam the LLM Manager
                await process_entry(entry['id'], entry['content'])
            except SystemMemoryOverloadError:
                # It will stay pending
                break

TASK_REGISTRY = {
    "generate_daily_briefing": generate_daily_briefing,
    "refresh_relevance_scores": refresh_relevance_scores,
    "refresh_significance_scores": refresh_significance_scores,
    "detect_stale_projects": detect_stale_projects,
    "detect_open_loops": detect_open_loops,
    "merge_duplicate_entities": merge_duplicate_entities,
    "validate_graph_consistency": validate_graph_consistency,
    "remove_invalid_relationships": remove_invalid_relationships,
    "refresh_cached_dashboard": refresh_cached_dashboard,
    "process_pending_entries": process_pending_entries
}
