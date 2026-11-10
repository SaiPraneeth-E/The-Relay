"""
Benchmark Runner for THE RELAY.
Executes load shapes, tracks live telemetry, and writes results.csv.
"""

import asyncio
import csv
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple
from app.benchmarking.metrics import (
    RESULTS_CSV_HEADERS,
    BenchmarkRecord,
    compute_scenario_metrics
)
from app.benchmarking.scenarios import BENCHMARK_SCENARIOS, ScenarioConfig
from app.core.config import settings
from app.pipeline.orchestrator import RelayOrchestrator
from app.providers.base import BaseProvider
from app.providers.groq_provider import GroqProvider
from app.providers.simulator_provider import StandInSimulatorProvider
from app.retrieval.hybrid_search import HybridSearchEngine

class BenchmarkRunner:
    def __init__(self, retrieval_engine: Optional[HybridSearchEngine] = None):
        self.retrieval_engine = retrieval_engine or HybridSearchEngine()
        self.evaluation_questions: List[Dict] = []
        self._load_questions()

    def _load_questions(self):
        q_path = settings.data_dir / "evaluation_questions.json"
        if q_path.exists():
            with open(q_path, "r", encoding="utf-8") as f:
                self.evaluation_questions = json.load(f)

    async def run_scenario(
        self,
        config: ScenarioConfig,
        provider: Optional[BaseProvider] = None
    ) -> Tuple[List[BenchmarkRecord], Dict]:
        """Runs a single configured benchmark scenario."""
        # 1. Instantiate provider according to config
        if provider is None:
            if config.source == "real":
                provider = GroqProvider()
            else:
                provider = StandInSimulatorProvider(
                    profile=config.profile,
                    seed=settings.simulator_seed,
                    rpm_limit=config.rpm_limit,
                    tpm_limit=config.tpm_limit
                )

        orchestrator = RelayOrchestrator(
            provider=provider,
            retrieval_engine=self.retrieval_engine,
            source_name=config.source
        )
        await orchestrator.initialize()

        records: List[BenchmarkRecord] = []
        num_questions = len(self.evaluation_questions) if self.evaluation_questions else 1
        scenario_start_time = time.perf_counter()

        # Execute requests according to arrival shape
        tasks = []

        async def worker(idx: int, q_data: Dict):
            req_id = f"{config.name}_{idx+1:03d}"
            query = q_data.get("question", "What is scaled dot product attention?")
            resp, trace, val = await orchestrator.process_request(
                query=query,
                request_id=req_id,
                scenario=config.name,
                override_setting=config.retrieval_setting,
                enable_retries=config.enable_retries
            )
            rec = BenchmarkRecord(
                request_id=trace.request_id,
                scenario=config.name,
                source=trace.source,  # type: ignore
                start_time=trace.start_time_iso,
                first_token_ms=trace.first_token_ms,
                total_ms=trace.total_ms,
                status=trace.status,  # type: ignore
                retries=trace.retries_count,
                tokens_in=trace.tokens_in,
                tokens_out=trace.tokens_out,
                retrieval_setting=trace.retrieval_setting,  # type: ignore
                answer_grade=trace.answer_grade  # type: ignore
            )
            records.append(rec)

        if config.is_burst:
            # Dispatch in concurrent batches
            for i in range(config.num_requests):
                q = self.evaluation_questions[i % num_questions]
                tasks.append(asyncio.create_task(worker(i, q)))
                if (i + 1) % config.burst_batch_size == 0:
                    await asyncio.sleep(config.inter_arrival_sec)
        else:
            # Poisson / steady paced arrivals
            for i in range(config.num_requests):
                q = self.evaluation_questions[i % num_questions]
                tasks.append(asyncio.create_task(worker(i, q)))
                await asyncio.sleep(config.inter_arrival_sec)

        await asyncio.gather(*tasks, return_exceptions=True)

        duration = time.perf_counter() - scenario_start_time
        metrics = compute_scenario_metrics(
            records=records,
            scenario_name=config.name,
            duration_s=duration,
            peak_queue_len=orchestrator.admission_controller.queue_manager.peak_queue_length
        )

        return records, metrics

    async def run_all_benchmarks(
        self,
        output_csv: Path,
        real_probe_count: int = 5
    ) -> Tuple[List[BenchmarkRecord], List[Dict]]:
        """Runs the entire benchmark matrix and outputs results.csv."""
        all_records: List[BenchmarkRecord] = []
        all_metrics: List[Dict] = []

        # 1. Real service probe if key is available
        if settings.groq_api_key:
            real_cfg = ScenarioConfig(
                name="steady_real",
                num_requests=real_probe_count,
                inter_arrival_sec=2.5,
                is_burst=False,
                burst_batch_size=1,
                profile="normal",
                source="real",
                rpm_limit=30,
                tpm_limit=6000
            )
            recs, mets = await self.run_scenario(real_cfg)
            all_records.extend(recs)
            all_metrics.append(mets)

        # 2. Run all required stand-in scenarios
        required_scenarios = [
            "steady",
            "burst",
            "sustained_overload",
            "per_minute_limit_halved",
            "daily_budget_exhausted",
            "retry_congestion_uncontrolled"
        ]

        for sc_name in required_scenarios:
            cfg = BENCHMARK_SCENARIOS[sc_name]
            recs, mets = await self.run_scenario(cfg)
            all_records.extend(recs)
            all_metrics.append(mets)

        # 3. Write results.csv with exact schema
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=RESULTS_CSV_HEADERS)
            writer.writeheader()
            for r in all_records:
                writer.writerow(r.to_csv_row())

        return all_records, all_metrics

