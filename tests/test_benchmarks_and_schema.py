"""
Tests for Benchmark Metrics, Schema Conformance, and CSV Serialization.
"""

import csv
import io
import pytest
from app.benchmarking.metrics import (
    RESULTS_CSV_HEADERS,
    BenchmarkRecord,
    compute_percentiles,
    compute_scenario_metrics
)

def test_results_csv_schema_conformance():
    expected_columns = [
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
    assert RESULTS_CSV_HEADERS == expected_columns

    rec = BenchmarkRecord(
        request_id="req_001",
        scenario="steady",
        source="stand-in",
        start_time="2026-11-10T12:00:00Z",
        first_token_ms=250.5,
        total_ms=580.2,
        status="ok",
        retries=0,
        tokens_in=120,
        tokens_out=85,
        retrieval_setting="B",
        answer_grade="correct"
    )

    row = rec.to_csv_row()
    assert list(row.keys()) == expected_columns
    assert row["source"] in ("real", "stand-in")
    assert row["status"] in ("ok", "rate_limited", "timeout", "error")
    assert row["answer_grade"] in ("correct", "wrong", "refused_correctly", "refused_wrongly")

def test_percentile_calculations():
    values = [100.0, 200.0, 300.0, 400.0, 500.0]
    p50, p95, p99 = compute_percentiles(values)
    assert p50 == 300.0
    assert p95 > 400.0
    assert p99 <= 500.0

def test_compute_scenario_metrics():
    records = [
        BenchmarkRecord("r1", "test", "stand-in", "t1", 200.0, 500.0, "ok", 0, 100, 50, "B", "correct"),
        BenchmarkRecord("r2", "test", "stand-in", "t2", 220.0, 550.0, "ok", 1, 100, 50, "B", "correct"),
        BenchmarkRecord("r3", "test", "stand-in", "t3", 0.0, 120.0, "rate_limited", 0, 100, 0, "B", "refused_correctly"),
    ]
    metrics = compute_scenario_metrics(records, "test", duration_s=10.0, peak_queue_len=2)
    assert metrics["requests_sent"] == 3
    assert metrics["succeeded_pct"] == 66.7
    assert metrics["rate_limited_pct"] == 33.3
    assert metrics["timed_out_pct"] == 0.0
    assert metrics["retries_per_req"] == 0.33
    assert metrics["peak_queue_len"] == 2

