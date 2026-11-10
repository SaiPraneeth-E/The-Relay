"""
Dense semantic vector search engine for THE RELAY.
Constructs continuous latent semantic embeddings and performs normalized cosine vector search.
"""

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize
from app.retrieval.chunking import TextChunk

@dataclass
class SearchResult:
    chunk: TextChunk
    score: float
    method: str

class SemanticSearchIndex:
    def __init__(self, n_components: int = 128):
        self.n_components = n_components
        self.vectorizer = TfidfVectorizer(
            sublinear_tf=True,
            ngram_range=(1, 2),
            max_df=0.85,
            min_df=2,
            stop_words="english"
        )
        self.svd: Optional[TruncatedSVD] = None
        self.chunks: List[TextChunk] = []
        self.chunk_embeddings: Optional[np.ndarray] = None

    def build_index(self, chunks: List[TextChunk]):
        self.chunks = chunks
        corpus = [c.text for c in chunks]
        tfidf_matrix = self.vectorizer.fit_transform(corpus)

        n_comp = min(self.n_components, tfidf_matrix.shape[1] - 1, len(corpus) - 1)
        if n_comp < 2:
            n_comp = 2

        self.svd = TruncatedSVD(n_components=n_comp, random_state=42)
        dense_embeddings = self.svd.fit_transform(tfidf_matrix)
        self.chunk_embeddings = normalize(dense_embeddings, norm="l2")

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        if self.svd is None or self.chunk_embeddings is None:
            raise RuntimeError("Semantic index has not been built.")

        query_tfidf = self.vectorizer.transform([query])
        query_dense = self.svd.transform(query_tfidf)
        query_norm = normalize(query_dense, norm="l2")

        # Compute cosine similarities via dot product
        similarities = np.dot(self.chunk_embeddings, query_norm.T).flatten()

        top_indices = np.argsort(similarities)[::-1][:top_k]
        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            results.append(SearchResult(chunk=self.chunks[idx], score=score, method="semantic"))

        return results

    def save(self, filepath: Path):
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, filepath: Path) -> "SemanticSearchIndex":
        with open(filepath, "rb") as f:
            return pickle.load(f)

