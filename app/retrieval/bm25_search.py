"""
BM25 Keyword Search Engine for THE RELAY.
"""

import pickle
import re
from pathlib import Path
from typing import List, Optional
import numpy as np
from rank_bm25 import BM25Okapi
from app.retrieval.chunking import TextChunk
from app.retrieval.semantic_search import SearchResult

def tokenize_bm25(text: str) -> List[str]:
    """Tokenize and normalize text for BM25 indexing."""
    tokens = re.findall(r"\b[a-zA-Z0-9_\-\.]+\b", text.lower())
    return [t for t in tokens if len(t) > 1]

class BM25SearchIndex:
    def __init__(self):
        self.bm25: Optional[BM25Okapi] = None
        self.chunks: List[TextChunk] = []

    def build_index(self, chunks: List[TextChunk]):
        self.chunks = chunks
        tokenized_corpus = [tokenize_bm25(c.text) for c in chunks]
        self.bm25 = BM25Okapi(tokenized_corpus)

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        if self.bm25 is None:
            raise RuntimeError("BM25 index has not been built.")

        query_tokens = tokenize_bm25(query)
        if not query_tokens:
            return []

        raw_scores = self.bm25.get_scores(query_tokens)
        max_score = np.max(raw_scores) if len(raw_scores) > 0 and np.max(raw_scores) > 0 else 1.0

        top_indices = np.argsort(raw_scores)[::-1][:top_k]
        results = []
        for idx in top_indices:
            normalized_score = float(raw_scores[idx] / max_score)
            if normalized_score > 0.01:
                results.append(
                    SearchResult(
                        chunk=self.chunks[idx],
                        score=normalized_score,
                        method="bm25"
                    )
                )

        return results

    def save(self, filepath: Path):
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, filepath: Path) -> "BM25SearchIndex":
        with open(filepath, "rb") as f:
            return pickle.load(f)

