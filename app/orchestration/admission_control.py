"""
Admission Control for THE RELAY.
Enforces multi-dimensional capacity constraints:
- RPM Token Bucket
- TPM Token Bucket
- Daily Quota Tracking (RPD & TPD)
- Dynamic In-Flight Concurrency
- Queue Management & Priority Filtering
"""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple
from app.core.config import settings
from app.orchestration.concurrency_controller import AdaptiveConcurrencyController
from app.orchestration.queue_manager import RequestQueueManager

class AdmissionDecision(Enum):
    ADMIT = "ADMIT"
    QUEUE = "QUEUE"
    REJECT_RATE_LIMIT = "REJECT_RATE_LIMIT"
    REJECT_QUOTA_EXHAUSTED = "REJECT_QUOTA_EXHAUSTED"
    REJECT_QUEUE_FULL = "REJECT_QUEUE_FULL"

@dataclass
class TokenBucket:
    capacity: float
    refill_rate_per_sec: float
    current_tokens: float
    last_update: float

    def consume(self, amount: float) -> bool:
        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now
        self.current_tokens = min(self.capacity, self.current_tokens + (elapsed * self.refill_rate_per_sec))

        if self.current_tokens >= amount:
            self.current_tokens -= amount
            return True
        return False

    def time_until_available(self, amount: float) -> float:
        if self.current_tokens >= amount:
            return 0.0
        needed = amount - self.current_tokens
        return needed / max(self.refill_rate_per_sec, 0.001)

class AdmissionController:
    def __init__(
        self,
        rpm: int = 30,
        tpm: int = 6000,
        rpd: int = 14400,
        tpd: int = 500000,
        max_concurrent: int = 4,
        queue_capacity: int = 50
    ):
        now = time.time()
        self.rpm = rpm
        self.tpm = tpm
        self.rpd = rpd
        self.tpd = tpd

        # Local Token Buckets
        self.rpm_bucket = TokenBucket(
            capacity=float(rpm),
            refill_rate_per_sec=float(rpm) / 60.0,
            current_tokens=float(rpm),
            last_update=now
        )
        self.tpm_bucket = TokenBucket(
            capacity=float(tpm),
            refill_rate_per_sec=float(tpm) / 60.0,
            current_tokens=float(tpm),
            last_update=now
        )

        # Daily Quota Trackers
        self.daily_requests_consumed = 0
        self.daily_tokens_consumed = 0
        self.day_start_timestamp = now

        # Active In-Flight Tracking & Adaptive Concurrency
        self.active_in_flight = 0
        self.concurrency_controller = AdaptiveConcurrencyController(
            min_concurrency=settings.min_concurrency,
            max_concurrency=settings.max_concurrency,
            target_latency_ms=settings.latency_threshold_p90_ms
        )
        self.queue_manager = RequestQueueManager(max_capacity=queue_capacity)
        self._async_lock = None

    @property
    def lock(self) -> asyncio.Lock:
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock

    def _reset_daily_if_needed(self):
        now = time.time()
        if now - self.day_start_timestamp >= 86400.0:
            self.day_start_timestamp = now
            self.daily_requests_consumed = 0
            self.daily_tokens_consumed = 0

    async def evaluate_request(
        self,
        estimated_tokens: int = 150,
        priority: int = 1
    ) -> Tuple[AdmissionDecision, Optional[str]]:
        """Evaluates whether to admit, queue, or reject an incoming request."""
        self._reset_daily_if_needed()

        # 1. Daily Quota Check
        if self.daily_requests_consumed >= self.rpd or (self.daily_tokens_consumed + estimated_tokens) > self.tpd:
            return (
                AdmissionDecision.REJECT_QUOTA_EXHAUSTED,
                "Daily quota exhausted. System cannot accept further requests until the 24-hour cycle resets."
            )

        # 2. Concurrency Check
        allowed_concurrency = self.concurrency_controller.limit
        async with self.lock:
            if self.active_in_flight >= allowed_concurrency:
                if self.queue_manager.qsize >= self.queue_manager.max_capacity:
                    return (
                        AdmissionDecision.REJECT_QUEUE_FULL,
                        f"Active capacity ({self.active_in_flight}) and queue ({self.queue_manager.qsize}) saturated."
                    )
                return (AdmissionDecision.QUEUE, "Queued due to concurrency saturation.")

        # 3. Rate Limit Bucket Check
        rpm_ok = self.rpm_bucket.consume(1.0)
        tpm_ok = self.tpm_bucket.consume(float(estimated_tokens))

        if not (rpm_ok and tpm_ok):
            wait_s = max(
                self.rpm_bucket.time_until_available(1.0),
                self.tpm_bucket.time_until_available(float(estimated_tokens))
            )
            return (
                AdmissionDecision.REJECT_RATE_LIMIT,
                f"Per-minute capacity exhausted. Estimated backoff required: {wait_s:.1f}s."
            )

        return (AdmissionDecision.ADMIT, None)

    async def acquire_slot(self):
        async with self.lock:
            self.active_in_flight += 1
            self.daily_requests_consumed += 1

    async def release_slot(self, actual_tokens: int = 0):
        async with self.lock:
            self.active_in_flight = max(0, self.active_in_flight - 1)
            self.daily_tokens_consumed += actual_tokens

