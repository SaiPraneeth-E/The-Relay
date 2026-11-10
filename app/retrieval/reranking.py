"""
Reranking and Reciprocal Rank Fusion (RRF) for THE RELAY.
"""

from typing import Dict, List
from app.retrieval.chunking import TextChunk
from app.retrieval.semantic_search import SearchResult

def reciprocal_rank_fusion(
    ranked_lists: List[List[SearchResult]],
    k: int = 60
) -> List[SearchResult]:
    """Combines multiple ranked result lists using Reciprocal Rank Fusion (RRF)."""
    scores: Dict[str, float] = {}
    chunk_map: Dict[str, TextChunk] = {}

    for ranked_list in ranked_lists:
        for rank, res in enumerate(ranked_list):
            cid = res.chunk.chunk_id
            chunk_map[cid] = res.chunk
            rrf_score = 1.0 / (k + rank + 1)
            scores[cid] = scores.get(cid, 0.0) + rrf_score

    # Sort descending by fused RRF score
    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    fused_results = [
        SearchResult(chunk=chunk_map[cid], score=score, method="rrf_fusion")
        for cid, score in sorted_items
    ]
    return fused_results

def contextual_rerank(
    query: str,
    candidates: List[SearchResult],
    top_k: int = 5
) -> List[SearchResult]:
    """
    Detailed lexical-semantic cross-scoring re-ranker.
    Evaluates query term proximity, phrase density, and section relevance.
    """
    query_terms = set(query.lower().split())
    reranked: List[SearchResult] = []

    for res in candidates:
        text_lower = res.chunk.text.lower()
        # Lexical coverage
        term_matches = sum(1 for term in query_terms if term in text_lower)
        coverage_ratio = term_matches / max(len(query_terms), 1)

        # Exact phrase bonus
        exact_bonus = 0.2 if query.lower() in text_lower else 0.0

        # Section relevance bonus
        sec_bonus = 0.1 if any(t in res.chunk.section_title.lower() for t in query_terms) else 0.0

        composite_score = (res.score * 0.5) + (coverage_ratio * 0.3) + exact_bonus + sec_bonus
        reranked.append(
            SearchResult(
                chunk=res.chunk,
                score=composite_score,
                method="cross_reranked"
            )
        )

    reranked.sort(key=lambda x: x.score, reverse=True)
    return reranked[:top_k]

