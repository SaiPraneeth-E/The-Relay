"""
Stage 6: Independent Answer Validator for THE RELAY.
Audits answer consistency, verifies absence of hallucinations, and checks required refusals.
"""

import re
from dataclasses import dataclass
from typing import List, Literal, Optional
from app.pipeline.request_understanding import RequestAnalysis
from app.retrieval.chunking import TextChunk
from app.verification.citation_checker import CitationChecker

AnswerGrade = Literal["correct", "wrong", "refused_correctly", "refused_wrongly"]

@dataclass
class ValidationReport:
    grade: AnswerGrade
    is_valid: bool
    consistency_score: float
    citation_valid: bool
    refusal_appropriate: bool
    reason: str
    suggests_correction: bool = False

class AnswerValidator:
    @staticmethod
    def audit(
        analysis: RequestAnalysis,
        response_text: str,
        retrieved_chunks: List[TextChunk]
    ) -> ValidationReport:
        citation_check = CitationChecker.validate(response_text, retrieved_chunks)
        text_lower = response_text.lower()
        is_refusal = citation_check.is_refusal

        # 1. Evaluate out-of-domain / unanswerable questions
        if analysis.question_type == "unanswerable_out_of_domain":
            if is_refusal:
                return ValidationReport(
                    grade="refused_correctly",
                    is_valid=True,
                    consistency_score=1.0,
                    citation_valid=True,
                    refusal_appropriate=True,
                    reason="Correctly refused out-of-domain question."
                )
            else:
                return ValidationReport(
                    grade="wrong",
                    is_valid=False,
                    consistency_score=0.2,
                    citation_valid=False,
                    refusal_appropriate=False,
                    reason="Failed to refuse an unanswerable question; fabricated out-of-domain facts.",
                    suggests_correction=True
                )

        # 2. In-domain question that was refused
        if is_refusal and analysis.question_type != "unanswerable_out_of_domain":
            # If retrieved chunks actually had zero relevance, refusal might be correct
            if len(retrieved_chunks) == 0:
                return ValidationReport(
                    grade="refused_correctly",
                    is_valid=True,
                    consistency_score=0.9,
                    citation_valid=True,
                    refusal_appropriate=True,
                    reason="No relevant evidence was retrieved; refused appropriately."
                )
            else:
                return ValidationReport(
                    grade="refused_wrongly",
                    is_valid=False,
                    consistency_score=0.4,
                    citation_valid=True,
                    refusal_appropriate=False,
                    reason="Refused to answer despite relevant evidence existing in retrieved library chunks.",
                    suggests_correction=True
                )

        # 3. Groundedness / Consistency check
        # Compute technical term overlap between response and retrieved chunk corpus
        chunk_corpus = " ".join(c.text.lower() for c in retrieved_chunks)
        chunk_words = set(re.findall(r"\b[a-z0-9_\-]{3,}\b", chunk_corpus))
        raw_words = re.findall(r"\b[a-z0-9_\-]{3,}\b", text_lower)
        # Filter boilerplate citation tokens so we measure genuine factual vocabulary
        boilerplate = {"arxiv", "version", "section", "page", "table", "paper", "need", "according"}
        content_words = [w for w in raw_words if w not in boilerplate]

        matches = sum(1 for w in content_words if w in chunk_words)
        overlap_ratio = matches / max(1, len(content_words))

        # Check for citation validity
        if not citation_check.has_valid_citations:
            return ValidationReport(
                grade="wrong",
                is_valid=False,
                consistency_score=min(overlap_ratio, 0.4),
                citation_valid=False,
                refusal_appropriate=True,
                reason="Lacks valid arXiv or paper section citation.",
                suggests_correction=True
            )

        if overlap_ratio >= 0.40:
            return ValidationReport(
                grade="correct",
                is_valid=True,
                consistency_score=round(overlap_ratio, 2),
                citation_valid=True,
                refusal_appropriate=True,
                reason="Answer is factually grounded in retrieved paper evidence with valid citations."
            )
        else:
            return ValidationReport(
                grade="wrong",
                is_valid=False,
                consistency_score=round(overlap_ratio, 2),
                citation_valid=True,
                refusal_appropriate=True,
                reason=f"Insufficient textual grounding in retrieved chunks (overlap={overlap_ratio:.2f}).",
                suggests_correction=True
            )

