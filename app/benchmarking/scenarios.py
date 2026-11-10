"""
Benchmark Scenario Configurations for THE RELAY.
Covers all required load shapes: steady, burst, sustained overload, limit halved, daily exhausted.
"""

from dataclasses import dataclass
from typing import List, Literal, Optional

@dataclass
class ScenarioConfig:
    name: str
    num_requests: int
    inter_arrival_sec: float
    is_burst: bool
    burst_batch_size: int
    profile: Literal["normal", "high_latency", "unstable", "rate_limited", "daily_quota_exhausted", "overloaded"]
    source: Literal["real", "stand-in"]
    rpm_limit: int = 30
    tpm_limit: int = 6000
    retrieval_setting: Literal["A", "B", "C"] = "B"
    enable_retries: bool = True
    aggressive_retries: bool = False

BENCHMARK_SCENARIOS = {
    "steady": ScenarioConfig(
        name="steady",
        num_requests=20,
        inter_arrival_sec=1.8,
        is_burst=False,
        burst_batch_size=1,
        profile="normal",
        source="stand-in",
        rpm_limit=30,
        tpm_limit=6000,
        retrieval_setting="B"
    ),
    "burst": ScenarioConfig(
        name="burst",
        num_requests=25,
        inter_arrival_sec=0.05,
        is_burst=True,
        burst_batch_size=12,
        profile="normal",
        source="stand-in",
        rpm_limit=30,
        tpm_limit=6000,
        retrieval_setting="B"
    ),
    "sustained_overload": ScenarioConfig(
        name="sustained_overload",
        num_requests=35,
        inter_arrival_sec=0.4,
        is_burst=False,
        burst_batch_size=1,
        profile="overloaded",
        source="stand-in",
        rpm_limit=30,
        tpm_limit=6000,
        retrieval_setting="B"
    ),
    "per_minute_limit_halved": ScenarioConfig(
        name="per_minute_limit_halved",
        num_requests=25,
        inter_arrival_sec=0.8,
        is_burst=False,
        burst_batch_size=1,
        profile="rate_limited",
        source="stand-in",
        rpm_limit=15,  # Halved limit
        tpm_limit=3000,
        retrieval_setting="B"
    ),
    "daily_budget_exhausted": ScenarioConfig(
        name="daily_budget_exhausted",
        num_requests=20,
        inter_arrival_sec=0.5,
        is_burst=False,
        burst_batch_size=1,
        profile="daily_quota_exhausted",
        source="stand-in",
        rpm_limit=30,
        tpm_limit=6000,
        retrieval_setting="B"
    ),
    # Additional scenario proving retries increase congestion under load
    "retry_congestion_uncontrolled": ScenarioConfig(
        name="retry_congestion_uncontrolled",
        num_requests=30,
        inter_arrival_sec=0.3,
        is_burst=False,
        burst_batch_size=1,
        profile="overloaded",
        source="stand-in",
        rpm_limit=20,
        tpm_limit=4000,
        retrieval_setting="B",
        aggressive_retries=True
    )
}

