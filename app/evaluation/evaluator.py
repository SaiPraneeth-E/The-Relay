"""
Retrieval Quality Evaluator for THE RELAY.
Evaluates all 18 test questions across Settings A, B, and C and outputs evaluation_results.csv.
"""

import asyncio
import csv
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Literal, Optional, Tuple
import numpy as np
from app.benchmarking.metrics import compute_percentiles
from app.core.config import settings
from app.pipeline.orchestrator import RelayOrchestrator
from app.providers.simulator_provider import StandInSimulatorProvider
from app.retrieval.hybrid_search import HybridSearchEngine

EVALUATION_CSV_HEADERS = [
    "question_id",
    "category",
    "setting",
    "question",
    "answer_grade",
    "consistency_score",
    "citation_valid",
    "tokens_used",
    "first_token_ms",
    "total_ms",
    "response_snippet",
    "audit_reason"
]

class RetrievalQualityEvaluator:
    def __init__(self, retrieval_engine: Optional[HybridSearchEngine] = None):
        self.retrieval_engine = retrieval_engine or HybridSearchEngine()
        self.questions: List[Dict] = []
        self._load_questions()

    def _load_questions(self):
        q_path = settings.data_dir / "evaluation_questions.json"
        with open(q_path, "r", encoding="utf-8") as f:
            self.questions = json.load(f)

    async def evaluate_setting(
        self,
        setting: Literal["A", "B", "C"]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Runs all 18 questions under a specific retrieval setting."""
        provider = StandInSimulatorProvider(profile="normal", seed=42)
        orchestrator = RelayOrchestrator(
            provider=provider,
            retrieval_engine=self.retrieval_engine,
            source_name="stand-in"
        )
        await orchestrator.initialize()

        question_rows = []
        first_tokens = []
        total_times = []
        tokens_out_list = []

        for q_item in self.questions:
            qid = q_item["id"]
            cat = q_item["category"]
            q_text = q_item["question"]

            resp, trace, val = await orchestrator.process_request(
                query=q_text,
                request_id=f"eval_{setting}_{qid}",
                scenario=f"eval_{setting}",
                override_setting=setting
            )

            first_tokens.append(trace.first_token_ms)
            total_times.append(trace.total_ms)
            tokens_out_list.append(trace.tokens_out)

            row = {
                "question_id": qid,
                "category": cat,
                "setting": setting,
                "question": q_text,
                "answer_grade": val.grade,
                "consistency_score": round(val.consistency_score, 2),
                "citation_valid": val.citation_valid,
                "tokens_used": trace.tokens_in + trace.tokens_out,
                "first_token_ms": round(trace.first_token_ms, 1),
                "total_ms": round(trace.total_ms, 1),
                "response_snippet": resp.content[:140].replace("\n", " "),
                "audit_reason": val.reason
            }
            question_rows.append(row)

        # Aggregate summary metrics for Table 3
        total_q = len(question_rows)
        correct_cited = sum(1 for r in question_rows if r["answer_grade"] == "correct" and r["citation_valid"])
        wrong = sum(1 for r in question_rows if r["answer_grade"] in ("wrong", "refused_wrongly"))
        refused_corr = sum(1 for r in question_rows if r["answer_grade"] == "refused_correctly")

        correct_cited_pct = round((correct_cited / total_q) * 100.0, 1)
        wrong_pct = round((wrong / total_q) * 100.0, 1)
        refused_corr_pct = round((refused_corr / total_q) * 100.0, 1)

        ft_p50, ft_p95, _ = compute_percentiles(first_tokens)
        tt_p50, tt_p95, _ = compute_percentiles(total_times)
        avg_tokens = round(float(np.mean(tokens_out_list)), 1)

        setting_label = {
            "A": "Setting A (250 tokens, 3 fetched, re-rank No)",
            "B": "Setting B (500 tokens, 5 fetched, re-rank No)",
            "C": "Setting C (1000 tokens, 8 fetched, re-rank Yes)"
        }[setting]

        summary = {
            "setting": setting_label,
            "setting_code": setting,
            "questions_asked": total_q,
            "correct_and_cited_pct": correct_cited_pct,
            "wrong_pct": wrong_pct,
            "correctly_refused_pct": refused_corr_pct,
            "tokens_per_answer": avg_tokens,
            "first_token_p50": ft_p50,
            "first_token_p95": ft_p95,
            "total_time_p50": tt_p50,
            "total_time_p95": tt_p95
        }

        return question_rows, summary

    async def run_full_evaluation(
        self,
        output_csv: Path
    ) -> Tuple[List[Dict], List[Dict]]:
        """Runs evaluation across all settings and writes evaluation_results.csv."""
        all_rows = []
        all_summaries = []

        for setting in ["A", "B", "C"]:
            rows, summary = await self.evaluate_setting(setting=setting)  # type: ignore
            all_rows.extend(rows)
            all_summaries.append(summary)

        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=EVALUATION_CSV_HEADERS)
            writer.writeheader()
            for r in all_rows:
                writer.writerow(r)

        return all_rows, all_summaries

