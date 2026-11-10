# Experimental Analysis & Benchmark Results: THE RELAY

This document provides complete experimental documentation for THE RELAY, detailing benchmark load shapes, results across scenarios, retrieval quality metrics, and naive retriever failure analyses.

---

## 1. Real Service Limits Discovery (Groq Free Tier)

| Metric | Documented / Observed | Validation Source | Confidence |
| :--- | :---: | :--- | :---: |
| Model | `llama-3.1-8b-instant` | Groq Model Documentation | High |
| Requests per minute (RPM) | 30 | Groq Console Limits & `x-ratelimit-limit-requests` | High |
| Tokens per minute (TPM) | 6,000 | Captured response header `x-ratelimit-limit-tokens` | High |
| Requests per day (RPD) | 14,400 | Organization limits table | High |
| Tokens per day (TPD) | 500,000 | Organization limits table | Medium |
| Concurrency Saturation | 4 – 8 | In-flight request throttling threshold | Medium |
| Error Code on Breach | HTTP 429 | `{"error": {"type": "tokens", "code": "rate_limit_exceeded"}}` | High |
| Recovery Duration | 1.0s – 60.0s | Sliding window `x-ratelimit-reset-requests` | High |

---

## 2. Load Scenarios & Benchmark Results (155 Requests)

All numbers are computed directly from `results.csv`.

### Table 2a: Latency Across Scenarios
| Scenario | Source | Reqs | Duration (s) | Offered Rate (/min) | First Token p50 / p95 / p99 (ms) | Total Time p50 / p95 / p99 (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| steady | stand-in | 20 | 36.0 | 33.3 | 263.4 / 382.1 / 424.8 | 1132.9 / 2065.3 / 2357.5 |
| burst | stand-in | 25 | 12.2 | 123.0 | 322.0 / 407.8 / 419.2 | 1205.0 / 2268.3 / 2451.4 |
| sustained_overload | stand-in | 35 | 49.3 | 42.6 | 5007.1 / 18233.0 / 25446.3 | 1958.1 / 33340.6 / 34487.8 |
| per_minute_limit_halved | stand-in | 25 | 78.6 | 19.1 | 300.5 / 319.2 / 323.3 | 78.9 / 58754.2 / 59281.5 |
| daily_budget_exhausted | stand-in | 20 | 10.0 | 120.0 | 2.0 / 2.0 / 2.0 | 12.6 / 20.0 / 22.1 |
| retry_congestion_uncontrolled | stand-in | 30 | 43.2 | 41.7 | 5650.6 / 21469.1 / 22666.5 | 1810.7 / 26184.3 / 26372.9 |

### Table 2b: Outcomes Across Scenarios
| Scenario | Succeeded % | Rate-limited % | Timed out % | Retries / req | Peak Queue | Tokens / answer | Cost / 1,000 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| steady | 100.0% | 0.0% | 0.0% | 0.00 | 0 | 48.9 | $0.0872 |
| burst | 100.0% | 0.0% | 0.0% | 0.00 | 11 | 51.4 | $0.0915 |
| sustained_overload | 74.3% | 0.0% | 25.7% | 0.14 | 28 | 42.5 | $0.0756 |
| per_minute_limit_halved | 44.0% | 0.0% | 56.0% | 0.20 | 18 | 38.0 | $0.0681 |
| daily_budget_exhausted | 20.0% | 25.0% | 55.0% | 0.00 | 0 | 0.0 | $0.0000 |
| retry_congestion_uncontrolled | 63.3% | 0.0% | 36.7% | 0.17 | 24 | 49.4 | $0.0866 |

---

## 3. Retrieval Quality Evaluation (54 Evaluated Queries)

All numbers are computed directly from `evaluation_results.csv`.

### Table 3: Retrieval Settings
| Setting | Questions | Correct & Cited % | Wrong % | Correct Refusal % | Tokens / answer | FT p50 / p95 (ms) | Total p50 / p95 (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Setting A (250 tokens, 3 fetched) | 18 | 50.0% | 27.8% | 22.2% | 689.3 | 265.0 / 400.4 | 1111.5 / 2410.8 |
| Setting B (500 tokens, 5 fetched) | 18 | 55.6% | 22.2% | 22.2% | 1679.5 | 263.9 / 396.7 | 1126.7 / 2125.6 |
| Setting C (1000 tokens, 8 fetched) | 18 | 44.4% | 33.3% | 22.2% | 4607.7 | 327.1 / 395.5 | 1098.1 / 1660.0 |

---

## 4. Naive Retrieval Failure Case Studies

### Case 1: Polysemous Terminology Confusion
- **Query:** *"How does the chunking mechanism segment input representations into discrete units?"*
- **Naive Retrieval:** Projects query into vector space where "chunking" matches both Moshi (audio frames) and H-Net (byte boundaries). Top hit returns Moshi's acoustic frame split instead of sequence modeling text tokenization.
- **Improved AEO Handling:** Request Understanding identifies technical entities and couples BM25 exact term matching ("dynamic chunking", "sequence modeling") with RRF fusion to prioritize arXiv:2507.07955v2.

### Case 2: Semantic Similarity Trap
- **Query:** *"Why is dot-product attention faster and more space-efficient in practice than additive attention?"*
- **Naive Retrieval:** Cosine similarity matches high-level introductory sentences in Section 1 and Abstract ("attention mechanisms provide parallelization"), omitting Section 3.2.1 where matrix multiplication code optimization is formulated.
- **Improved AEO Handling:** Setting C with contextual reranking scores query term density across mathematical sections, pulling Section 3.2.1 and Table 1.

### Case 3: Contextual Incompleteness via Boundary Truncation
- **Query:** *"What is the exact learning rate schedule and warmup formula for the Transformer base model?"*
- **Naive Retrieval:** Under Setting A (250 tokens), the Adam optimizer parameter discussion (beta1, beta2) in Section 5.3 is separated from the closed-form equation on page 7.
- **Improved AEO Handling:** Setting B's 500-token window with 50-token overlap preserves both the hyperparameter declarations and the warmup formula in a single coherent context block.

