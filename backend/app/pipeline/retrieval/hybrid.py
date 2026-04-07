"""
Hybrid retrieval: intent extraction + RAG + code scan + LLM filter.
"""
import re
import logging
from typing import Dict, List

from pydantic import BaseModel
from agents import Agent, Runner

from app.models import DocSection
from app.pipeline.retrieval.base import BaseRetriever
from app.pipeline.retrieval.rag import RagRetriever


class _IntentResult(BaseModel):
    """Structured output from the intent-extraction agent."""

    code_patterns: List[str]
    reasoning: str


class _FilterResult(BaseModel):
    """Structured output from the LLM relevance filter."""

    section_ids: List[str]
    reasoning: str


class HybridRetriever(BaseRetriever):
    """Combines RAG, code scanning, and LLM filtering for high-precision retrieval.

    Pipeline:
        1. Intent extraction — identify exact code patterns to scan for.
        2. Code scan — find sections containing those patterns.
        3. RAG retrieval — semantic search over all sections.
        4. LLM filter — keep only genuinely relevant candidates.
    """

    def __init__(self, rag: RagRetriever, model: str = "gpt-4o-mini", rag_top_k: int = 20):
        """
        Args:
            rag: A pre-built ``RagRetriever`` instance.
            model: Chat model used by the intent and filter agents.
            rag_top_k: Candidate pool size for the RAG pass.
        """
        self._rag = rag
        self._model = model
        self._rag_top_k = rag_top_k
        self.logger = logging.getLogger(__name__)

    async def _extract_intent(self, query: str) -> List[str]:
        """Use an LLM to extract concrete code identifiers from the change request.

        Args:
            query: User's change-request string.

        Returns:
            List of exact code pattern strings to search for; empty on failure.
        """
        agent = Agent(
            name="Intent Extractor",
            model=self._model,
            output_type=_IntentResult,
            instructions="""You are a code-pattern extractor for an OpenAI Agents SDK documentation system.

Given a user's change request, extract the concrete code identifiers, method names,
or patterns that would appear in code blocks and need to be changed.

Examples:
- "use async/await instead of sync calls"  → ["run_sync", "Runner.run_sync"]
- "remove the as_tool() method"            → ["as_tool", ".as_tool("]
- "handoff_to is deprecated"               → ["handoff_to"]
- "rename foo to bar"                      → ["foo"]

Return:
- code_patterns: list of strings to search for in code blocks (exact substrings)
- reasoning: one line explaining what you extracted and why

If no specific code patterns can be inferred, return an empty list.""",
        )
        try:
            result = await Runner.run(agent, input=query)
            if result.final_output:
                intent: _IntentResult = result.final_output
                self.logger.info(f"Intent extraction | patterns={intent.code_patterns} | {intent.reasoning}")
                return intent.code_patterns
        except Exception as e:
            self.logger.error(f"Intent extraction failed: {e}")
        return []

    def _code_scan(self, patterns: List[str], docs: Dict[str, List[DocSection]]) -> List[str]:
        """Return IDs of sections whose code blocks contain any of ``patterns``.

        Args:
            patterns: Exact substrings to search for.
            docs: Full documentation keyed by page ID.

        Returns:
            List of matching section IDs.
        """
        if not patterns:
            return []
        hits: List[str] = []
        for page_sections in docs.values():
            for section in page_sections:
                code_blocks = re.findall(r'```[\s\S]*?```', section.content)
                searchable = '\n'.join(code_blocks) or section.content
                if any(p in searchable for p in patterns):
                    hits.append(section.id)
        self.logger.info(f"Code scan | patterns={patterns} | hits={len(hits)}")
        return hits

    async def _llm_filter(
        self, query: str, candidate_ids: List[str], docs: Dict[str, List[DocSection]]
    ) -> List[str]:
        """Filter candidate section IDs down to those that genuinely need updating.

        Args:
            query: User's change-request string.
            candidate_ids: Section IDs from the code scan + RAG pass.
            docs: Full documentation for content lookup.

        Returns:
            Subset of ``candidate_ids`` confirmed relevant by the LLM.
        """
        section_map: Dict[str, DocSection] = {
            s.id: s for page_sections in docs.values() for s in page_sections
        }
        sections_text = ""
        for sid in candidate_ids:
            sec = section_map.get(sid)
            if not sec:
                continue
            preview = sec.content[:500] + ("…" if len(sec.content) > 500 else "")
            sections_text += f"\n---\nID: {sid}\nTitle: {sec.section_title}\nContent:\n{preview}\n"

        if not sections_text:
            return []

        agent = Agent(
            name="Relevance Filter",
            model=self._model,
            output_type=_FilterResult,
            instructions=f"""You are a documentation relevance filter.

User's change request: "{query}"

Below are candidate documentation sections. Read each section's content carefully.
Return ONLY the IDs of sections that contain something that directly needs to change
to satisfy the user's request.

{sections_text}

Rules:
- Include a section only if it contains content or code that must be modified.
- Exclude sections that are only tangentially related.
- Exclude sections that already satisfy the request.

Return:
- section_ids: list of IDs that need updating (may be empty)
- reasoning: one-line explanation""",
        )
        try:
            result = await Runner.run(agent, input=query)
            if result.final_output:
                filtered: _FilterResult = result.final_output
                self.logger.info(
                    f"LLM filter | candidates={len(candidate_ids)} → kept={len(filtered.section_ids)} | {filtered.reasoning}"
                )
                return filtered.section_ids
        except Exception as e:
            self.logger.error(f"LLM filter failed, returning all candidates: {e}")
        return candidate_ids

    async def retrieve(
        self,
        query: str,
        docs: Dict[str, List[DocSection]],
        section_index: List[Dict],
    ) -> List[str]:
        """Run the full hybrid retrieval pipeline and return verified section IDs."""
        patterns = await self._extract_intent(query)

        rag_results = await self._rag.retrieve_scored(query, top_k=self._rag_top_k)
        rag_ids = [sid for sid, _ in rag_results]
        self.logger.info(f"Hybrid | RAG candidates: {len(rag_ids)}")

        code_ids = self._code_scan(patterns, docs)

        seen: set = set(code_ids)
        combined = list(code_ids)
        for sid in rag_ids:
            if sid not in seen:
                combined.append(sid)
                seen.add(sid)
        self.logger.info(f"Hybrid | combined candidates (code scan + RAG): {len(combined)}")

        verified = await self._llm_filter(query, combined, docs)
        self.logger.info(f"Hybrid | final verified sections: {len(verified)}")
        return verified
