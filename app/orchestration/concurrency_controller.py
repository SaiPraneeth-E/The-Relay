"""
Adaptive Concurrency Controller for THE RELAY.
Implements Additive Increase / Multiplicative Decrease (AIMD) based on observed latency and provider feedback.
"""

import time
from typing import List

class AdaptiveConcurrencyController:
    def __init__(
        self,
        min_concurrency: int = 1,
        max_concurrency: int = 8,
        target_latency_ms: float = 2000.0,
        increase_rate: float = 0.5,
        decrease_ratio: float = 0.5
    ):
        self.min_concurrency = min_concurrency
        self.max_concurrency = max_concurrency
        self.target_latency_ms = target_latency_ms
        self.increase_rate = increase_rate
        self.decrease_ratio = decrease_ratio

        self.current_concurrency: float = float(min(4, max_concurrency))
        self.recent_latencies: List[float] = []
        self.last_adjustment_time: float = time.time()
        self.cooldown_sec: float = 1.0

    @property
    def limit(self) -> int:
        return max(self.min_concurrency, int(round(self.current_concurrency)))

    def record_observation(self, latency_ms: float, is_rate_limited: bool = False, is_failure: bool = False):
        self.recent_latencies.append(latency_ms)
        if len(self.recent_latencies) > 20:
            self.recent_latencies.pop(0)

        now = time.time()
        if now - self.last_adjustment_time < self.cooldown_sec:
            return

        # Back off on rate limits or severe errors
        if is_rate_limited or is_failure:
            self.current_concurrency = max(
                float(self.min_concurrency),
                self.current_concurrency * self.decrease_ratio
            )
            self.last_adjustment_time = now
            return

        # Latency-guided AIMD
        if len(self.recent_latencies) >= 3:
            p90 = sorted(self.recent_latencies)[int(len(self.recent_latencies) * 0.9)]
            if p90 > self.target_latency_ms:
                self.current_concurrency = max(
                    float(self.min_concurrency),
                    self.current_concurrency * self.decrease_ratio
                )
            elif p90 < self.target_latency_ms * 0.7:
                self.current_concurrency = min(
                    float(self.max_concurrency),
                    self.current_concurrency + self.increase_rate
                )
            self.last_adjustment_time = now

