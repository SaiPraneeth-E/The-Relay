"""
Metrics calculation and CSV serialization for THE RELAY Benchmarks.
Strictly conforms to the required results.csv schema and computes Table 2a / 2b figures.
"""

import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple
import numpy as np

# Exact CSV column headers required by the assignment brief (Page 4)
RESULTS_CSV_HEADERS = [
    "request_id",
    "scenario",
    "source",
    "start_time",
    "first_token_ms",
    "total_ms",
    "status",
    "retries",
    "tokens_in",
    "tokens_out",
    "retrieval_setting",
    "answer_grade"
]

@dataclass
class BenchmarkRecord:
    request_id: str
    scenario: str
    source: Literal["real", "stand-in"]
    start_time: str
    first_token_ms: float
    total_ms: float
    status: Literal["ok", "rate_limited", "timeout", "error"]
    retries: int
    tokens_in: int
    tokens_out: int
    retrieval_setting: Literal["A", "B", "C"]
    answer_grade: Literal["correct", "wrong", "refused_correctly", "refused_wrongly"]

    def to_csv_row(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "scenario": self.scenario,
            "source": self.source,
            "start_time": self.start_time,
            "first_token_ms": round(self.first_token_ms, 1),
            "total_ms": round(self.total_ms, 1),
            "status": self.status,
            "retries": self.retries,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "retrieval_setting": self.retrieval_setting,
            "answer_grade": self.answer_grade
        }

def compute_percentiles(values: List[float]) -> Tuple[float, float, float]:
    """Returns (p50, p95, p99) in milliseconds."""
    if not values:
        return 0.0, 0.0, 0.0
    arr = np.array(values)
    p50 = float(np.percentile(arr, 50))
    p95 = float(np.percentile(arr, 95))
    p99 = float(np.percentile(arr, 99))
    return round(p50, 1), round(p95, 1), round(p99, 1)

def compute_scenario_metrics(
    records: List[BenchmarkRecord],
    scenario_name: str,
    duration_s: float,
    peak_queue_len: int = 0
) -> Dict[str, Any]:
    """Computes Table 2a and Table 2b columns strictly from request records."""
    if not records:
        return {}

    n = len(records)
    source = records[0].source
    first_tokens = [r.first_token_ms for r in records if r.first_token_ms > 0]
    total_times = [r.total_ms for r in records]

    ft_p50, ft_p95, ft_p99 = compute_percentiles(first_tokens)
    tt_p50, tt_p95, tt_p99 = compute_percentiles(total_times)

    ok_count = sum(1 for r in records if r.status == "ok")
    rate_limited_count = sum(1 for r in records if r.status == "rate_limited")
    timeout_count = sum(1 for r in records if r.status in ("timeout", "error"))

    success_pct = round((ok_count / n) * 100.0, 1)
    rate_limited_pct = round((rate_limited_count / n) * 100.0, 1)
    timeout_pct = round((timeout_count / n) * 100.0, 1)

    total_retries = sum(r.retries for r in records)
    retries_per_req = round(total_retries / n, 2)

    total_tokens_out = sum(r.tokens_out for r in records if r.status == "ok")
    avg_tokens_per_answer = round(total_tokens_out / max(1, ok_count), 1)

    # Cost model: Groq Llama 3.1 8B ($0.05/1M input, $0.08/1M output)
    total_in = sum(r.tokens_in for r in records)
    total_out = sum(r.tokens_out for r in records)
    cost_usd = ((total_in / 1_000_000.0) * 0.05) + ((total_out / 1_000_000.0) * 0.08)
    cost_per_1000 = round((cost_usd / max(1, ok_count)) * 1000.0, 4)

    offered_rate_per_min = round((n / max(0.1, duration_s)) * 60.0, 1)

    return {
        "scenario": scenario_name,
        "source": source,
        "requests_sent": n,
        "duration_s": round(duration_s, 1),
        "offered_rate_per_min": offered_rate_per_min,
        "first_token_p50": ft_p50,
        "first_token_p95": ft_p95,
        "first_token_p99": ft_p99,
        "total_time_p50": tt_p50,
        "total_time_p95": tt_p95,
        "total_time_p99": tt_p99,
        "succeeded_pct": success_pct,
        "rate_limited_pct": rate_limited_pct,
        "timed_out_pct": timeout_pct,
        "retries_per_req": retries_per_req,
        "peak_queue_len": peak_queue_len,
        "tokens_per_answer": avg_tokens_per_answer,
        "cost_per_1000": cost_per_1000
    }
