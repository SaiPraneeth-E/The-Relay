# THE RELAY: Engineering a Reliable, Adaptive AI Pipeline Under Real-World Constraints

**THE RELAY** is a production-grade, highly resilient AI pipeline designed to answer engineering research queries grounded strictly in three arXiv research papers:
1. **Attention Is All You Need** (`arXiv:1706.03762v7`)
2. **Moshi: a speech-text foundation model for real-time dialogue** (`arXiv:2410.00037v1`)
3. **Dynamic Chunking for End-to-End Hierarchical Sequence Modeling** (`arXiv:2507.07955v2`)

The pipeline operates under a core design philosophy: **Adaptive Evidence-Aware Orchestration (AEO)**—combining adaptive request scheduling, evidence-calibrated hybrid retrieval, real provider telemetry handling, and independent answer verification.

---

## Key Features

- **Adaptive Evidence-Aware Orchestration (AEO):** Dynamic admission control and request routing that prioritizes factual grounding over premature speed.
- **7-Stage Asynchronous Pipeline:**
  1. *Request Understanding:* Intent classification, complexity rating, entity disambiguation, token budgeting, and priority assignment.
  2. *Admission Control:* Dual token-bucket rate limiting (RPM/TPM), daily quota tracking (RPD/TPD), concurrency gates, priority queuing, and request abandonment detection.
  3. *Evidence Retrieval:* Multi-strategy hybrid search (Dense LSA Semantic Search + BM25Okapi + Reciprocal Rank Fusion) across Settings A, B, and C.
  4. *Reasoning & Tool Execution:* Closed-form mathematical formula extraction, benchmark table cross-referencing, and bounded reflection loops.
  5. *Answer Generation:* Real Groq API client (`llama-3.1-8b-instant`) and Calibrated Stand-In Model Simulator with streaming token delivery.
  6. *Independent Verification:* Citation validation (exact paper, arXiv ID, version, section/page), claim-to-evidence consistency checking, and honest refusal enforcement.
  7. *Response Delivery & Observability:* End-to-end token streaming, time-to-first-token (TTFT) recording, and terminal waterfall latency breakdown.
- **Calibrated Stand-In Simulator:** Six realistic operational profiles (`normal`, `high_latency`, `unstable`, `rate_limited`, `daily_quota_exhausted`, `overloaded`) calibrated against live Groq free-tier response headers.
- **100% Reproducible Benchmarks:** Automated runner generating `results.csv` and `evaluation_results.csv`.
- **Publication-Ready Two-Page Report:** Automated ReportLab generator compiling `submission-report.pdf`.

---

## Quickstart & CLI Commands

### 1. Installation
Clone the repository and install dependencies using Python 3.10+:
```bash
pip install -r requirements.txt
```

### 2. Configure Environment (Optional for Real Groq Calls)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Provide your Groq API key:
```env
GROQ_API_KEY=gsk_...
```
*(Note: If `GROQ_API_KEY` is omitted, THE RELAY runs seamlessly using the Calibrated Stand-in Model Simulator).*

### 3. Ingest Papers and Build Indices
Download the exact 3 arXiv paper versions and generate hybrid indices:
```bash
python scripts/download_papers.py
python -m app.main ingest
```

### 4. Query THE RELAY (Interactive CLI)
Ask engineering questions with full waterfall latency breakdowns:
```bash
python -m app.main ask "What is the formula for Scaled Dot-Product Attention?"
```
Ask an out-of-domain question to observe strict evidence-grounded refusal:
```bash
python -m app.main ask "What is the average temperature in Tokyo during July?"
```

### 5. Run Automated Tests
Execute the complete test suite:
```bash
pytest -v tests/
```

### 6. Run Benchmark Scenarios
Run all 6 required benchmark load shapes (Steady, Burst, Sustained Overload, Limit Halved, Daily Budget Exhausted, Uncontrolled Retries):
```bash
python -m app.main benchmark --scenario all
```

### 7. Run Retrieval Evaluation
Evaluate 18 comprehensive test questions across Settings A, B, and C:
```bash
python -m app.main evaluate
```

### 8. Inspect Naive Retrieval Failures
Demonstrate the three ways a naive semantic retriever is misled by this library:
```bash
python -m app.main investigate
```

### 9. Compile Submission Report PDF
Generate the publication-ready two-page report:
```bash
python -m app.main report
```

---

## Directory Layout

```
the-relay/
├── app/
│   ├── core/                  # Configuration, logging, waterfall metrics
│   ├── pipeline/              # Orchestrator, request understanding, generator, delivery
│   ├── retrieval/             # Ingestion, chunking, semantic search, BM25, hybrid search
│   ├── providers/             # Base provider, real Groq provider, calibrated simulator
│   ├── orchestration/         # Admission control, AIMD concurrency, retries, circuit breaker
│   ├── verification/          # Citation checker, answer validator, refusal auditor
│   ├── benchmarking/          # Scenarios, metrics, benchmark runner
│   ├── evaluation/            # Test dataset, quality evaluator, failure investigation
│   ├── tools/                 # Formula and benchmark table tools
│   └── main.py                # Unified CLI entry point
├── data/
│   ├── papers/                # Downloaded exact arXiv PDFs
│   ├── indexes/               # Serialized hybrid search indices
│   └── evaluation_questions.json # 18 comprehensive evaluation questions
├── docs/
│   ├── architecture.md        # System architecture and design documentation
│   ├── design-decisions.md    # Key engineering decisions and trade-offs
│   ├── experiments.md         # Full benchmark and evaluation analysis
│   ├── assistant_history.md   # Assistant prompt log and engineering reflection
│   └── report.md              # Markdown mirror of the 2-page report
├── scripts/
│   ├── download_papers.py     # Paper fetcher and verification script
│   ├── compute_tables.py      # Computes Table 1, 2a, 2b, 3 from CSV data
│   └── generate_report.py     # Two-page PDF report generator
├── tests/                     # 20 automated pytest test cases
├── results.csv                # 155 request benchmark records
├── evaluation_results.csv     # 54 question-level evaluation records
├── submission-report.pdf      # Exactly 2 pages PDF engineering report
├── requirements.txt
├── Dockerfile
├── render.yaml
└── README.md
```

---

## Experimental Summary

### Table 2a: Latency Across Load Scenarios
| Scenario | Source | Reqs | First Token p50 / p95 / p99 (ms) | Total Time p50 / p95 / p99 (ms) |
| :--- | :---: | :---: | :---: | :---: |
| steady | stand-in | 20 | 266.0 / 418.1 / 421.6 | 1947.3 / 2443.5 / 2497.2 |
| burst | stand-in | 25 | 339.4 / 425.7 / 427.8 | 2034.5 / 2560.4 / 2594.9 |
| sustained_overload | stand-in | 35 | 7155.0 / 22240.8 / 22813.0 | 967.1 / 38552.5 / 42117.4 |
| per_minute_limit_halved | stand-in | 25 | 312.4 / 315.7 / 315.9 | 81.3 / 58772.0 / 59331.2 |
| daily_budget_exhausted | stand-in | 20 | 0.0 / 0.0 / 0.0 | 17.2 / 21.0 / 21.1 |
| retry_congestion_uncontrolled | stand-in | 30 | 6904.6 / 17839.9 / 21942.3 | 1573.7 / 36067.7 / 37566.7 |

### Table 2b: Outcomes Across Load Scenarios
| Scenario | Succeeded % | Rate-limited % | Timed out % | Retries / req | Peak Queue | Tokens / answer | Cost / 1,000 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| steady | 100.0% | 0.0% | 0.0% | 0.00 | 0 | 61.4 | $0.0948 |
| burst | 100.0% | 0.0% | 0.0% | 0.00 | 11 | 61.6 | $0.0976 |
| sustained_overload | 45.7% | 0.0% | 54.3% | 0.14 | 28 | 59.7 | $0.0924 |
| per_minute_limit_halved | 32.0% | 0.0% | 68.0% | 0.24 | 18 | 65.2 | $0.1099 |
| daily_budget_exhausted | 0.0% | 25.0% | 75.0% | 0.00 | 0 | 0.0 | $0.0000 |
| retry_congestion_uncontrolled | 46.7% | 0.0% | 53.3% | 0.17 | 24 | 62.1 | $0.0969 |

### Table 3: Retrieval Settings Evaluation
| Setting | Qs | Correct & Cited % | Wrong % | Correct Refusal % | Tokens / answer | FT p50 / p95 (ms) | Total p50 / p95 (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Setting A (250 tokens, 3 fetched) | 18 | 5.6% | 77.8% | 16.7% | 774.7 | 298.4 / 411.1 | 2094.0 / 2426.6 |
| Setting B (500 tokens, 5 fetched) | 18 | 22.2% | 61.1% | 16.7% | 1838.4 | 269.6 / 421.2 | 1951.3 / 2431.2 |
| Setting C (1000 tokens, 8 fetched) | 18 | 5.6% | 77.8% | 16.7% | 4930.4 | 294.6 / 407.9 | 1787.2 / 2435.8 |

