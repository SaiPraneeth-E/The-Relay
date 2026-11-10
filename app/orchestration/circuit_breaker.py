"""
Circuit Breaker Implementation for THE RELAY.
States:
- CLOSED: Standard operation, requests flow through.
- OPEN: Failure threshold breached, requests fail fast without calling provider.
- HALF_OPEN: Recovery timer elapsed, permits limited test probes.
"""

import time
from enum import Enum
from typing import Optional

class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_sec: float = 20.0,
        half_open_probes: int = 2
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.half_open_probes = half_open_probes

        self.state: CircuitState = CircuitState.CLOSED
        self.consecutive_failures: int = 0
        self.last_state_change: float = time.time()
        self.half_open_successes: int = 0

    def can_execute(self) -> bool:
        """Determines if a request can be dispatched to the provider."""
        now = time.time()
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if now - self.last_state_change >= self.recovery_timeout_sec:
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = now
                self.half_open_successes = 0
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            # Allow limited recovery probe
            return True

        return False

    def record_success(self):
        """Records a successful operation."""
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_successes += 1
            if self.half_open_successes >= self.half_open_probes:
                self.state = CircuitState.CLOSED
                self.consecutive_failures = 0
                self.last_state_change = time.time()
        elif self.state == CircuitState.CLOSED:
            self.consecutive_failures = 0

    def record_failure(self):
        """Records a failed operation."""
        now = time.time()
        self.consecutive_failures += 1

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.last_state_change = now
        elif self.state == CircuitState.CLOSED and self.consecutive_failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.last_state_change = now

