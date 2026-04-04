"""
Hybrid retrieval: intent extraction + RAG + code-pattern scan + LLM filter.

Stage 0 — Intent extraction:     LLM translates the query into concrete code
                                   patterns to search for (e.g. "sync calls" → "run_sync")
Stage 1 — RAG (semantic):        top-K sections by embedding similarity
Stage 2 — Code scan (structural): sections whose code blocks contain the extracted patterns
Stage 3 — Union:                  deduplicated combined candidates
Stage 4 — LLM filter (verify):   reads actual section content, keeps only sections
                                   that genuinely need updating
"""

import re
import logging
from typing import Dict, List, Optional

from pydantic import BaseModel
from agents import Agent, Runner

from .models import DocSection
from .rag_retriever import RagRetriever


class _IntentResult(BaseModel):
    code_patterns: List[str]
    reasoning: str


class _FilterResult(BaseModel):
    section_ids: List[str]
    reasoning: str


class HybridRetriever:
    """
    Four-stage retrieval combining intent extraction, semantic search,
    structural code scanning, and LLM-based content verification.
    """

    def __init__(self, rag: RagRetriever, model: str = "gpt-4o-mini"):
        self.rag = rag
        self.model = model
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------ #
    # Stage 0 — Intent extraction                                          #
    # ------------------------------------------------------------------ #

    async def _extract_intent(self, query: str) -> List[str]:
        """
        Ask the LLM what concrete code patterns the query refers to.
        e.g. "sync calls"  → ["run_sync", "Runner.run_sync"]
             "old API name" → ["OldClass", "old_method"]
        """
        agent = Agent(
            name="Intent Extractor",
            model=self.model,
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
                self.logger.info(
                    f"Intent extraction | patterns={intent.code_patterns} | {intent.reasoning}"
                )
                return intent.code_patterns
        except Exception as e:
            self.logger.error(f"Intent extraction failed: {e}")

        return []

    # ------------------------------------------------------------------ #
    # Stage 2 — Code scan                                                  #
    # ------------------------------------------------------------------ #

    def _code_scan(
        self, patterns: List[str], docs: Dict[str, List[DocSection]]
    ) -> List[str]:
        """
        Find sections whose code blocks (or full content) contain any of
        the extracted patterns.
        """
        if not patterns:
            return []

        hits: List[str] = []
        for page_sections in docs.values():
            for section in page_sections:
                code_blocks = re.findall(r'```[\s\S]*?```', section.content)
                searchable = ('\n'.join(code_blocks) or section.content)
                if any(p in searchable for p in patterns):
                    hits.append(section.id)

        self.logger.info(f"Code scan | patterns={patterns} | hits={len(hits)}")
        return hits

    # ------------------------------------------------------------------ #
    # Stage 4 — LLM filter                                                #
    # ------------------------------------------------------------------ #

    async def _llm_filter(
        self,
        query: str,
        candidate_ids: List[str],
        docs: Dict[str, List[DocSection]],
    ) -> List[str]:
        """
        Read actual section content and keep only sections that genuinely
        need updating. All candidates are batched into a single LLM call.
        """
        section_map: Dict[str, DocSection] = {
            s.id: s
            for page_sections in docs.values()
            for s in page_sections
        }

        sections_text = ""
        for sid in candidate_ids:
            sec = section_map.get(sid)
            if not sec:
                continue
            preview = sec.content[:500] + ("…" if len(sec.content) > 500 else "")
            sections_text += (
                f"\n---\nID: {sid}\nTitle: {sec.section_title}\nContent:\n{preview}\n"
            )

        if not sections_text:
            return []

        agent = Agent(
            name="Relevance Filter",
            model=self.model,
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
                    f"LLM filter | candidates={len(candidate_ids)} → "
                    f"kept={len(filtered.section_ids)} | {filtered.reasoning}"
                )
                return filtered.section_ids
        except Exception as e:
            self.logger.error(f"LLM filter failed, returning all candidates: {e}")

        return candidate_ids  # fallback

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    async def retrieve(
        self,
        query: str,
        docs: Dict[str, List[DocSection]],
        rag_top_k: int = 20,
    ) -> List[str]:
        """
        Full hybrid retrieval pipeline.
        Returns a deduplicated, LLM-verified list of section IDs to edit.
        """
        # Stage 0: Extract concrete code patterns from query
        patterns = await self._extract_intent(query)

        # Stage 1: RAG — semantic candidates
        rag_results = await self.rag.retrieve(query, top_k=rag_top_k)
        rag_ids = [sid for sid, _ in rag_results]
        self.logger.info(f"Hybrid | RAG candidates: {len(rag_ids)}")

        # Stage 2: Code scan — structural candidates using extracted patterns
        code_ids = self._code_scan(patterns, docs)

        # Stage 3: Union (code scan first — higher confidence, then RAG additions)
        seen: set = set(code_ids)
        combined = list(code_ids)
        for sid in rag_ids:
            if sid not in seen:
                combined.append(sid)
                seen.add(sid)
        self.logger.info(f"Hybrid | combined candidates (code scan + RAG): {len(combined)}")

        # Stage 4: LLM filter — content verification
        verified = await self._llm_filter(query, combined, docs)
        self.logger.info(f"Hybrid | final verified sections: {len(verified)}")
        return verified
