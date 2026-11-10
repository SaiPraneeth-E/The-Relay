"""
Structured logging and request-level waterfall tracing for THE RELAY.
"""

import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

class JsonFormatter(logging.Formatter):
    """Formats log records as structured JSON."""
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_obj.update(record.extra)
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)

def get_logger(name: str = "relay") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False
    return logger

logger = get_logger("relay")

@dataclass
class StageSpan:
    name: str
    start_time: float
    end_time: float = 0.0
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def finish(self, **meta):
        self.end_time = time.perf_counter()
        self.duration_ms = max(0.0, (self.end_time - self.start_time) * 1000.0)
        self.metadata.update(meta)
        return self

@dataclass
class RequestTrace:
    """Detailed waterfall trace for a single request lifecycle."""
    request_id: str
    scenario: str = "adhoc"
    source: str = "stand-in"
    start_time_iso: str = ""
    start_perf: float = field(default_factory=time.perf_counter)
    end_perf: float = 0.0

    # Key lifecycle milestones (in ms from request arrival)
    queue_wait_ms: float = 0.0
    understanding_ms: float = 0.0
    retrieval_ms: float = 0.0
    tool_exec_ms: float = 0.0
    model_exec_ms: float = 0.0
    first_token_ms: float = 0.0
    token_gen_ms: float = 0.0
    verification_ms: float = 0.0
    retry_ms: float = 0.0
    total_ms: float = 0.0

    retries_count: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    status: str = "ok"  # ok, rate_limited, timeout, error
    answer_grade: str = "correct"  # correct, wrong, refused_correctly, refused_wrongly
    retrieval_setting: str = "B"

    spans: List[StageSpan] = field(default_factory=list)
    delay_location: str = "unknown"  # "before_first_token", "during_generation", "none"

    def start_span(self, name: str) -> StageSpan:
        span = StageSpan(name=name, start_time=time.perf_counter())
        self.spans.append(span)
        return span

    def mark_first_token(self):
        if self.first_token_ms == 0.0:
            self.first_token_ms = max(0.0, (time.perf_counter() - self.start_perf) * 1000.0)

    def finalize(self, status: Optional[str] = None, grade: Optional[str] = None):
        self.end_perf = time.perf_counter()
        self.total_ms = max(0.0, (self.end_perf - self.start_perf) * 1000.0)
        if status:
            self.status = status
        if grade:
            self.answer_grade = grade

        # Token generation duration
        if self.first_token_ms > 0:
            self.token_gen_ms = max(0.0, self.total_ms - self.first_token_ms)

        # Classify delay locus
        if self.total_ms > 2000.0:
            if self.first_token_ms > (self.total_ms * 0.6):
                self.delay_location = "before_first_token (queue/retrieval/provider TTFT)"
            else:
                self.delay_location = "after_first_token (token streaming/verification)"
        else:
            self.delay_location = "normal_latency"

    def render_waterfall(self) -> str:
        """Render an informative ASCII terminal waterfall trace."""
        lines = [
            f"=== REQUEST TRACE WATERFALL: {self.request_id} ===",
            f"Scenario: {self.scenario} | Source: {self.source} | Setting: {self.retrieval_setting}",
            f"Status: {self.status} | Grade: {self.answer_grade} | Retries: {self.retries_count}",
            f"Tokens: In={self.tokens_in}, Out={self.tokens_out} | Total: {self.total_ms:.1f} ms",
            f"Delay Locus: {self.delay_location}",
            "-" * 60,
        ]
        total = max(self.total_ms, 1.0)
        stages = [
            ("Queue Wait", self.queue_wait_ms),
            ("Understanding", self.understanding_ms),
            ("Retrieval", self.retrieval_ms),
            ("Tool Execution", self.tool_exec_ms),
            ("First Token (TTFT)", self.first_token_ms),
            ("Token Gen Streaming", self.token_gen_ms),
            ("Verification", self.verification_ms),
            ("Retries", self.retry_ms),
        ]
        for name, dur in stages:
            pct = (dur / total) * 100.0
            bar_len = int(pct / 2.5)
            bar = "#" * bar_len
            lines.append(f"  {name:<22} | {dur:>7.1f} ms | {pct:>5.1f}% | {bar}")
        lines.append("=" * 60)
        return "\n".join(lines)

