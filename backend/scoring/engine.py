import datetime
import math

async def get_or_create_score(db, object_id, object_type, initial_relevance=50.0, initial_significance=50.0):
    """Fetch existing scores or create a baseline entry."""
    cursor = await db.execute("SELECT * FROM knowledge_scores WHERE object_id = ?", (object_id,))
    row = await cursor.fetchone()
    if row:
        return dict(row)
    
    await db.execute(
        """
        INSERT INTO knowledge_scores (object_id, object_type, relevance, significance, previous_relevance)
        VALUES (?, ?, ?, ?, ?)
        """,
        (object_id, object_type, initial_relevance, initial_significance, initial_relevance)
    )
    return {
        "object_id": object_id,
        "object_type": object_type,
        "relevance": initial_relevance,
        "significance": initial_significance,
        "previous_relevance": initial_relevance,
        "explanation": "Initial baseline estimate."
    }

async def fetch_scores(db, object_ids: list[str]) -> dict:
    """Fetch scores for a list of object IDs. Returns a dict mapping object_id -> score dict."""
    if not object_ids:
        return {}
    
    placeholders = ",".join(["?"] * len(object_ids))
    cursor = await db.execute(f"SELECT * FROM knowledge_scores WHERE object_id IN ({placeholders})", object_ids)
    rows = await cursor.fetchall()
    
    result = {}
    for row in rows:
        result[row['object_id']] = {
            "relevance": row["relevance"],
            "significance": row["significance"],
            "trend": row["relevance"] - row["previous_relevance"],
            "explanation": row["explanation"]
        }
    return result

async def update_object_scores(db, object_id, object_type, baseline_rel=None, baseline_sig=None):
    """
    Computes Relevance and Significance for a given object using backend heuristics.
    Relevance: "How useful is this information RIGHT NOW?"
    Significance: "If I look back in five years, how important is this?"
    """
    if baseline_rel is None: baseline_rel = 50.0
    if baseline_sig is None: baseline_sig = 50.0
    
    score_data = await get_or_create_score(db, object_id, object_type, baseline_rel, baseline_sig)
    
    rel_score = 50.0
    sig_score = 50.0
    rel_explanations = []
    sig_explanations = []
    
    # 1. Fetch metadata based on object type
    created_at = datetime.datetime.utcnow()
    updated_at = datetime.datetime.utcnow()
    last_seen = None
    mention_count = 0
    is_completed = False
    
    if object_type == 'entry':
        cursor = await db.execute("SELECT created_at, updated_at FROM entries WHERE id = ?", (object_id,))
        row = await cursor.fetchone()
        if row:
            created_at = datetime.datetime.fromisoformat(row['created_at'].replace("Z", "+00:00"))
            updated_at = datetime.datetime.fromisoformat(row['updated_at'].replace("Z", "+00:00")) if row['updated_at'] else created_at
            
    elif object_type in ('entity', 'project', 'person', 'meeting', 'event'):
        cursor = await db.execute("SELECT created_at, updated_at, last_seen, mention_count FROM entities WHERE id = ?", (object_id,))
        row = await cursor.fetchone()
        if row:
            created_at = datetime.datetime.fromisoformat(row['created_at'].replace("Z", "+00:00"))
            updated_at = datetime.datetime.fromisoformat(row['updated_at'].replace("Z", "+00:00")) if row['updated_at'] else created_at
            if row['last_seen']:
                last_seen = datetime.datetime.fromisoformat(row['last_seen'].replace("Z", "+00:00"))
            mention_count = row['mention_count']
            
    elif object_type == 'task':
        cursor = await db.execute("SELECT created_at, completed_at, status FROM tasks WHERE id = ?", (object_id,))
        row = await cursor.fetchone()
        if row:
            created_at = datetime.datetime.fromisoformat(row['created_at'].replace("Z", "+00:00"))
            is_completed = row['status'] == 'done'
            if row['completed_at']:
                updated_at = datetime.datetime.fromisoformat(row['completed_at'].replace("Z", "+00:00"))
                
    elif object_type == 'decision':
        cursor = await db.execute("SELECT created_at, status FROM decisions WHERE id = ?", (object_id,))
        row = await cursor.fetchone()
        if row:
            created_at = datetime.datetime.fromisoformat(row['created_at'].replace("Z", "+00:00"))
            is_completed = row['status'] != 'Active'
            
    elif object_type == 'idea':
        cursor = await db.execute("SELECT created_at FROM ideas WHERE id = ?", (object_id,))
        row = await cursor.fetchone()
        if row:
            created_at = datetime.datetime.fromisoformat(row['created_at'].replace("Z", "+00:00"))

    # Graph Connectivity
    in_edges = 0
    out_edges = 0
    if object_type in ('entity', 'project', 'person', 'meeting', 'event'):
        c1 = await db.execute("SELECT COUNT(*) as c FROM entity_relations WHERE to_entity_id = ?", (object_id,))
        in_edges = (await c1.fetchone())['c']
        c2 = await db.execute("SELECT COUNT(*) as c FROM entity_relations WHERE from_entity_id = ?", (object_id,))
        out_edges = (await c2.fetchone())['c']
        
        # Count associated entries
        c3 = await db.execute("SELECT COUNT(*) as c FROM entry_entities WHERE entity_id = ?", (object_id,))
        mention_count = max(mention_count, (await c3.fetchone())['c'])
        
    elif object_type == 'entry':
        c1 = await db.execute("SELECT COUNT(*) as c FROM entry_entities WHERE entry_id = ?", (object_id,))
        out_edges = (await c1.fetchone())['c']

    # --- Relevance Heuristics ---
    now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    # Ensure dt has tzinfo
    if created_at.tzinfo is None: created_at = created_at.replace(tzinfo=datetime.timezone.utc)
    if updated_at.tzinfo is None: updated_at = updated_at.replace(tzinfo=datetime.timezone.utc)
    if last_seen and last_seen.tzinfo is None: last_seen = last_seen.replace(tzinfo=datetime.timezone.utc)

    days_since_update = (now - updated_at).days
    days_since_seen = (now - last_seen).days if last_seen else days_since_update
    
    if days_since_update <= 1:
        rel_score += 20
        rel_explanations.append("Updated recently")
    elif days_since_update <= 7:
        rel_score += 10
        rel_explanations.append("Updated this week")
        
    if days_since_seen <= 3:
        rel_score += 15
        rel_explanations.append("Viewed or referenced recently")
        
    if is_completed:
        rel_score -= 30
        rel_explanations.append("Completed or inactive")
        
    if object_type in ('project', 'entity'):
        # Check for open tasks
        cursor = await db.execute("SELECT COUNT(*) as c FROM tasks WHERE project_id = ? AND status != 'done'", (object_id,))
        open_tasks = (await cursor.fetchone())['c']
        if open_tasks > 0:
            rel_score += min(30, open_tasks * 5)
            rel_explanations.append(f"Contains {open_tasks} open tasks")
            
    if mention_count > 5:
        rel_score += min(20, mention_count * 2)
        rel_explanations.append(f"Referenced frequently ({mention_count} times)")

    # Gradual time decay for relevance
    decay = min(40, days_since_update * 0.5)
    if decay > 10:
        rel_score -= decay
        rel_explanations.append(f"Decayed due to inactivity ({days_since_update} days)")

    # Clamp Relevance
    rel_score = max(0.0, min(100.0, rel_score))

    # --- Significance Heuristics ---
    
    # Base significance is higher for structured objects
    if object_type == 'decision':
        sig_score += 30
        sig_explanations.append("Architecture or life decision")
    elif object_type == 'project':
        sig_score += 20
        sig_explanations.append("Project milestone")
        
    total_edges = in_edges + out_edges
    if total_edges > 3:
        sig_score += min(30, total_edges * 3)
        sig_explanations.append(f"Connected to {total_edges} important entities")
        
    if mention_count > 10:
        sig_score += min(20, mention_count)
        sig_explanations.append(f"Historically referenced {mention_count} times")
        
    days_alive = (now - created_at).days
    if days_alive > 30 and mention_count > 5:
        sig_score += 15
        sig_explanations.append(f"Referenced across {days_alive} days")

    # Time does NOT decay significance, but extremely old isolated nodes might be slightly lower
    if days_alive > 100 and total_edges == 0:
        sig_score -= 10
        sig_explanations.append("Isolated for a long time")
        
    # Combine baseline with heuristics
    # If the LLM gave a very high baseline, respect it slightly
    if baseline_sig > 50:
        sig_score = (sig_score + baseline_sig) / 2
        
    # Clamp Significance
    sig_score = max(0.0, min(100.0, sig_score))
    
    # Format explanation
    final_explanation = "Relevance:\n" + "\n".join([f"• {e}" for e in rel_explanations]) + "\n\nSignificance:\n" + "\n".join([f"• {e}" for e in sig_explanations])

    # Save to DB
    await db.execute(
        """
        UPDATE knowledge_scores 
        SET previous_relevance = relevance,
            relevance = ?,
            significance = ?,
            explanation = ?,
            last_computed_at = CURRENT_TIMESTAMP
        WHERE object_id = ?
        """,
        (rel_score, sig_score, final_explanation, object_id)
    )
    
    return rel_score, sig_score
