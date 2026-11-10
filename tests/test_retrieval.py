"""
Tests for Ingestion, Chunking, and Hybrid Retrieval in THE RELAY.
"""

import pytest
from pathlib import Path
from app.retrieval.ingestion import ingest_papers, clean_extracted_text, PAPERS_METADATA
from app.retrieval.chunking import chunk_document_library, CHUNK_CONFIGS
from app.retrieval.hybrid_search import HybridSearchEngine

@pytest.fixture(scope="session")
def library():
    return ingest_papers(Path("data/papers"))

def test_paper_ingestion_exact_versions(library):
    assert len(library.papers) == 3
    assert "1706.03762v7" in library.papers
    assert "2410.00037v1" in library.papers
    assert "2507.07955v2" in library.papers

    # Verify pages extracted
    assert len(library.papers["1706.03762v7"]) >= 10
    assert len(library.papers["2410.00037v1"]) >= 10
    assert len(library.papers["2507.07955v2"]) >= 10

def test_chunking_configurations(library):
    for setting in ["A", "B", "C"]:
        chunks = chunk_document_library(library, setting=setting)
        assert len(chunks) > 0
        cfg = CHUNK_CONFIGS[setting]
        # Check that metadata is preserved on all chunks
        for c in chunks[:10]:
            assert c.paper_id in PAPERS_METADATA
            assert c.page_number >= 1
            assert len(c.text) > 40
            assert c.setting == setting

def test_hybrid_search_accuracy():
    engine = HybridSearchEngine()
    engine.initialize()

    # Query for Scaled Dot-Product Attention (Paper 1)
    results = engine.search("scaled dot product attention formula", setting="B", top_k=3)
    assert len(results) > 0
    top_chunk = results[0].chunk
    assert top_chunk.paper_id == "1706.03762v7"
    assert "softmax" in top_chunk.text.lower() or "attention" in top_chunk.text.lower()

    # Query for Moshi Mimi codec (Paper 2)
    results_m = engine.search("Mimi neural audio codec bandwidth latency", setting="B", top_k=3)
    assert len(results_m) > 0
    top_m = results_m[0].chunk
    assert top_m.paper_id == "2410.00037v1"

    # Query for H-Net Dynamic Chunking (Paper 3)
    results_h = engine.search("H-Net dynamic chunking eliminates BPE", setting="B", top_k=3)
    assert len(results_h) > 0
    top_h = results_h[0].chunk
    assert top_h.paper_id == "2507.07955v2"

