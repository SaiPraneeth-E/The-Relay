"""
Stage 1: Request Understanding for THE RELAY.
Analyzes engineering questions, classifies intent, extracts entities, and estimates resources.
"""

import re
import uuid
from dataclasses import dataclass, field
from typing import List, Literal, Optional

QuestionType = Literal[
    "factual",
    "comparative",
    "methodological",
    "architectural",
    "unanswerable_out_of_domain"
]

PriorityLevel = Literal[0, 1, 2]  # 0: High, 1: Normal, 2: Low

@dataclass
class RequestAnalysis:
    request_id: str
    raw_query: str
    question_type: QuestionType
    entities: List[str]
    complexity: Literal["low", "medium", "high"]
    estimated_prompt_tokens: int
    estimated_completion_tokens: int
    priority: PriorityLevel
    recommended_retrieval_setting: Literal["A", "B", "C"]
    requires_tool: bool
    tool_name: Optional[str] = None
    tool_arg: Optional[str] = None

OUT_OF_DOMAIN_KEYWORDS = [
    "solar radiation", "weather", "recipe", "quantum", "stock", "bitcoin",
    "crypto", "cooking", "nba", "football", "president", "tokyo",
    "gpt-4", "gpt4", "openai", "chatgpt", "wmt 2014 in 2023"
]

class RequestUnderstandingEngine:
    @staticmethod
    def analyze(query: str, request_id: Optional[str] = None) -> RequestAnalysis:
        req_id = request_id or f"req_{uuid.uuid4().hex[:10]}"
        query_clean = query.strip()
        query_lower = query_clean.lower()

        # 1. Detect Out-of-Domain / Unanswerable
        if any(kw in query_lower for kw in OUT_OF_DOMAIN_KEYWORDS):
            return RequestAnalysis(
                request_id=req_id,
                raw_query=query_clean,
                question_type="unanswerable_out_of_domain",
                entities=[],
                complexity="low",
                estimated_prompt_tokens=len(query_clean.split()) * 2,
                estimated_completion_tokens=60,
                priority=1,
                recommended_retrieval_setting="A",
                requires_tool=False
            )

        # 2. Extract technical entities
        entities = []
        if re.search(r"\b(attention|scaled dot-product|multi-head|transformer)\b", query_lower):
            entities.append("Transformer")
        if re.search(r"\b(moshi|mimi|speech|audio|dialogue|conversational)\b", query_lower):
            entities.append("Moshi")
        if re.search(r"\b(dynamic chunking|h-net|hierarchical|byte|bpe)\b", query_lower):
            entities.append("H-Net")

        # 3. Classify question type & complexity
        is_comparative = any(w in query_lower for w in ["compare", "difference", "versus", "vs", "trade-off", "tradeoff"])
        is_formula = any(w in query_lower for w in ["formula", "equation", "math", "calculate", "derive"])
        is_table = any(w in query_lower for w in ["table", "metric", "bleu", "latency", "benchmark", "score", "flops"])

        if is_comparative:
            qtype = "comparative"
            complexity = "high"
            est_comp_tokens = 320
            rec_setting = "C"
            priority = 1
        elif is_formula:
            qtype = "methodological"
            complexity = "medium"
            est_comp_tokens = 220
            rec_setting = "B"
            priority = 0
        elif is_table:
            qtype = "factual"
            complexity = "medium"
            est_comp_tokens = 200
            rec_setting = "B"
            priority = 1
        else:
            qtype = "factual"
            complexity = "low"
            est_comp_tokens = 160
            rec_setting = "B"
            priority = 1

        # 4. Determine tool execution requirement
        requires_tool = False
        tool_name = None
        tool_arg = None

        if is_formula or "attention" in query_lower:
            requires_tool = True
            tool_name = "verify_formula_context"
            tool_arg = "scaled_dot_product_attention"
        elif is_table or "bleu" in query_lower or "latency" in query_lower:
            requires_tool = True
            tool_name = "cross_reference_tables"
            tool_arg = "moshi_latency" if "moshi" in query_lower or "speech" in query_lower else "transformer_base"

        words = len(query_clean.split())
        est_prompt_tokens = max(20, int(words * 1.33) + 150)  # query + context envelope

        return RequestAnalysis(
            request_id=req_id,
            raw_query=query_clean,
            question_type=qtype,
            entities=entities,
            complexity=complexity,
            estimated_prompt_tokens=est_prompt_tokens,
            estimated_completion_tokens=est_comp_tokens,
            priority=priority,
            recommended_retrieval_setting=rec_setting,
            requires_tool=requires_tool,
            tool_name=tool_name,
            tool_arg=tool_arg
        )

