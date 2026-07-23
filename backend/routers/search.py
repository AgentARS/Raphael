"""
Search router for Raphael.

Provides full-text search over entries using SQLite FTS5.
"""

from fastapi import APIRouter, Query, HTTPException
import numpy as np

from database import get_db
from models import EntryResponse, SearchResult
from extraction.embeddings import generate_embedding
from routers.entries import _row_to_entry_response
from scoring.engine import fetch_scores

router = APIRouter(prefix="/api/search", tags=["search"])


def cosine_similarity(v1, v2):
    dot = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


@router.get("", response_model=list[SearchResult])
async def search_entries(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Hybrid search: Combines FTS5 MATCH with vector cosine similarity.
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    query_vector = generate_embedding(q)
    query_np = np.array(query_vector, dtype=np.float32) if query_vector else None

    results_map = {} # entry_id -> SearchResult data
    
    async with get_db() as db:
        # 1. Get FTS5 results
        cursor = await db.execute(
            """
            SELECT
                e.id, e.content, e.created_at, e.updated_at, e.source_type, e.extraction_status,
                snippet(entries_fts, 0, '<mark>', '</mark>', '...', 32) AS snippet,
                entries_fts.rank AS fts_rank
            FROM entries_fts
            JOIN entries e ON e.rowid = entries_fts.rowid
            WHERE entries_fts MATCH ?
            """,
            (q,),
        )
        fts_rows = await cursor.fetchall()
        
        # Max FTS rank is highly variable, but usually more negative is better.
        # We'll normalize FTS rank later if needed, but for simplicity:
        for row in fts_rows:
            entry_id = row["id"]
            results_map[entry_id] = {
                "row": row,
                "snippet": row["snippet"],
                "fts_score": -row["fts_rank"], # invert so higher is better
                "vector_score": 0.0
            }

        # 2. Vector Search
        if query_np is not None:
            cursor = await db.execute("SELECT id, content, created_at, updated_at, source_type, extraction_status, embedding FROM entries WHERE embedding IS NOT NULL")
            all_rows = await cursor.fetchall()
            
            for row in all_rows:
                entry_id = row["id"]
                emb_bytes = row["embedding"]
                if emb_bytes:
                    db_vec = np.frombuffer(emb_bytes, dtype=np.float32)
                    sim = cosine_similarity(query_np, db_vec)
                    
                    if entry_id in results_map:
                        results_map[entry_id]["vector_score"] = float(sim)
                    elif sim > 0.3: # Threshold for semantic match
                        results_map[entry_id] = {
                            "row": row,
                            "snippet": None, # Vector search doesn't generate snippets by default
                            "fts_score": 0.0,
                            "vector_score": float(sim)
                        }


    # 3. Combine scores (Simple hybrid scoring)
    # Give semantic search high weight, FTS search a boost if words match exactly.
    final_results = []
    
    async with get_db() as db:
        scores_map = await fetch_scores(db, list(results_map.keys()))
        
        for entry_id, data in results_map.items():
            row = data["row"]
            
            relevance = scores_map.get(entry_id, {}).get("relevance", 50.0)
            
            # Normalize fts somewhat (typically 0 to 10 range depending on length)
            # Vector is 0 to 1
            combined_score = (data["vector_score"] * 10) + data["fts_score"] + (relevance / 100 * 5)
            
            # Filter low relevance
            if combined_score <= 0.5:
                continue
                
            entry = await _row_to_entry_response(db, row)
            final_results.append(
                SearchResult(
                    entry=entry,
                    snippet=data["snippet"],
                    rank=combined_score,
                )
            )

    # Sort descending
    final_results.sort(key=lambda x: x.rank or 0, reverse=True)
    return final_results[:limit]
