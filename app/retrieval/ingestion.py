"""
PDF Ingestion and Section-Aware Extraction for THE RELAY Research Library.
"""

import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional
import fitz  # PyMuPDF

PAPERS_METADATA = {
    "1706.03762v7": {
        "id": "1706.03762v7",
        "arxiv_id": "1706.03762",
        "version": 7,
        "title": "Attention Is All You Need",
        "authors": "Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Lukasz Kaiser, Illia Polosukhin",
        "filename": "1706.03762v7_Attention_Is_All_You_Need.pdf"
    },
    "2410.00037v1": {
        "id": "2410.00037v1",
        "arxiv_id": "2410.00037",
        "version": 1,
        "title": "Moshi: a speech-text foundation model for real-time dialogue",
        "authors": "Alexandre Défossez, Laurent Mazaré, Manu Orsini, Amélie Royer, Patrick Pérez, Hervé Jégou, Edouard Grave, Neil Zeghidour",
        "filename": "2410.00037v1_Moshi_Speech_Text_Foundation_Model.pdf"
    },
    "2507.07955v2": {
        "id": "2507.07955v2",
        "arxiv_id": "2507.07955",
        "version": 2,
        "title": "Dynamic Chunking for End-to-End Hierarchical Sequence Modeling",
        "authors": "Sukjun Hwang, Brandon Wang, Albert Gu",
        "filename": "2507.07955v2_Dynamic_Chunking_Hierarchical_Sequence_Modeling.pdf"
    }
}

SECTION_HEADING_REGEX = re.compile(
    r"^([0-9]+(\.[0-9]+)*\s+[A-Z][A-Za-z0-9\s\-_,:]{2,60}|Abstract|References|Conclusion|Discussion|Appendix.*)$",
    re.MULTILINE
)

@dataclass
class ExtractedPage:
    paper_id: str
    paper_title: str
    arxiv_id: str
    version: int
    page_number: int
    text: str
    sections: List[str]

@dataclass
class DocumentLibrary:
    papers: Dict[str, List[ExtractedPage]]

def clean_extracted_text(text: str) -> str:
    """Removes hyphenation artifacts and standardizes whitespace."""
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def extract_sections_from_page(text: str) -> List[str]:
    """Detects section titles and headings on a page."""
    sections = []
    lines = text.split("\n")
    for line in lines:
        line_clean = line.strip()
        if SECTION_HEADING_REGEX.match(line_clean) and len(line_clean) < 65:
            sections.append(line_clean)
    return sections

def ingest_papers(papers_dir: Optional[Path] = None) -> DocumentLibrary:
    """Parses all three arXiv PDFs and returns structured extracted pages."""
    if papers_dir is None:
        papers_dir = Path("data/papers")

    doc_library: Dict[str, List[ExtractedPage]] = {}

    for paper_key, meta in PAPERS_METADATA.items():
        pdf_path = papers_dir / meta["filename"]
        if not pdf_path.exists():
            raise FileNotFoundError(f"Missing required paper PDF: {pdf_path}. Run download_papers.py first.")

        doc = fitz.open(str(pdf_path))
        extracted_pages: List[ExtractedPage] = []
        current_section = "Abstract"

        for page_idx in range(len(doc)):
            page_num = page_idx + 1
            raw_text = doc[page_idx].get_text("text")
            cleaned_text = clean_extracted_text(raw_text)
            detected_sections = extract_sections_from_page(cleaned_text)

            if detected_sections:
                current_section = detected_sections[-1]

            extracted_pages.append(
                ExtractedPage(
                    paper_id=meta["id"],
                    paper_title=meta["title"],
                    arxiv_id=meta["arxiv_id"],
                    version=meta["version"],
                    page_number=page_num,
                    text=cleaned_text,
                    sections=detected_sections if detected_sections else [current_section]
                )
            )

        doc_library[paper_key] = extracted_pages

    return DocumentLibrary(papers=doc_library)

