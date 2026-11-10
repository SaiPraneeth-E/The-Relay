"""
Intelligent Retry Manager for THE RELAY.
Implements exponential backoff with full jitter, retry budgets, and permanent vs transient classification.
"""

import random
import time
from typing import Optional
from app.providers.base import ProviderResponse

class RetryManager:
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 8.0,
        retry_budget_ratio: float = 0.20
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.retry_budget_ratio = retry_budget_ratio

        self.total_requests = 0
        self.total_retries = 0

    def should_retry(
        self,
        attempt: int,
        response: ProviderResponse,
        enable_budget: bool = True
    ) -> bool:
        """Determines whether a failed request is eligible for retry."""
        if attempt >= self.max_retries:
            return False

        # Non-retryable HTTP status codes
        if response.status_code in (400, 401, 403, 404):
            return False

        # Do not retry daily quota exhaustion
        if response.status_code == 429 and response.retry_after_s and response.retry_after_s > 300:
            return False

        # Check retry budget (preventing retry storms)
        if enable_budget and self.total_requests > 10:
            current_ratio = self.total_retries / max(1, self.total_requests)
            if current_ratio > self.retry_budget_ratio:
                return False

        # 429 (per-minute), 500, 502, 503, 504, 408 are retryable
        if response.status_code in (429, 500, 502, 503, 504, 408) or response.rate_limited:
            return True

        return False

    def compute_backoff(self, attempt: int, response: Optional[ProviderResponse] = None) -> float:
        """Calculates backoff delay using Full Jitter or Retry-After."""
        if response and response.retry_after_s and response.retry_after_s > 0:
            # Respect server Retry-After plus a slight random jitter
            return response.retry_after_s + random.uniform(0.1, 0.5)

        # Full jitter: sleep = Uniform(0, min(max_delay, base * 2^attempt))
        upper_bound = min(self.max_delay, self.base_delay * (2 ** attempt))
        return random.uniform(0.1, upper_bound)

    def record_request(self):
        self.total_requests += 1

    def record_retry(self):
        self.total_retries += 1

