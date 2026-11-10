"""
CLI Entry Point for THE RELAY: Engineering a Reliable, Adaptive AI Pipeline.
"""

import argparse
import asyncio
import sys
from pathlib import Path
from app.benchmarking.metrics import compute_scenario_metrics
from app.benchmarking.runner import BenchmarkRunner
from app.benchmarking.scenarios import BENCHMARK_SCENARIOS
from app.core.config import settings
from app.core.logging import logger
from app.evaluation.evaluator import RetrievalQualityEvaluator
from app.evaluation.failure_investigation import RetrievalFailureInvestigator
from app.pipeline.orchestrator import RelayOrchestrator
from app.providers.groq_provider import GroqProvider
from app.providers.simulator_provider import StandInSimulatorProvider
from app.retrieval.hybrid_search import HybridSearchEngine
from app.retrieval.ingestion import ingest_papers

def cmd_ingest(args):
    print("\n[INGESTION] Parsing exact arXiv papers and constructing hybrid indices...")
    engine = HybridSearchEngine()
    engine.initialize(force_reindex=args.force)
    for setting in ["A", "B", "C"]:
        n_chunks = len(engine.chunks_by_setting[setting])
        print(f"  ✓ Indexed Setting {setting}: {n_chunks} chunks")
    print("[SUCCESS] All indices generated in data/indexes/\n")

async def cmd_ask(args):
    engine = HybridSearchEngine()
    engine.initialize()

    provider = GroqProvider() if args.source == "real" else StandInSimulatorProvider(profile=args.profile)
    orchestrator = RelayOrchestrator(provider=provider, retrieval_engine=engine, source_name=args.source)

    print(f"\n[QUERY] {args.query}")
    print(f"[CONFIG] Source: {args.source} | Profile: {args.profile} | Setting: {args.setting}\n")

    resp, trace, val = await orchestrator.process_request(
        query=args.query,
        override_setting=args.setting
    )

    print("\n=== ANSWER ===")
    print(resp.content)
    print("\n" + trace.render_waterfall())
    print(f"Audit Grade: {val.grade.upper()} | Consistency: {val.consistency_score:.2f} | Valid Citation: {val.citation_valid}\n")

async def cmd_benchmark(args):
    runner = BenchmarkRunner()
    output_path = Path("results.csv")

    if args.scenario == "all":
        print("\n[BENCHMARK] Executing full suite across all load scenarios...")
        records, metrics = await runner.run_all_benchmarks(output_csv=output_path)
        print(f"\n[SUCCESS] Wrote {len(records)} request records to {output_path.resolve()}")
    else:
        if args.scenario not in BENCHMARK_SCENARIOS:
            print(f"Unknown scenario '{args.scenario}'. Choose from {list(BENCHMARK_SCENARIOS.keys())} or 'all'.")
            return
        cfg = BENCHMARK_SCENARIOS[args.scenario]
        print(f"\n[BENCHMARK] Executing scenario '{cfg.name}' ({cfg.num_requests} requests)...")
        records, mets = await runner.run_scenario(cfg)
        print("\n=== SCENARIO METRICS ===")
        for k, v in mets.items():
            print(f"  {k}: {v}")

async def cmd_evaluate(args):
    print("\n[EVALUATION] Evaluating all 18 test questions across Settings A, B, and C...")
    evaluator = RetrievalQualityEvaluator()
    output_path = Path("evaluation_results.csv")
    all_rows, summaries = await evaluator.run_full_evaluation(output_csv=output_path)
    print(f"\n[SUCCESS] Wrote {len(all_rows)} question evaluations to {output_path.resolve()}\n")
    print("=== TABLE 3: RETRIEVAL SETTINGS ===")
    for s in summaries:
        print(f"\n{s['setting']}:")
        print(f"  Correct & Cited: {s['correct_and_cited_pct']}% | Wrong: {s['wrong_pct']}% | Correctly Refused: {s['correctly_refused_pct']}%")
        print(f"  Tokens / Answer: {s['tokens_per_answer']} | TTFT p50: {s['first_token_p50']}ms | Total p50: {s['total_time_p50']}ms")

def cmd_investigate(args):
    print("\n[INVESTIGATION] Analyzing 3 Retrieval Failure Modes in Naive Retrievers...")
    engine = HybridSearchEngine()
    engine.initialize()
    investigator = RetrievalFailureInvestigator(engine)
    reports = investigator.run_investigation()

    for idx, rep in enumerate(reports, 1):
        print(f"\n--- FAILURE CASE {idx}: {rep.problem_title} ---")
        print(f"Question: {rep.example_question}")
        print(f"Naive Result Snippet:\n  {rep.naive_retrieved_passage}")
        print(f"Why Misleading:\n  {rep.why_misleading}")
        print(f"Improved AEO Snippet:\n  {rep.improved_retrieved_passage}")
        print(f"Improved Handling:\n  {rep.improved_method_explanation}\n")

def main():
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    parser = argparse.ArgumentParser(description="THE RELAY: Adaptive AI Pipeline CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Ingest
    ingest_p = subparsers.add_parser("ingest", help="Ingest papers and build hybrid indices")
    ingest_p.add_argument("--force", action="store_true", help="Force reindexing")

    # Ask
    ask_p = subparsers.add_parser("ask", help="Ask an engineering question")
    ask_p.add_argument("query", type=str, help="Question string")
    ask_p.add_argument("--source", choices=["stand-in", "real"], default="stand-in", help="Provider source")
    ask_p.add_argument("--profile", default="normal", help="Simulator profile")
    ask_p.add_argument("--setting", choices=["A", "B", "C"], default="B", help="Retrieval setting")

    # Benchmark
    bench_p = subparsers.add_parser("benchmark", help="Run benchmark load scenarios")
    bench_p.add_argument("--scenario", default="all", help="Scenario name or 'all'")

    # Evaluate
    eval_p = subparsers.add_parser("evaluate", help="Run retrieval quality evaluation")

    # Investigate
    inv_p = subparsers.add_parser("investigate", help="Run naive retrieval failure investigations")

    # Report
    rep_p = subparsers.add_parser("report", help="Generate final engineering report PDF and markdown")

    args = parser.parse_args()

    if args.command == "ingest":
        cmd_ingest(args)
    elif args.command == "ask":
        asyncio.run(cmd_ask(args))
    elif args.command == "benchmark":
        asyncio.run(cmd_benchmark(args))
    elif args.command == "evaluate":
        asyncio.run(cmd_evaluate(args))
    elif args.command == "investigate":
        cmd_investigate(args)
    elif args.command == "report":
        from scripts.generate_report import generate_final_report
        generate_final_report()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()

