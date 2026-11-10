"""
Chunking strategies for THE RELAY:
- Setting A: Small chunks (250 tokens / ~1000 chars, 30-token overlap)
- Setting B: Medium chunks (500 tokens / ~2000 chars, 50-token overlap)
- Setting C: Large chunks (1000 tokens / ~4000 chars, 100-token overlap)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Literal
from app.retrieval.ingestion import DocumentLibrary, ExtractedPage

@dataclass
class TextChunk:
    chunk_id: str
    paper_id: str
    paper_title: str
    arxiv_id: str
    version: int
    page_number: int
    section_title: str
    text: str
    token_estimate: int
    setting: str

CHUNK_CONFIGS = {
    "A": {
        "target_tokens": 250,
        "overlap_tokens": 30,
        "target_chars": 1000,
        "overlap_chars": 120,
        "top_k": 3,
        "rerank": False
    },
    "B": {
        "target_tokens": 500,
        "overlap_tokens": 50,
        "target_chars": 2000,
        "overlap_chars": 200,
        "top_k": 5,
        "rerank": False
    },
    "C": {
        "target_tokens": 1000,
        "overlap_tokens": 100,
        "target_chars": 4000,
        "overlap_chars": 400,
        "top_k": 8,
        "rerank": True
    }
}

def estimate_tokens(text: str) -> int:
    """Accurate word-to-token ratio approximation (~1.33 tokens per word)."""
    words = text.split()
    return max(1, int(len(words) * 1.33))

def chunk_document_library(
    doc_library: DocumentLibrary,
    setting: Literal["A", "B", "C"] = "B"
) -> List[TextChunk]:
    """Slices documents into overlapping chunks with preserved metadata."""
    cfg = CHUNK_CONFIGS[setting]
    target_chars = cfg["target_chars"]
    overlap_chars = cfg["overlap_chars"]

    chunks: List[TextChunk] = []

    for paper_id, pages in doc_library.papers.items():
        for page in pages:
            text = page.text
            if not text:
                continue

            section_name = page.sections[0] if page.sections else "General"
            text_len = len(text)
            start = 0
            chunk_num = 1

            while start < text_len:
                end = min(start + target_chars, text_len)

                # Try to break on a sentence or paragraph boundary
                if end < text_len:
                    last_period = text.rfind(". ", start, end)
                    last_newline = text.rfind("\n", start, end)
                    boundary = max(last_period, last_newline)
                    if boundary > start + (target_chars // 2):
                        end = boundary + 1

                chunk_text = text[start:end].strip()
                if len(chunk_text) > 40:  # Ignore tiny slivers
                    chunk_id = f"{paper_id}_p{page.page_number}_c{chunk_num}_{setting}"
                    chunks.append(
                        TextChunk(
                            chunk_id=chunk_id,
                            paper_id=page.paper_id,
                            paper_title=page.paper_title,
                            arxiv_id=page.arxiv_id,
                            version=page.version,
                            page_number=page.page_number,
                            section_title=section_name,
                            text=chunk_text,
                            token_estimate=estimate_tokens(chunk_text),
                            setting=setting
                        )
                    )
                    chunk_num += 1

                if end >= text_len:
                    break
                start = max(start + 1, end - overlap_chars)

    return chunks

