"""
Ranking module for hybrid retrieval using Reciprocal Rank Fusion (RRF).
"""

from typing import List, Dict

RRF_K = 60
MAX_CANDIDATES_PER_SOURCE = 60
MAX_FUSED_CANDIDATES = 20
ENABLE_RANKING_DIAGNOSTICS = False

def rrf_fusion(rankings_lists: List[List[str]], rrf_k: int = RRF_K) -> Dict[str, float]:
    """
    Computes RRF score for a set of candidate lists.
    rankings_lists is a list where each element is a list of document IDs ordered by rank.
    Rank is 1-based.
    
    Formula: RRF(document) = Σ 1 / (k + rank)
    """
    rrf_scores: Dict[str, float] = {}
    for candidates in rankings_lists:
        for rank, doc_id in enumerate(candidates, start=1):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (rrf_k + rank)
    return rrf_scores

def rerank_by_relevance(rrf_scores: Dict[str, float], relevance_scores: Dict[str, float]) -> Dict[str, float]:
    """
    Applies a weak deterministic reranking using stored relevance_score.
    Relevance should only break ties or slightly prefer more relevant knowledge.
    Max boost is 0.01 (assuming relevance 0-100).
    """
    final_scores: Dict[str, float] = {}
    for doc_id, rrf in rrf_scores.items():
        rel = relevance_scores.get(doc_id, 50.0)
        # Max boost is 0.01 for a relevance of 100
        boost = (rel / 100.0) * 0.01 
        final_scores[doc_id] = rrf + boost
    return final_scores
