"""
Stages 4 & 5: Reasoning, Tool Execution, and Answer Generation for THE RELAY.
Implements multi-step synthesis, tool dispatch, and bounded reflection loops.
"""

from typing import Any, Dict, List, Optional, Tuple
from app.pipeline.request_understanding import RequestAnalysis
from app.providers.base import BaseProvider, ProviderResponse
from app.retrieval.chunking import TextChunk
from app.tools.research_tools import ResearchToolRegistry
from app.verification.answer_validator import AnswerValidator, ValidationReport

class AnswerGenerator:
    def __init__(self, provider: BaseProvider, max_reflection_loops: int = 1):
        self.provider = provider
        self.max_reflection_loops = max_reflection_loops

    def build_prompt_context(
        self,
        analysis: RequestAnalysis,
        chunks: List[TextChunk],
        tool_output: Optional[Dict[str, Any]] = None,
        feedback: Optional[str] = None
    ) -> List[Dict[str, str]]:
        system_instruction = (
            "You are THE RELAY, an adaptive AI research assistant grounded strictly in three arXiv papers:\n"
            "1. 'Attention Is All You Need' (arXiv:1706.03762v7)\n"
            "2. 'Moshi: a speech-text foundation model for real-time dialogue' (arXiv:2410.00037v1)\n"
            "3. 'Dynamic Chunking for End-to-End Hierarchical Sequence Modeling' (arXiv:2507.07955v2)\n\n"
            "CRITICAL RULES:\n"
            "- Every factual statement must cite its paper title or arXiv ID, version, and page or section.\n"
            "- If the provided evidence is insufficient or the question is outside these three papers, "
            "you must explicitly refuse by stating: 'The available research library does not provide sufficient information.'\n"
            "- Do not extrapolate, speculate, or fabricate citations.\n"
        )

        evidence_blocks = []
        for c in chunks:
            block = (
                f"--- EVIDENCE [{c.paper_title} | arXiv:{c.arxiv_id}v{c.version} | "
                f"Page {c.page_number} | {c.section_title}] ---\n{c.text}\n"
            )
            evidence_blocks.append(block)

        context_str = "\n".join(evidence_blocks)

        if tool_output and tool_output.get("status") == "found":
            context_str += f"\n--- VERIFIED TOOL CROSS-REFERENCE ---\n{tool_output}\n"

        if feedback:
            context_str += f"\n--- PREVIOUS AUDIT FEEDBACK (CORRECTION REQUIRED) ---\n{feedback}\n"

        user_content = (
            f"Question: {analysis.raw_query}\n\n"
            f"Retrieved Passages & Verified Evidence:\n{context_str}\n\n"
            "Please provide a rigorous, cited technical answer:"
        )

        return [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content}
        ]

    async def execute_reasoning_and_generation(
        self,
        analysis: RequestAnalysis,
        chunks: List[TextChunk]
    ) -> Tuple[ProviderResponse, ValidationReport, int]:
        """
        Executes multi-step reasoning, conditional tool calling, model invocation,
        and a bounded correction loop.
        """
        tool_result = None
        # 1. Tool execution step
        if analysis.requires_tool and analysis.tool_name:
            if analysis.tool_name == "verify_formula_context" and analysis.tool_arg:
                tool_result = ResearchToolRegistry.verify_formula_context(analysis.tool_arg)
            elif analysis.tool_name == "cross_reference_tables" and analysis.tool_arg:
                tool_result = ResearchToolRegistry.cross_reference_tables(analysis.tool_arg)

        # 2. Generation step
        messages = self.build_prompt_context(analysis, chunks, tool_output=tool_result)
        resp = await self.provider.generate(messages, temperature=0.2, max_tokens=analysis.estimated_completion_tokens)

        # 3. Independent Verification audit
        validation = AnswerValidator.audit(analysis, resp.content, chunks)
        loops_taken = 0

        # 4. Controlled Bounded Loop / Branch
        if validation.suggests_correction and loops_taken < self.max_reflection_loops and resp.status_code == 200:
            loops_taken += 1
            correction_messages = self.build_prompt_context(
                analysis,
                chunks,
                tool_output=tool_result,
                feedback=f"Verification audit failed: {validation.reason}. Strictly ground your claims and include valid citations."
            )
            corrected_resp = await self.provider.generate(
                correction_messages,
                temperature=0.1,
                max_tokens=analysis.estimated_completion_tokens
            )
            # Re-audit corrected response
            new_validation = AnswerValidator.audit(analysis, corrected_resp.content, chunks)
            if new_validation.is_valid or new_validation.consistency_score > validation.consistency_score:
                resp = corrected_resp
                validation = new_validation

        return resp, validation, loops_taken

