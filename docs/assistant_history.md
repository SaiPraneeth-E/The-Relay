# How I Worked with the Assistant

This section documents the actual interaction log, strategic directions, error corrections, and architectural decisions made while engineering **THE RELAY**.

---

## 1. The Three Prompts That Mattered Most

### Prompt 1: System Vision & Orchestration Philosophy
> *"Act as a Senior AI Infrastructure Engineer, Python Architect, Distributed Systems Engineer, LLM Performance Engineer, and Technical Research Engineer. Build THE RELAY as an adaptive AI research assistant that answers engineering questions using exactly three specified research papers. Make the project distinctive through Adaptive Evidence-Aware Orchestration (AEO): combine adaptive execution, evidence-aware retrieval, and reliability-first delivery. Never trade factual correctness for response speed."*

**Why it mattered:** This prompt established the fundamental architectural invariant of the system: factual grounding supersedes speed. It prevented the pipeline from becoming a standard RAG demo and forced the creation of independent verification, admission control, and quota-aware refusal mechanisms.

### Prompt 2: Calibrated Model Stand-in Specification
> *"Build a separate model stand-in service controlled entirely by THE RELAY. The stand-in must simulate: variable latency, slow successful responses, random failures, timeouts, RPM exhaustion, TPM exhaustion, daily quota exhaustion, concurrency restrictions, and partial streaming across six configurable profiles (normal, high_latency, unstable, rate_limited, daily_quota_exhausted, overloaded). Calibrate it from real Groq measurements."*

**Why it mattered:** Free-tier LLM accounts cannot survive the dozens of load tests required to evaluate burst and sustained overload. This prompt drove the creation of a high-fidelity synthetic provider that replicates Groq's exact HTTP 429 response bodies, headers (`retry-after`, `x-ratelimit-*`), and non-linear queuing penalties without violating provider terms of service.

### Prompt 3: Empirical Retrieval Failure Investigations
> *"Investigate three ways a naive retriever can be misled by this library. For each failure: identify the retrieval problem, create an example question, record naive retrieval results, explain why it is misleading, demonstrate how the improved method handles it, and record actual observations. Do not manufacture examples."*

**Why it mattered:** Grounded the retrieval evaluation in real PDF textual anomalies—such as the polysemous use of "chunking" in audio codecs (Moshi) versus byte hierarchies (H-Net), and chunk boundary truncation in Attention Is All You Need.

---

## 2. One Thing the Assistant Got Wrong and How I Caught It

**The Error:**
During the initial dependency setup, the assistant attempted to import Sentence Transformers and PyTorch directly on Windows. However, the Windows Application Control (WDAC) policy on the host machine blocked `torch\lib\shm.dll` from loading (`OSError: [WinError 4551] An Application Control policy has blocked this file`). Later, when executing async tests inside the Windows sandbox, Python's default `ProactorEventLoop` hung because internal loopback socket pairs are restricted in non-network sandbox mode.

**How I Caught It:**
I monitored the process execution logs using terminal inspection commands. Observing that the background test worker hung at `test_full_pipeline_factual_query`, I isolated the issue:
1. Replaced the heavy PyTorch dependency with an in-memory, zero-DLL-blocked, high-performance dense semantic vector space using scikit-learn's sublinear `TfidfVectorizer` + `TruncatedSVD` (128-dimensional LSA continuous vector projection) + `BM25Okapi` + Reciprocal Rank Fusion.
2. Verified that all async test runners execute cleanly under unrestricted network mode (`BypassSandbox: true`), yielding 100% test pass rates in under 12 seconds.

---

## 3. One Decision Where I Overruled the Assistant

**The Decision:**
When designing the retry manager for rate limits, the assistant initially suggested retrying all HTTP 429 errors indefinitely with exponential backoff until a response succeeded.

**Why I Overruled It:**
I overruled this behavior because when a daily budget limit (RPD or TPD) is hit, continuous retrying consumes CPU, holds client connection sockets open, and guarantees repeated failure across a 24-hour reset horizon. Furthermore, under overload conditions, aggressive retries create a self-inflicted DDoS attack (as proven in our `retry_congestion_uncontrolled` benchmark, which surged tail latency to 26.4s and spiked peak queue depth to 24). I enforced a strict rule:
1. Daily quota 429 errors are permanently non-retryable and trigger an immediate honest refusal in under 13ms (12.6ms measured).
2. Per-minute 429 errors respect server `Retry-After` headers and are bound by a maximum 20% retry budget.

---

## 4. What Is Distinctly Mine in This Submission

1. **Adaptive Evidence-Aware Orchestration (AEO):** The architectural concept of dynamically downgrading retrieval chunk sizes (from Setting C to B or A) under queue backpressure to protect the TPM token budget while preserving answer grounding, and the Zero-Token Early Refusal Gate that short-circuits unanswerable queries at 0 tokens and < 2ms latency.
2. **Deterministic Multi-Profile Stand-In:** The mathematical calibration of the stand-in simulator's concurrency penalty ($L = L_0 \cdot (1 + 0.35 \cdot C^{1.8})$) and authentic Groq header emulation.
3. **Evidence-Based Refusal Guarantee:** The implementation of a multi-tier verification stage that audits claims against extracted PDF chunks and explicitly refuses out-of-domain queries rather than hallucinating.
4. **Empirically Proven Optimal Setting B:** Establishing that Setting B achieves the highest ground truth fidelity (77.8%) at only 1,679.5 tokens, while Setting A fragments mathematical context and Setting C introduces a 2.74× cost penalty with distractor dilution.
5. **Reproducible Experimental Evidence:** Complete agreement across raw request-level telemetry (`results.csv`), question-level audits (`evaluation_results.csv`), and the compiled two-page submission report (`submission-report.pdf`).

