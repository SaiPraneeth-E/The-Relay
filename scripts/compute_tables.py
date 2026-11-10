import pandas as pd
import numpy as np

def compute_tables():
    df = pd.read_csv("results.csv")
    scenarios = [
        "steady",
        "burst",
        "sustained_overload",
        "per_minute_limit_halved",
        "daily_budget_exhausted",
        "retry_congestion_uncontrolled"
    ]

    print("=== Table 2a: Latency, one row per load scenario ===")
    print(f"{'Scenario':<30} | {'Source':<8} | {'Reqs':<4} | {'FT p50/p95/p99 (ms)':<25} | {'Total p50/p95/p99 (ms)':<25}")
    print("-" * 105)

    for sc in scenarios:
        sub = df[df["scenario"] == sc]
        if len(sub) == 0:
            continue
        source = sub.iloc[0]["source"]
        n_req = len(sub)
        ft = sub[sub["first_token_ms"] > 0]["first_token_ms"]
        tt = sub["total_ms"]

        ft_p50, ft_p95, ft_p99 = np.percentile(ft, [50, 95, 99]) if len(ft) > 0 else (0.0, 0.0, 0.0)
        tt_p50, tt_p95, tt_p99 = np.percentile(tt, [50, 95, 99])

        ft_str = f"{ft_p50:.1f} / {ft_p95:.1f} / {ft_p99:.1f}"
        tt_str = f"{tt_p50:.1f} / {tt_p95:.1f} / {tt_p99:.1f}"
        print(f"{sc:<30} | {source:<8} | {n_req:<4} | {ft_str:<25} | {tt_str:<25}")

    print("\n=== Table 2b: Outcomes, same rows ===")
    print(f"{'Scenario':<30} | {'Succ %':<7} | {'RL %':<7} | {'TO %':<7} | {'Retries':<8} | {'Tokens/Ans':<10} | {'Cost/1k':<10}")
    print("-" * 95)

    for sc in scenarios:
        sub = df[df["scenario"] == sc]
        if len(sub) == 0:
            continue
        n_req = len(sub)
        succ = (sub["status"] == "ok").mean() * 100.0
        rl = (sub["status"] == "rate_limited").mean() * 100.0
        to = (sub["status"].isin(["timeout", "error"])).mean() * 100.0
        retries = sub["retries"].mean()
        toks = sub[sub["status"] == "ok"]["tokens_out"].mean() if (sub["status"] == "ok").sum() > 0 else 0.0
        cost = (((sub["tokens_in"].sum() / 1e6) * 0.05) + ((sub["tokens_out"].sum() / 1e6) * 0.08)) / max(1, (sub["status"] == "ok").sum()) * 1000.0

        print(f"{sc:<30} | {succ:>6.1f}% | {rl:>6.1f}% | {to:>6.1f}% | {retries:>7.2f}  | {toks:>9.1f}  | ${cost:>7.4f}")

    print("\n=== Table 3: Retrieval settings ===")
    edf = pd.read_csv("evaluation_results.csv")
    for s in ["A", "B", "C"]:
        sub = edf[edf["setting"] == s]
        total_q = len(sub)
        corr_cited = ((sub["answer_grade"] == "correct") & (sub["citation_valid"] == True)).mean() * 100.0
        wrong = (sub["answer_grade"].isin(["wrong", "refused_wrongly"])).mean() * 100.0
        ref_corr = (sub["answer_grade"] == "refused_correctly").mean() * 100.0
        toks = sub["tokens_used"].mean()
        ft_p50, ft_p95 = np.percentile(sub["first_token_ms"], [50, 95])
        tt_p50, tt_p95 = np.percentile(sub["total_ms"], [50, 95])
        setting_desc = {
            "A": "Setting A (250 tokens, 3 fetched, re-rank No)",
            "B": "Setting B (500 tokens, 5 fetched, re-rank No)",
            "C": "Setting C (1000 tokens, 8 fetched, re-rank Yes)"
        }[s]
        print(f"{setting_desc}:")
        print(f"  Q: {total_q} | Correct & Cited: {corr_cited:.1f}% | Wrong: {wrong:.1f}% | Correct Refusal: {ref_corr:.1f}% | Tokens: {toks:.1f} | FT p50/95: {ft_p50:.1f}/{ft_p95:.1f}ms | TT p50/95: {tt_p50:.1f}/{tt_p95:.1f}ms")

if __name__ == "__main__":
    compute_tables()

