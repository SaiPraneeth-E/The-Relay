"""
Tests for Orchestration: Admission Control, Concurrency, Circuit Breaker, Retries, Queue Abandonment.
"""

import asyncio
import time
import pytest
from app.orchestration.admission_control import AdmissionController, AdmissionDecision, TokenBucket
from app.orchestration.circuit_breaker import CircuitBreaker, CircuitState
from app.orchestration.concurrency_controller import AdaptiveConcurrencyController
from app.orchestration.queue_manager import RequestQueueManager, QueuedItem
from app.orchestration.retry_manager import RetryManager
from app.providers.base import ProviderResponse

def test_token_bucket_rate_limiting():
    bucket = TokenBucket(capacity=5.0, refill_rate_per_sec=1.0, current_tokens=5.0, last_update=time.time())
    assert bucket.consume(3.0) is True
    assert bucket.consume(2.0) is True
    assert bucket.consume(1.0) is False  # Exhausted

def test_circuit_breaker_transitions():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_sec=0.2, half_open_probes=1)
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True

    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False

    # Wait for recovery timeout
    time.sleep(0.25)
    assert cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_success()
    assert cb.state == CircuitState.CLOSED

def test_adaptive_concurrency_controller_aimd():
    ctrl = AdaptiveConcurrencyController(min_concurrency=1, max_concurrency=6, target_latency_ms=1000.0)
    initial = ctrl.limit

    # Fast responses increase concurrency
    ctrl.record_observation(latency_ms=400.0)
    ctrl.last_adjustment_time = 0.0  # Bypass cooldown
    ctrl.record_observation(latency_ms=450.0)
    ctrl.last_adjustment_time = 0.0
    ctrl.record_observation(latency_ms=500.0)
    assert ctrl.limit >= initial

    # Rate limit causes multiplicative backoff
    ctrl.record_observation(latency_ms=2800.0, is_rate_limited=True)
    assert ctrl.limit <= initial

def test_retry_manager_budget_and_classification():
    rm = RetryManager(max_retries=3, retry_budget_ratio=0.20)

    # 400 is not retryable
    resp_400 = ProviderResponse(content="", status_code=400)
    assert rm.should_retry(attempt=0, response=resp_400) is False

    # 503 is retryable
    resp_503 = ProviderResponse(content="", status_code=503)
    assert rm.should_retry(attempt=0, response=resp_503) is True

    # Exceeding max retries
    assert rm.should_retry(attempt=3, response=resp_503) is False

def test_queue_item_ttl_and_abandonment():
    qm = RequestQueueManager(max_capacity=10, default_ttl_sec=0.01)
    # Simulate an expired item that arrived in the past
    item_expired = QueuedItem(
        priority=1,
        arrival_time=time.time() - 2.0,
        ttl_seconds=0.1,
        request_id="req_expired",
        payload="data"
    )
    assert item_expired.is_expired() is True

    # Fresh item
    item_fresh = QueuedItem(
        priority=1,
        arrival_time=time.time(),
        ttl_seconds=10.0,
        request_id="req_fresh",
        payload="data"
    )
    assert item_fresh.is_expired() is False
