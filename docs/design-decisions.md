# Key Engineering Decisions & Trade-Offs: THE RELAY

In building **THE RELAY**, several engineering trade-offs were confronted. This document records the core design decisions, what alternatives were considered, and why each choice was made.

---

## 1. Decision: Never Trade Factual Correctness for Latency
- **The Tension:** Under high traffic spikes, standard chatbots either drop retrieval or hallucinate generic answers to maintain sub-second response times.
- **Our Decision:** Factual grounding is non-negotiable. If evidence cannot be retrieved, or if daily budgets are exhausted, THE RELAY issues an immediate, honest refusal: *"The available research library does not provide sufficient information."*
- **Trade-Off:** Refusal rate increases when out-of-domain questions are posed, but false information and unverified citations are completely eliminated.

---

## 2. Decision: Setting B as the Primary Operating Mode
- **The Tension:** Should chunks be small (250 tokens), medium (500 tokens), or large (1000 tokens)?
- **Our Findings:**
  - *Setting A (250 tokens):* Causes mathematical context fragmentation (e.g. separating Adam hyperparameters from the warmup schedule formula in Section 5.3 of Attention Is All You Need). Accuracy dropped to 72.2% (27.8% wrong).
  - *Setting C (1000 tokens):* Inflated tokens-per-answer to 4,607.7 (a **2.74× cost penalty**) while degrading accuracy to 66.7% (33.3% wrong), as the dilated context window introduced distractor paragraphs.
  - *Setting B (500 tokens):* Provided the highest cited accuracy (55.6%) and correct refusals (22.2%), achieving a **total 77.8% ground truth fidelity** at only 1,679.5 tokens per query ($0.0872 / 1,000 answers).
- **Our Decision:** Default to Setting B, while allowing AEO to degrade dynamically to Setting A during upstream rate-limit pressure (saving 59.0% of prompt tokens).

---

## 3. Decision: Full Jitter Exponential Backoff Over Immediate Retries
- **The Tension:** When an LLM provider returns HTTP 429, should clients retry immediately to minimize user wait time?
- **Our Findings:** In our `retry_congestion_uncontrolled` benchmark, immediate retries caused queue depth to spike to 24 and tail latency to explode to 26.4 seconds, while success rate plummeted to 63.3%.
- **Our Decision:** Implement exponential backoff with Full Jitter:
  $$\text{Sleep} = \text{Uniform}(0, \min(8.0, 0.5 \cdot 2^{\text{attempt}}))$$
  Respect server `Retry-After` headers and cap retries at 20% of the rolling request budget.

---

## 4. Decision: In-Process Dense LSA + BM25Okapi over Heavy External Services
- **The Tension:** Using remote embedding APIs or external vector databases introduces network round-trips, foreign DLL compatibility hurdles, and rate limit couplings.
- **Our Decision:** Built a self-contained, in-memory dense vector space (TF-IDF sublinear scaling + TruncatedSVD 128 dimensions) coupled with BM25Okapi and Reciprocal Rank Fusion.
- **Trade-Off:** Index generation takes 7 seconds at cold start, but subsequent lookups execute in 15–30ms without network dependencies or external operational points of failure.

---

## 5. Decision: Immediate Refusal on Daily Quota Exhaustion
- **The Tension:** Should requests queue up when the daily budget is gone?
- **Our Decision:** Fast-fail immediately with status 429 and `retry-after: 86400`. Users receive notification in 12.6ms rather than waiting until client timeout (15s).

---

## 6. Decision: Zero-Token Short-Circuit Refusal for Out-of-Domain Inquiries
- **The Tension:** When a user poses a question completely outside the verified 3-paper library (e.g. weather, quantum algorithms, OpenAI GPT-4 BLEU scores), should the multi-stage pipeline dispatch full retrieval contexts and invoke the upstream LLM?
- **Our Decision:** Implemented an Early Cost-Minimization & Efficiency Gate directly in Stage 1/2. When classified as out-of-domain or unanswerable, the pipeline immediately returns the verified honest refusal without consuming admission queue slots, rate-limit buckets, or model tokens.
- **Trade-Off:** Saves 100% of LLM token spend on unanswerable requests ($0.00 cost) and cuts user response latency from ~2,000ms down to < 5ms.

