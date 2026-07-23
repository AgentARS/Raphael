import json
import uuid
import string
import numpy as np
from rapidfuzz import fuzz
from .embeddings import generate_embedding
import ollama
import os

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EXTRACTION_MODEL = os.getenv("EXTRACTION_MODEL", "qwen3:8b")

client = ollama.AsyncClient(host=OLLAMA_BASE_URL)

VALID_RELATIONS = {
    "Person": {"discussed", "created", "assigned_to", "attended", "mentioned", "inspired"},
    "Project": {"contains", "related_to", "depends_on", "supersedes", "belongs_to", "completed", "blocked_by", "scheduled_for"},
    "Topic": {"related_to", "part_of", "depends_on", "references", "supports", "contradicts"},
    "Organization": {"employs", "owns", "related_to"},
    "Tool": {"used_for", "integrated_with", "used_by", "depends_on", "belongs_to"}
}

def normalize_name(name: str) -> str:
    """Stage 2: Lowercase, strip punctuation and whitespace, remove common titles."""
    if not name:
        return ""
    name = name.lower()
    # Remove titles
    titles = ["dr.", "dr", "mr.", "mr", "ms.", "ms", "mrs.", "mrs", "prof.", "prof"]
    for t in titles:
        if name.startswith(t + " "):
            name = name[len(t)+1:]
    
    # Remove punctuation
    name = name.translate(str.maketrans('', '', string.punctuation))
    # Strip whitespace
    return " ".join(name.split())

async def _update_entity_stats(db, entity_id, current_entry_id):
    await db.execute(
        "UPDATE entities SET mention_count = mention_count + 1, last_seen = CURRENT_TIMESTAMP WHERE id = ?",
        (entity_id,)
    )

async def _add_alias_and_update(db, entity_id, new_alias, existing_aliases_json, current_entry_id):
    aliases = json.loads(existing_aliases_json or "[]")
    if new_alias not in aliases:
        aliases.append(new_alias)
    await db.execute(
        "UPDATE entities SET aliases = ?, mention_count = mention_count + 1, last_seen = CURRENT_TIMESTAMP WHERE id = ?",
        (json.dumps(aliases), entity_id)
    )

async def resolve_canonical_entity(db, entity_dict, current_entry_id):
    """
    5-Stage Pipeline to find or create Canonical Entities.
    Returns the Canonical Entity ID.
    """
    raw_name = entity_dict.get('name', '')
    ent_type = entity_dict.get('type', 'Topic')
    if not raw_name:
        return None
        
    norm_name = normalize_name(raw_name)
    
    # Get all entities of the same type for comparison
    cursor = await db.execute("SELECT * FROM entities WHERE type = ?", (ent_type,))
    existing_entities = await cursor.fetchall()
    
    # Stage 1: Exact match (against name or aliases)
    for row in existing_entities:
        if row["name"] == raw_name:
            await _update_entity_stats(db, row["id"], current_entry_id)
            return row["id"]
        aliases = json.loads(row["aliases"] or "[]")
        if raw_name in aliases:
            await _update_entity_stats(db, row["id"], current_entry_id)
            return row["id"]
            
    # Stage 2 & 3: Normalize & Fuzzy match (RapidFuzz > 95%)
    for row in existing_entities:
        db_norm_name = normalize_name(row["name"])
        if db_norm_name == norm_name:
            await _add_alias_and_update(db, row["id"], raw_name, row["aliases"], current_entry_id)
            return row["id"]
            
        similarity = fuzz.token_set_ratio(norm_name, db_norm_name)
        if similarity > 95:
            await _add_alias_and_update(db, row["id"], raw_name, row["aliases"], current_entry_id)
            return row["id"]
            
    # Stage 4: Embedding similarity
    new_embedding = await generate_embedding(raw_name)
    if new_embedding and existing_entities:
        q_vec = np.array(new_embedding, dtype=np.float32)
        for row in existing_entities:
            if row["embedding"]:
                e_vec = np.frombuffer(row["embedding"], dtype=np.float32)
                norm1 = np.linalg.norm(q_vec)
                norm2 = np.linalg.norm(e_vec)
                if norm1 != 0 and norm2 != 0:
                    sim = float(np.dot(q_vec, e_vec) / (norm1 * norm2))
                    if sim > 0.95:  # High threshold for purely semantic match
                        await _add_alias_and_update(db, row["id"], raw_name, row["aliases"], current_entry_id)
                        return row["id"]
                        
    # Stage 5: LLM
    # We will use the LLM to verify if there's any ambiguous entities with semantic similarity between 0.85 and 0.95
    if new_embedding and existing_entities:
        q_vec = np.array(new_embedding, dtype=np.float32)
        for row in existing_entities:
            if row["embedding"]:
                e_vec = np.frombuffer(row["embedding"], dtype=np.float32)
                norm1 = np.linalg.norm(q_vec)
                norm2 = np.linalg.norm(e_vec)
                if norm1 != 0 and norm2 != 0:
                    sim = float(np.dot(q_vec, e_vec) / (norm1 * norm2))
                    if 0.85 < sim <= 0.95:
                        # Ambiguous match, ask LLM
                        prompt = f"Are the entities '{raw_name}' and '{row['name']}' likely referring to the same exact {ent_type}? Reply with ONLY 'YES' or 'NO'."
                        response = await client.chat(
                            model=EXTRACTION_MODEL,
                            messages=[{"role": "user", "content": prompt}],
                            options={"temperature": 0.0}
                        )
                        reply = response.get('message', {}).get('content', '').strip().upper()
                        if 'YES' in reply:
                            await _add_alias_and_update(db, row["id"], raw_name, row["aliases"], current_entry_id)
                            return row["id"]
    
    # Create new Canonical Entity
    new_id = str(uuid.uuid4())
    emb_bytes = np.array(new_embedding, dtype=np.float32).tobytes() if new_embedding else None
    confidence = entity_dict.get("confidence", 1.0)
    if confidence is None:
        confidence = 1.0
    
    await db.execute(
        """
        INSERT INTO entities (id, type, name, aliases, metadata, embedding, confidence, last_seen, mention_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1)
        """,
        (new_id, ent_type, raw_name, "[]", "{}", emb_bytes, float(confidence))
    )
    
    # Store initial scores
    rel_est = entity_dict.get("relevance_estimate")
    sig_est = entity_dict.get("significance_estimate")
    if rel_est is not None or sig_est is not None:
        from scoring.engine import update_object_scores
        await update_object_scores(db, new_id, "entities", baseline_rel=rel_est, baseline_sig=sig_est)

    return new_id


class Validator:
    def __init__(self, db, current_entry_id):
        self.db = db
        self.entry_id = current_entry_id
        
    async def validate_and_resolve(self, raw_json):
        """Validates the JSON from LLM and returns clean, resolved data with entity IDs."""
        data = raw_json if isinstance(raw_json, dict) else json.loads(raw_json)
        
        # Filter by confidence
        threshold = 0.5
        
        clean_entities = []
        name_to_id = {}
        
        for e in data.get("entities", []):
            conf = e.get("confidence")
            if conf is None or conf >= threshold:
                ent_id = await resolve_canonical_entity(self.db, e, self.entry_id)
                if ent_id:
                    name_to_id[e.get("name")] = ent_id
                    clean_entities.append({
                        "id": ent_id, 
                        "type": e.get("type"), 
                        "name": e.get("name"),
                        "relevance_estimate": e.get("relevance_estimate"),
                        "significance_estimate": e.get("significance_estimate")
                    })
                    
        clean_tasks = []
        for t in data.get("tasks", []):
            conf = t.get("confidence")
            if conf is None or conf >= threshold:
                clean_tasks.append(t)
                
        clean_ideas = []
        for i in data.get("ideas", []):
            conf = i.get("confidence")
            if conf is None or conf >= threshold:
                clean_ideas.append(i)
                
        clean_relationships = []
        for r in data.get("relationships", []):
            conf = r.get("confidence")
            if conf is None or conf >= threshold:
                source_type = r.get("source_type")
                rel_type = r.get("relationship_type")
                
                # Check ontology schema
                if source_type in VALID_RELATIONS and rel_type in VALID_RELATIONS[source_type]:
                    clean_relationships.append(r)
                else:
                    print(f"Validator rejected impossible relationship: {source_type} -> {rel_type}")
                    
        return {
            "entities": clean_entities,
            "tasks": clean_tasks,
            "task_updates": data.get("task_updates", []),
            "ideas": clean_ideas,
            "decisions": data.get("decisions", []),
            "relationships": clean_relationships,
            "name_to_id": name_to_id
        }
