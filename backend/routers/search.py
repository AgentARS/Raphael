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

from search.ranking import (
    rrf_fusion,
    rerank_by_relevance,
    MAX_CANDIDATES_PER_SOURCE,
    MAX_FUSED_CANDIDATES,
    ENABLE_RANKING_DIAGNOSTICS
)

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
    Hybrid search: Combines FTS5 MATCH with vector cosine similarity using RRF.
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    query_vector = generate_embedding(q)
    query_np = np.array(query_vector, dtype=np.float32) if query_vector else None

    results_map = {} # entry_id -> {row, snippet, fts_score, vector_score}
    fts_candidates = []
    semantic_candidates = []
    
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
        
        # Sort FTS rows by score (fts_rank is typically more negative = better)
        fts_sorted = sorted(fts_rows, key=lambda r: r["fts_rank"])
        for row in fts_sorted[:MAX_CANDIDATES_PER_SOURCE]:
            entry_id = row["id"]
            fts_candidates.append(entry_id)
            results_map[entry_id] = {
                "row": row,
                "snippet": row["snippet"],
                "fts_score": -row["fts_rank"],
                "vector_score": 0.0
            }

        # 2. Vector Search
        if query_np is not None:
            cursor = await db.execute("SELECT id, content, created_at, updated_at, source_type, extraction_status, embedding FROM entries WHERE embedding IS NOT NULL")
            all_rows = await cursor.fetchall()
            
            semantic_results = []
            for row in all_rows:
                entry_id = row["id"]
                emb_bytes = row["embedding"]
                if emb_bytes:
                    db_vec = np.frombuffer(emb_bytes, dtype=np.float32)
                    sim = float(cosine_similarity(query_np, db_vec))
                    if sim > 0.3:
                        semantic_results.append((sim, row))
            
            # Sort by similarity descending
            semantic_results.sort(key=lambda x: x[0], reverse=True)
            for sim, row in semantic_results[:MAX_CANDIDATES_PER_SOURCE]:
                entry_id = row["id"]
                semantic_candidates.append(entry_id)
                if entry_id in results_map:
                    results_map[entry_id]["vector_score"] = sim
                else:
                    results_map[entry_id] = {
                        "row": row,
                        "snippet": None,
                        "fts_score": 0.0,
                        "vector_score": sim
                    }

    # 3. Ranking using RRF and Relevance Reranking
    rrf_scores = rrf_fusion([semantic_candidates, fts_candidates])
    
    final_results = []
    
    async with get_db() as db:
        fused_ids = list(rrf_scores.keys())
        scores_map = await fetch_scores(db, fused_ids)
        
        # Extract just the relevance score per document
        relevance_scores = {doc_id: scores_map.get(doc_id, {}).get("relevance", 50.0) for doc_id in fused_ids}
        
        # Rerank
        final_scores = rerank_by_relevance(rrf_scores, relevance_scores)
        
        # Build responses
        for entry_id in fused_ids:
            data = results_map[entry_id]
            entry = await _row_to_entry_response(db, data["row"])
            
            diagnostics = None
            if ENABLE_RANKING_DIAGNOSTICS:
                diagnostics = {
                    "semantic_rank": semantic_candidates.index(entry_id) + 1 if entry_id in semantic_candidates else None,
                    "fts_rank": fts_candidates.index(entry_id) + 1 if entry_id in fts_candidates else None,
                    "rrf_score": round(rrf_scores[entry_id], 4),
                    "relevance_score": round(relevance_scores.get(entry_id, 50.0), 2),
                    "final_score": round(final_scores[entry_id], 4)
                }
                
            final_results.append(
                SearchResult(
                    entry=entry,
                    snippet=data["snippet"],
                    rank=final_scores[entry_id],
                    diagnostics=diagnostics
                )
            )

    # Sort final results descending
    final_results.sort(key=lambda x: x.rank or 0, reverse=True)
    capped_limit = min(limit, MAX_FUSED_CANDIDATES)
    return final_results[:capped_limit]
