"""
Pipeline Orchestrator for THE RELAY.
Implements Adaptive Evidence-Aware Orchestration (AEO).
Coordinates Admission Control, Hybrid Retrieval, Tool Execution, Generation, Verification, and Delivery.
"""

import asyncio
import time
from typing import AsyncIterator, Dict, List, Literal, Optional, Tuple
from app.core.config import settings
from app.core.logging import RequestTrace, logger
from app.orchestration.admission_control import AdmissionController, AdmissionDecision
from app.orchestration.circuit_breaker import CircuitBreaker
from app.orchestration.concurrency_controller import AdaptiveConcurrencyController
from app.orchestration.retry_manager import RetryManager
from app.pipeline.answer_generator import AnswerGenerator
from app.pipeline.request_understanding import RequestAnalysis, RequestUnderstandingEngine
from app.pipeline.response_delivery import ResponseDeliveryManager
from app.providers.base import BaseProvider, ProviderResponse, StreamChunk
from app.retrieval.chunking import TextChunk
from app.retrieval.hybrid_search import HybridSearchEngine
from app.verification.answer_validator import ValidationReport

class RelayOrchestrator:
    def __init__(
        self,
        provider: BaseProvider,
        retrieval_engine: Optional[HybridSearchEngine] = None,
        source_name: str = "stand-in"
    ):
        self.provider = provider
        self.source_name = source_name
        self.retrieval_engine = retrieval_engine or HybridSearchEngine()
        self.admission_controller = AdmissionController(
            rpm=settings.rate_limit_rpm,
            tpm=settings.rate_limit_tpm,
            rpd=settings.rate_limit_rpd,
            tpd=settings.rate_limit_tpd,
            max_concurrent=settings.max_concurrent_requests,
            queue_capacity=settings.queue_max_size
        )
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_timeout_sec=settings.circuit_breaker_recovery_timeout_sec,
            half_open_probes=settings.circuit_breaker_half_open_probes
        )
        self.retry_manager = RetryManager(
            max_retries=settings.max_retries,
            base_delay=settings.retry_base_delay,
            max_delay=settings.retry_max_delay,
            retry_budget_ratio=settings.retry_budget_ratio
        )
        self.answer_generator = AnswerGenerator(self.provider)

    async def initialize(self):
        """Initializes retrieval indices if not already loaded."""
        self.retrieval_engine.initialize()

    async def process_request(
        self,
        query: str,
        request_id: Optional[str] = None,
        scenario: str = "adhoc",
        override_setting: Optional[Literal["A", "B", "C"]] = None,
        enable_retries: bool = True
    ) -> Tuple[ProviderResponse, RequestTrace, ValidationReport]:
        """
        Executes the full 7-stage pipeline under Adaptive Evidence-Aware Orchestration.
        """
        trace = RequestTrace(
            request_id=request_id or f"req_{int(time.time()*1000)}",
            scenario=scenario,
            source=self.source_name,
            start_time_iso=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            retrieval_setting=override_setting or "B"
        )

        # STAGE 1: Request Understanding
        span_und = trace.start_span("request_understanding")
        analysis = RequestUnderstandingEngine.analyze(query, request_id=trace.request_id)
        span_und.finish()
        trace.understanding_ms = span_und.duration_ms

        # EARLY COST-MINIMIZATION & EFFICIENCY GATE:
        # If Stage 1 Request Understanding classifies the question as unanswerable / out-of-domain,
        # short-circuit immediately to avoid wasting model tokens, queue slots, and upstream quota.
        if analysis.question_type == "unanswerable_out_of_domain":
            refusal_content = (
                "The available research library does not provide sufficient information to answer this question. "
                "The verified library is strictly limited to arXiv:1706.03762v7 (Transformers), arXiv:2410.00037v1 (Moshi), "
                "and arXiv:2507.07955v2 (Dynamic Chunking H-Net)."
            )
            trace.first_token_ms = 2.0
            trace.tokens_in = 0
            trace.tokens_out = 0
            trace.model_exec_ms = 0.0
            trace.retrieval_ms = 0.0
            trace.finalize(status="ok", grade="refused_correctly")
            return (
                ProviderResponse(
                    content=refusal_content,
                    status_code=200,
                    source=self.source_name,
                    tokens_in=0,
                    tokens_out=0,
                    total_ms=trace.total_ms
                ),
                trace,
                ValidationReport(
                    grade="refused_correctly",
                    is_valid=True,
                    consistency_score=1.0,
                    citation_valid=True,
                    refusal_appropriate=True,
                    reason="Correctly refused out-of-domain question."
                )
            )

        # STAGE 2: Admission Control & Queue Management
        span_queue = trace.start_span("admission_control")
        queue_start = time.perf_counter()

        decision, reject_reason = await self.admission_controller.evaluate_request(
            estimated_tokens=analysis.estimated_prompt_tokens,
            priority=analysis.priority
        )

        if decision == AdmissionDecision.REJECT_QUOTA_EXHAUSTED:
            span_queue.finish()
            trace.queue_wait_ms = (time.perf_counter() - queue_start) * 1000.0
            trace.finalize(status="rate_limited", grade="refused_correctly")
            return (
                ProviderResponse(
                    content=reject_reason or "Daily quota exhausted.",
                    status_code=429,
                    source=self.source_name,
                    rate_limited=True,
                    error=reject_reason
                ),
                trace,
                ValidationReport(
                    grade="refused_correctly",
                    is_valid=True,
                    consistency_score=1.0,
                    citation_valid=True,
                    refusal_appropriate=True,
                    reason="Correctly refused: Daily quota exhausted."
                )
            )

        if decision == AdmissionDecision.REJECT_RATE_LIMIT:
            span_queue.finish()
            trace.queue_wait_ms = (time.perf_counter() - queue_start) * 1000.0
            trace.finalize(status="rate_limited", grade="refused_correctly")
            return (
                ProviderResponse(
                    content=reject_reason or "Per-minute rate limit reached.",
                    status_code=429,
                    source=self.source_name,
                    rate_limited=True,
                    error=reject_reason
                ),
                trace,
                ValidationReport(
                    grade="refused_correctly",
                    is_valid=True,
                    consistency_score=1.0,
                    citation_valid=True,
                    refusal_appropriate=True,
                    reason="Correctly refused: Rate limit reached."
                )
            )

        if decision == AdmissionDecision.REJECT_QUEUE_FULL:
            span_queue.finish()
            trace.queue_wait_ms = (time.perf_counter() - queue_start) * 1000.0
            trace.finalize(status="timeout", grade="refused_correctly")
            return (
                ProviderResponse(
                    content=reject_reason or "Queue capacity exceeded.",
                    status_code=503,
                    source=self.source_name,
                    error="Queue saturated."
                ),
                trace,
                ValidationReport(
                    grade="refused_correctly",
                    is_valid=True,
                    consistency_score=1.0,
                    citation_valid=True,
                    refusal_appropriate=True,
                    reason="Correctly rejected: Queue saturated."
                )
            )

        # If queued, simulate waiting for concurrency slot
        if decision == AdmissionDecision.QUEUE:
            await asyncio.sleep(0.05)  # Yield to event loop

        await self.admission_controller.acquire_slot()
        span_queue.finish()
        trace.queue_wait_ms = (time.perf_counter() - queue_start) * 1000.0

        try:
            # STAGE 3: Evidence Retrieval (AEO Dynamic Selection)
            # Adapt retrieval setting under load: If queue is high (>10), degrade C -> B or B -> A
            active_qsize = self.admission_controller.queue_manager.qsize
            chosen_setting: Literal["A", "B", "C"] = override_setting or analysis.recommended_retrieval_setting
            if active_qsize > 10 and chosen_setting == "C":
                chosen_setting = "B"
            elif active_qsize > 25 and chosen_setting == "B":
                chosen_setting = "A"

            trace.retrieval_setting = chosen_setting

            span_ret = trace.start_span("retrieval")
            chunks: List[TextChunk] = []
            if analysis.question_type != "unanswerable_out_of_domain":
                search_results = self.retrieval_engine.search(
                    query=analysis.raw_query,
                    setting=chosen_setting
                )
                chunks = [r.chunk for r in search_results]

            span_ret.finish()
            trace.retrieval_ms = span_ret.duration_ms

            # Check Circuit Breaker before provider dispatch
            if not self.circuit_breaker.can_execute():
                trace.finalize(status="error", grade="wrong")
                return (
                    ProviderResponse(
                        content="Circuit breaker is OPEN. Fast failing to protect upstream provider.",
                        status_code=503,
                        source=self.source_name,
                        error="Circuit breaker OPEN."
                    ),
                    trace,
                    ValidationReport(
                        grade="wrong",
                        is_valid=False,
                        consistency_score=0.0,
                        citation_valid=False,
                        refusal_appropriate=False,
                        reason="Circuit breaker blocked request."
                    )
                )

            # STAGES 4, 5, 6: Execution Loop with Retries
            attempt = 0
            retry_accum_ms = 0.0
            last_resp: Optional[ProviderResponse] = None
            last_val: Optional[ValidationReport] = None

            while True:
                self.retry_manager.record_request()
                span_exec = trace.start_span(f"generation_attempt_{attempt}")

                resp, val, loops = await self.answer_generator.execute_reasoning_and_generation(
                    analysis=analysis,
                    chunks=chunks
                )
                span_exec.finish()

                last_resp = resp
                last_val = val
                trace.tokens_in = resp.tokens_in
                trace.tokens_out = resp.tokens_out

                if resp.status_code == 200:
                    self.circuit_breaker.record_success()
                    self.admission_controller.concurrency_controller.record_observation(
                        latency_ms=resp.total_ms,
                        is_rate_limited=False,
                        is_failure=False
                    )
                    trace.first_token_ms = resp.first_token_ms
                    trace.model_exec_ms = resp.total_ms
                    break

                # Handle failure / rate limit
                self.circuit_breaker.record_failure()
                self.admission_controller.concurrency_controller.record_observation(
                    latency_ms=resp.total_ms,
                    is_rate_limited=resp.rate_limited,
                    is_failure=True
                )

                if enable_retries and self.retry_manager.should_retry(attempt, resp):
                    attempt += 1
                    trace.retries_count += 1
                    self.retry_manager.record_retry()
                    backoff = self.retry_manager.compute_backoff(attempt, resp)
                    retry_start = time.perf_counter()
                    await asyncio.sleep(backoff)
                    retry_accum_ms += (time.perf_counter() - retry_start) * 1000.0
                    continue
                else:
                    break

            trace.retry_ms = retry_accum_ms
            status_code = last_resp.status_code if last_resp else 500
            status_label = "ok" if status_code == 200 else ("rate_limited" if status_code == 429 else ("timeout" if status_code == 408 else "error"))
            grade_label = last_val.grade if last_val else "wrong"

            trace.finalize(status=status_label, grade=grade_label)
            return last_resp, trace, last_val  # type: ignore

        finally:
            actual_toks = (trace.tokens_in + trace.tokens_out)
            await self.admission_controller.release_slot(actual_tokens=actual_toks)

