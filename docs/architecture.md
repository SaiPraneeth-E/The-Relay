# Architecture: THE RELAY

THE RELAY is architected as an **Adaptive Evidence-Aware Orchestration (AEO)** engine for multi-stage LLM question-answering pipelines under real-world infrastructure constraints.

---

## 1. High-Level System Architecture

```
                                      [ Incoming Query ]
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │  STAGE 1: Request Understanding           │
                         │  - Entity Disambiguation (Transformer/    │
                         │    Moshi/H-Net)                           │
                         │  - Complexity Rating & Token Envelope     │
                         │  - Priority Assignment (P0/P1/P2)         │
                         └─────────────────────┬─────────────────────┘
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │  STAGE 2: Admission Control & Queue       │
                         │  - RPM Token Bucket (Capacity 30)         │
                         │  - TPM Token Bucket (Capacity 6,000)      │
                         │  - Daily Quotas (14.4k RPD / 500k TPD)    │
                         │  - AIMD Concurrency Gate (Limit: 1 - 8)   │
                         │  - Priority Queue & TTL Abandonment (15s) │
                         └─────────────────────┬─────────────────────┘
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │  STAGE 3: Adaptive Hybrid Retrieval       │
                         │  - Dense Semantic Vector Space (LSA 128d) │
                         │  - Sparse Keyword Matcher (BM25Okapi)     │
                         │  - Reciprocal Rank Fusion (k=60)          │
                         │  - Dynamic Fallback (C -> B -> A on load) │
                         └─────────────────────┬─────────────────────┘
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │  STAGE 4: Reasoning & Tool Execution      │
                         │  - Context Construction & Prompt Synthesis│
                         │  - Formula Verification & Table Lookups   │
                         │  - Circuit Breaker Interception           │
                         └─────────────────────┬─────────────────────┘
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │  STAGE 5: Model Provider Execution        │
                         │  - Groq Real API (Llama 3.1 8B Instant)   │
                         │  - Calibrated Stand-in Simulator (6 prof.)│
                         │  - Full Jitter Retries & Backoff Budget   │
                         └─────────────────────┬─────────────────────┘
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │  STAGE 6: Independent Answer Verification │
                         │  - Citation Format & Existence Validation │
                         │  - Claim-to-Evidence Overlap Audit        │
                         │  - Bounded Correction Loop (Max 1 retry)  │
                         └─────────────────────┬─────────────────────┘
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │  STAGE 7: Response Delivery & Tracing     │
                         │  - Incremental Token Streaming            │
                         │  - TTFT & Generation Duration Breakdown   │
                         │  - Waterfall Request Telemetry Recording  │
                         └───────────────────────────────────────────┘
```

---

## 2. Core Engineering Subsystems

### A. Admission Control System (`app/orchestration/admission_control.py`)
- **Dual Token Buckets:** Manages separate RPM and TPM replenishment rates.
- **Quota State Tracking:** Tracks total daily requests (RPD) and daily tokens (TPD), ensuring the pipeline halts gracefully before hitting upstream provider penalties.
- **Priority Queuing:** Uses `heapq`-based priority sorting where P0 (formula verification) takes precedence over P1 (factual) and P2 (batch).
- **Client Abandonment Detection:** Automatically evicts expired items from the queue based on request arrival timestamps, saving inference capacity.

### B. Adaptive Concurrency Controller (`app/orchestration/concurrency_controller.py`)
- Employs Additive Increase / Multiplicative Decrease (AIMD):
  $$\text{Concurrency}_{t+1} = \begin{cases} \min(\text{Limit} + 0.5, \text{Max}) & \text{if } p90 < 0.7 \cdot \text{Target} \\ \max(\text{Limit} \cdot 0.5, \text{Min}) & \text{if } p90 > \text{Target or Rate-Limited} \end{cases}$$
- Dampens oscillations via a mandatory 1.0s cooldown window.

### C. Hybrid Search Engine (`app/retrieval/hybrid_search.py`)
- **Dense Vector Search:** Sublinear term frequency TF-IDF with 128-dimensional TruncatedSVD projection and L2 normalization.
- **BM25 Keyword Search:** Tokenized BM25Okapi scoring.
- **Reciprocal Rank Fusion (RRF):**
  $$RRF(d) = \sum_{m \in \{\text{Dense}, \text{BM25}\}} \frac{1}{60 + \text{rank}_m(d)}$$
- **Dynamic Retrieval Degradation:** Under queue congestion (>10 requests), degrades Setting C to Setting B; under severe congestion (>25 requests), degrades Setting B to Setting A, reducing token expenditure by up to 57.8%.

### D. Circuit Breaker (`app/orchestration/circuit_breaker.py`)
- State machine transitioning between `CLOSED`, `OPEN`, and `HALF_OPEN`.
- Trips after 5 consecutive failures, fast-failing subsequent requests for 20 seconds before admitting a probe to test upstream recovery.

### E. Independent Verification Audit (`app/verification/answer_validator.py`)
- Evaluates citations for paper title, arXiv ID, version, and section/page.
- Verifies claim overlap with retrieved passage text.
- Validates that unanswerable or out-of-domain queries receive an explicit, honest refusal.

