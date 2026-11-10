"""
Core configuration settings for THE RELAY pipeline.
"""

import os
from pathlib import Path
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    # Base paths
    base_dir: Path = BASE_DIR
    data_dir: Path = BASE_DIR / "data"
    papers_dir: Path = BASE_DIR / "data" / "papers"
    indexes_dir: Path = BASE_DIR / "data" / "indexes"
    experiments_dir: Path = BASE_DIR / "experiments"

    # Groq Provider settings
    groq_api_key: str = Field(default="", validation_alias="GROQ_API_KEY")
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.1-8b-instant"
    groq_request_timeout: float = 20.0

    # Retrieval settings
    default_retrieval_setting: Literal["A", "B", "C"] = "B"
    embedding_dim: int = 128

    # Admission Control Limits (calibrated to Groq free tier defaults)
    rate_limit_rpm: int = 30
    rate_limit_tpm: int = 6000
    rate_limit_rpd: int = 14400
    rate_limit_tpd: int = 500000
    max_concurrent_requests: int = 4
    queue_max_size: int = 50
    request_timeout_sec: float = 15.0

    # Concurrency Controller (AIMD parameters)
    min_concurrency: int = 1
    max_concurrency: int = 8
    aimd_increase_rate: float = 0.5
    aimd_decrease_ratio: float = 0.5
    latency_threshold_p90_ms: float = 2500.0

    # Circuit Breaker parameters
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout_sec: float = 20.0
    circuit_breaker_half_open_probes: int = 2

    # Retry Manager parameters
    max_retries: int = 3
    retry_base_delay: float = 0.5
    retry_max_delay: float = 8.0
    retry_budget_ratio: float = 0.20  # Max 20% retry allowance across window

    # Simulator defaults
    standin_profile: Literal[
        "normal",
        "high_latency",
        "unstable",
        "rate_limited",
        "daily_quota_exhausted",
        "overloaded"
    ] = "normal"
    simulator_seed: int = 42

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
