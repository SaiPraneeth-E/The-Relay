"""
Hybrid Search Engine for THE RELAY.
Coordinates Semantic Search, BM25 Keyword Search, and Reranking across Settings A, B, and C.
"""

from pathlib import Path
from typing import Dict, List, Literal, Optional
from app.core.config import settings
from app.retrieval.bm25_search import BM25SearchIndex
from app.retrieval.chunking import CHUNK_CONFIGS, TextChunk, chunk_document_library
from app.retrieval.ingestion import DocumentLibrary, ingest_papers
from app.retrieval.reranking import contextual_rerank, reciprocal_rank_fusion
from app.retrieval.semantic_search import SearchResult, SemanticSearchIndex

class HybridSearchEngine:
    def __init__(self, indexes_dir: Optional[Path] = None):
        self.indexes_dir = indexes_dir or settings.indexes_dir
        self.doc_library: Optional[DocumentLibrary] = None
        self.semantic_indexes: Dict[str, SemanticSearchIndex] = {}
        self.bm25_indexes: Dict[str, BM25SearchIndex] = {}
        self.chunks_by_setting: Dict[str, List[TextChunk]] = {}

    def initialize(self, papers_dir: Optional[Path] = None, force_reindex: bool = False):
        """Loads or builds indexes for all three retrieval settings (A, B, C)."""
        papers_dir = papers_dir or settings.papers_dir
        all_exist = all(
            (self.indexes_dir / f"semantic_{s}.pkl").exists() and
            (self.indexes_dir / f"bm25_{s}.pkl").exists()
            for s in ["A", "B", "C"]
        )

        if not force_reindex and all_exist:
            for setting in ["A", "B", "C"]:
                sem_path = self.indexes_dir / f"semantic_{setting}.pkl"
                bm25_path = self.indexes_dir / f"bm25_{setting}.pkl"
                self.semantic_indexes[setting] = SemanticSearchIndex.load(sem_path)
                self.bm25_indexes[setting] = BM25SearchIndex.load(bm25_path)
                self.chunks_by_setting[setting] = self.semantic_indexes[setting].chunks
            return

        self.doc_library = ingest_papers(papers_dir)
        for setting in ["A", "B", "C"]:
            sem_path = self.indexes_dir / f"semantic_{setting}.pkl"
            bm25_path = self.indexes_dir / f"bm25_{setting}.pkl"
            chunks = chunk_document_library(self.doc_library, setting=setting)  # type: ignore
            self.chunks_by_setting[setting] = chunks

            sem_idx = SemanticSearchIndex(n_components=settings.embedding_dim)
            sem_idx.build_index(chunks)
            sem_idx.save(sem_path)
            self.semantic_indexes[setting] = sem_idx

            bm25_idx = BM25SearchIndex()
            bm25_idx.build_index(chunks)
            bm25_idx.save(bm25_path)
            self.bm25_indexes[setting] = bm25_idx

    def search(
        self,
        query: str,
        setting: Literal["A", "B", "C"] = "B",
        filter_paper_id: Optional[str] = None,
        top_k: Optional[int] = None
    ) -> List[SearchResult]:
        """
        Executes hybrid search tailored to the specified retrieval setting:
        - Setting A: Small chunks, top_k=3, combined BM25+Semantic without reranking.
        - Setting B: Medium chunks, top_k=5, hybrid RRF.
        - Setting C: Large chunks, top_k=8, hybrid RRF with contextual reranking.
        """
        if setting not in self.semantic_indexes:
            self.initialize()

        cfg = CHUNK_CONFIGS[setting]
        effective_k = top_k if top_k is not None else cfg["top_k"]

        # Fetch candidate pools from both modalities
        pool_size = effective_k * 3
        sem_results = self.semantic_indexes[setting].search(query, top_k=pool_size)
        bm25_results = self.bm25_indexes[setting].search(query, top_k=pool_size)

        # Apply metadata filters if requested
        if filter_paper_id:
            sem_results = [r for r in sem_results if r.chunk.paper_id == filter_paper_id]
            bm25_results = [r for r in bm25_results if r.chunk.paper_id == filter_paper_id]

        if setting == "A":
            # Setting A: Quick merged top-k
            fused = reciprocal_rank_fusion([sem_results, bm25_results], k=40)
            return fused[:effective_k]

        elif setting == "B":
            # Setting B: Standard balanced RRF
            fused = reciprocal_rank_fusion([sem_results, bm25_results], k=60)
            return fused[:effective_k]

        else:
            # Setting C: Large chunks with RRF + deep contextual reranking
            fused = reciprocal_rank_fusion([sem_results, bm25_results], k=60)
            candidates = fused[: effective_k * 2]
            reranked = contextual_rerank(query, candidates, top_k=effective_k)
            return reranked

