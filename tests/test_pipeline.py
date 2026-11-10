"""
Tests for Pipeline: Request Understanding, Tool Execution, Generation, Verification, Refusals.
"""

import asyncio
import pytest
from app.pipeline.request_understanding import RequestUnderstandingEngine
from app.pipeline.orchestrator import RelayOrchestrator
from app.providers.simulator_provider import StandInSimulatorProvider
from app.tools.research_tools import ResearchToolRegistry
from app.verification.citation_checker import CitationChecker
from app.verification.answer_validator import AnswerValidator

def test_request_understanding_classification():
    # Out of domain
    analysis_ood = RequestUnderstandingEngine.analyze("What is the weather in Tokyo?")
    assert analysis_ood.question_type == "unanswerable_out_of_domain"
    assert analysis_ood.recommended_retrieval_setting == "A"

    # Formula question
    analysis_math = RequestUnderstandingEngine.analyze("What is the formula for scaled dot-product attention?")
    assert analysis_math.question_type == "methodological"
    assert analysis_math.requires_tool is True
    assert analysis_math.tool_name == "verify_formula_context"

    # Comparative question
    analysis_comp = RequestUnderstandingEngine.analyze("Compare the latency of Moshi versus traditional cascades.")
    assert analysis_comp.question_type == "comparative"
    assert analysis_comp.complexity == "high"

def test_research_tools():
    res_formula = ResearchToolRegistry.verify_formula_context("scaled_dot_product_attention")
    assert res_formula["status"] == "found"
    assert "softmax" in res_formula["formula"]["equation"]

    res_table = ResearchToolRegistry.cross_reference_tables("moshi_latency")
    assert res_table["status"] == "found"
    assert res_table["benchmark"]["metrics"]["theoretical_latency_ms"] == 160.0

def test_citation_checker():
    # Valid cited text
    cited_text = "According to Attention Is All You Need (arXiv:1706.03762v7, Section 3.2.1), attention is scaled."
    check = CitationChecker.validate(cited_text, retrieved_chunks=[])
    assert check.has_valid_citations is True
    assert "1706.03762v7" in check.cited_ids

    # Uncited / Hallucinated text
    uncited_text = "Transformers are neural models that use deep layers without recurrence."
    check_bad = CitationChecker.validate(uncited_text, retrieved_chunks=[])
    assert check_bad.has_valid_citations is False

def test_full_pipeline_factual_query():
    async def _run():
        provider = StandInSimulatorProvider(profile="normal", seed=42)
        orchestrator = RelayOrchestrator(provider=provider)
        await orchestrator.initialize()

        resp, trace, val = await orchestrator.process_request(
            query="What is the formula for scaled dot product attention in Attention Is All You Need?",
            scenario="test"
        )

        assert resp.status_code == 200
        assert trace.status == "ok"
        assert val.grade == "correct"
        assert "Attention(Q, K, V)" in resp.content
        assert trace.first_token_ms > 0
        assert trace.total_ms >= trace.first_token_ms

    asyncio.run(_run())

def test_full_pipeline_refusal_behavior():
    async def _run():
        provider = StandInSimulatorProvider(profile="normal", seed=42)
        orchestrator = RelayOrchestrator(provider=provider)
        await orchestrator.initialize()

        resp, trace, val = await orchestrator.process_request(
            query="What is the average solar radiation index in Tokyo?",
            scenario="test_refusal"
        )

        assert resp.status_code == 200
        assert val.grade == "refused_correctly"
        assert "does not provide sufficient information" in resp.content.lower()

    asyncio.run(_run())
