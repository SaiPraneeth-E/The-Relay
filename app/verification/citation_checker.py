"""
Stage 6: Independent Citation Checker for THE RELAY.
Validates that citations refer strictly to the exact three-paper library and align with retrieved chunks.
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple
from app.retrieval.chunking import TextChunk

ALLOWED_ARXIV_IDS = {"1706.03762", "2410.00037", "2507.07955"}
ALLOWED_VERSIONS = {"1706.03762v7", "2410.00037v1", "2507.07955v2"}

@dataclass
class CitationValidationResult:
    has_valid_citations: bool
    cited_ids: List[str] = field(default_factory=list)
    has_page_or_section: bool = False
    is_refusal: bool = False
    details: str = ""

class CitationChecker:
    @staticmethod
    def validate(response_text: str, retrieved_chunks: List[TextChunk]) -> CitationValidationResult:
        text_lower = response_text.lower()

        # Check if response is a valid refusal
        is_refusal = any(
            phrase in text_lower
            for phrase in [
                "does not provide sufficient information",
                "not covered in the research library",
                "outside the scope",
                "strictly limited to"
            ]
        )
        if is_refusal:
            return CitationValidationResult(
                has_valid_citations=True,
                is_refusal=True,
                details="Legitimate evidence-based refusal."
            )

        # Detect arXiv citations
        found_arxiv = re.findall(r"(?:arxiv:?\s*)?([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)", text_lower)
        cited_allowed = []
        for aid in found_arxiv:
            base_id = aid.split("v")[0]
            if base_id in ALLOWED_ARXIV_IDS or aid in ALLOWED_VERSIONS:
                cited_allowed.append(aid)

        has_section = bool(re.search(r"\b(section|sec\.|page|p\.)\s+[0-9]+", text_lower))

        # Check if citations match retrieved evidence
        retrieved_paper_ids = {c.paper_id for c in retrieved_chunks}
        matches_retrieved = any(
            any(pid.startswith(c) for pid in retrieved_paper_ids)
            for c in cited_allowed
        ) if cited_allowed else False

        is_valid = bool(cited_allowed and (has_section or matches_retrieved))

        return CitationValidationResult(
            has_valid_citations=is_valid,
            cited_ids=cited_allowed,
            has_page_or_section=has_section,
            is_refusal=False,
            details=f"Found citations: {cited_allowed}, Has section/page: {has_section}"
        )

