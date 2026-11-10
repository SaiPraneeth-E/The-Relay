"""
Research Tools for THE RELAY Pipeline.
Provides analytical tools to verify formulas, cross-reference tables, and inspect metadata.
"""

from typing import Any, Dict, Optional
from app.retrieval.ingestion import PAPERS_METADATA

VERIFIED_FORMULAS = {
    "scaled_dot_product_attention": {
        "paper_id": "1706.03762v7",
        "name": "Scaled Dot-Product Attention",
        "section": "Section 3.2.1, Page 4",
        "equation": "Attention(Q, K, V) = softmax(Q K^T / sqrt(d_k)) V",
        "variables": {
            "Q": "Queries matrix (dim d_k)",
            "K": "Keys matrix (dim d_k)",
            "V": "Values matrix (dim d_v)",
            "d_k": "Dimensionality of keys/queries",
            "scaling_factor": "1 / sqrt(d_k) to counteract small gradients in softmax for large d_k"
        }
    },
    "multi_head_attention": {
        "paper_id": "1706.03762v7",
        "name": "Multi-Head Attention",
        "section": "Section 3.2.2, Page 4",
        "equation": "MultiHead(Q, K, V) = Concat(head_1, ..., head_h) W^O",
        "variables": {
            "head_i": "Attention(Q W_i^Q, K W_i^K, V W_i^V)",
            "h": "Number of heads (h=8)",
            "d_model": "512",
            "d_k": "d_model / h = 64"
        }
    },
    "dynamic_chunking_loss": {
        "paper_id": "2507.07955v2",
        "name": "Dynamic Chunking Continuity Formulation",
        "section": "Section 3, Page 5",
        "equation": "H-Net Hierarchical Representation: L = L_byte + lambda * L_chunk",
        "variables": {
            "L_byte": "Cross-entropy loss on raw byte predictions",
            "L_chunk": "Learned boundary segmentation loss without heuristic BPE supervision"
        }
    }
}

VERIFIED_BENCHMARKS = {
    "transformer_base": {
        "paper_id": "1706.03762v7",
        "table": "Table 2",
        "metrics": {"EN-DE BLEU": 27.3, "EN-FR BLEU": 38.1, "Training FLOPs": "3.3e18"}
    },
    "transformer_big": {
        "paper_id": "1706.03762v7",
        "table": "Table 2",
        "metrics": {"EN-DE BLEU": 28.4, "EN-FR BLEU": 41.8, "Training FLOPs": "2.3e19"}
    },
    "moshi_latency": {
        "paper_id": "2410.00037v1",
        "table": "Section 4.1 & Table 1",
        "metrics": {
            "theoretical_latency_ms": 160.0,
            "frame_size_ms": 80.0,
            "stride_ms": 80.0,
            "end_to_end_practical_ms": 200.0,
            "mimi_bandwidth_kbps": 1.1
        }
    },
    "h_net_efficiency": {
        "paper_id": "2507.07955v2",
        "table": "Table 1 & Figure 4",
        "metrics": {
            "dna_efficiency_gain": "Nearly 4x vs BPE baselines",
            "character_robustness": "Significant gain under typo perturbations",
            "architecture": "Single-stage and multi-stage hierarchical byte modeling"
        }
    }
}

class ResearchToolRegistry:
    @staticmethod
    def verify_formula_context(formula_key: str) -> Dict[str, Any]:
        """Tool 1: Verifies exact mathematical formulation and variable semantics."""
        key = formula_key.lower().strip().replace(" ", "_").replace("-", "_")
        for fkey, details in VERIFIED_FORMULAS.items():
            if fkey in key or key in fkey:
                return {"status": "found", "formula": details}
        return {
            "status": "not_found",
            "message": f"Formula '{formula_key}' not in verified library equations."
        }

    @staticmethod
    def cross_reference_tables(benchmark_key: str) -> Dict[str, Any]:
        """Tool 2: Cross-references empirical performance metrics and benchmark tables."""
        key = benchmark_key.lower().strip().replace(" ", "_").replace("-", "_")
        for bkey, details in VERIFIED_BENCHMARKS.items():
            if bkey in key or key in bkey:
                return {"status": "found", "benchmark": details}
        return {
            "status": "not_found",
            "message": f"Benchmark data '{benchmark_key}' not found in library tables."
        }

    @staticmethod
    def get_paper_metadata(paper_id: str) -> Dict[str, Any]:
        """Tool 3: Resolves paper metadata, official version, and citation coordinates."""
        for pid, meta in PAPERS_METADATA.items():
            if pid in paper_id or meta["arxiv_id"] in paper_id:
                return {"status": "found", "metadata": meta}
        return {
            "status": "not_found",
            "message": f"Paper identifier '{paper_id}' not found in exact 3-paper library."
        }

