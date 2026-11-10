import sys
sys.path.insert(0, ".")
from app.retrieval.hybrid_search import HybridSearchEngine

engine = HybridSearchEngine()
engine.initialize()

for qid, qtext in [
    ("q01", "What is the mathematical formula for Scaled Dot-Product Attention in Attention Is All You Need, and why is the scaling factor applied?"),
    ("q04", "In the Transformer architecture, how many attention heads are used in the base model, what is the dimension of each head, and how are positional encodings injected?"),
    ("q09", "What learning rate schedule was used for the Transformer base model, including warmup steps and formula?")
]:
    print(f"\n=== Query: {qid} in Setting B ===")
    res = engine.search(qtext, setting="B")
    for i, r in enumerate(res):
        print(f"  Rank {i+1}: Paper={r.chunk.paper_id} | Sec={r.chunk.section_title} | Pkg={r.chunk.page_number} | Score={r.score:.3f}")
        print(f"     Preview: {r.chunk.text[:120]}...")
