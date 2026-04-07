"""
Auto retrieval: signal extraction + strategy routing.

rename/removal    → exact string scan (fast, free)
addition/behavior → RAG (semantic)
structural        → triage (LLM with section index)
"""
import logging
import re
from typing import Dict, List, Literal

from pydantic import BaseModel
from agents import Agent, Runner

from app.models import DocSection
from app.pipeline.retrieval.base import BaseRetriever
from app.pipeline.retrieval.rag import RagRetriever


class _QuerySignal(BaseModel):
    """Structured signal extracted from the user query by the signal-extraction agent."""

    change_type: Literal["rename", "removal", "addition", "behavior_change", "structural"]
    old_terms: List[str]
    new_terms: List[str]
    affects_code: bool
    affects_prose: bool
    reasoning: str


class _TriageResult(BaseModel):
    """Structured output from the triage fallback agent."""

    section_ids: List[str]
    reasoning: str


class AutoRetriever(BaseRetriever):
    """Automatically selects a retrieval strategy based on the query's change type.

    Strategy routing:
        - ``rename`` / ``removal`` → exact string scan (then RAG fallback if 0 or too many hits).
        - ``addition`` / ``behavior_change`` → RAG semantic retrieval.
        - ``structural`` → LLM triage over the full section index.
    """

    def __init__(
        self,
        rag: RagRetriever,
        model: str = "gpt-4o-mini",
        rag_top_k: int = 10,
        max_exact_scan_hits: int = 15,
    ):
        """
        Args:
            rag: Pre-built ``RagRetriever`` instance.
            model: Chat model used by signal-extraction and triage agents.
            rag_top_k: Number of sections returned by the RAG pass.
            max_exact_scan_hits: Cap before exact scan falls back to RAG.
        """
        self._rag = rag
        self._model = model
        self._rag_top_k = rag_top_k
        self._max_exact_scan_hits = max_exact_scan_hits
        self.logger = logging.getLogger(__name__)

    async def _extract_signal(self, query: str) -> _QuerySignal:
        """Ask an LLM to classify the query and extract old/new terms.

        Args:
            query: User's change-request string.

        Returns:
            A ``_QuerySignal`` describing the change type and searchable terms.
        """
        agent = Agent(
            name="Signal Extractor",
            model=self._model,
            output_type=_QuerySignal,
            instructions="""You extract the meaningful signal from a documentation change request.

Strip away the instruction noise ("rename", "we no longer", "update all", etc.)
and identify the concrete entities that need to be found and changed in documentation.

Change types:
- rename:           a term or API is being renamed (old → new)
- removal:          a feature/term is being removed entirely
- addition:         a new feature/concept is being added
- behavior_change:  existing behavior is changing but no rename
- structural:       reorganization of docs (splitting, moving, grouping sections)

Rules for old_terms / new_terms:
- Include ALL forms of the term: e.g. for "Agent.run()" include ["Agent.run", ".run(", "run_sync"]
- For renames, old_terms = what to search for, new_terms = what it becomes
- For removals, old_terms = what to find and remove, new_terms = []
- For additions, old_terms = [], new_terms = the new concept/feature names
- Keep terms concise and exact — these will be used for string matching

affects_code: true if code examples/blocks need updating
affects_prose: true if prose text (not code) needs updating

Return reasoning as one line explaining your classification.""",
        )
        result = await Runner.run(agent, input=query)
        return result.final_output

    def _exact_scan(
        self,
        terms: List[str],
        docs: Dict[str, List[DocSection]],
        affects_code: bool,
        affects_prose: bool,
    ) -> List[str]:
        """Return IDs of sections containing any of the given terms.

        Args:
            terms: Exact substrings to search for.
            docs: Full documentation keyed by page ID.
            affects_code: Search within fenced code blocks when True.
            affects_prose: Search within prose text when True.

        Returns:
            List of matching section IDs.
        """
        if not terms:
            return []
        hits: List[str] = []
        for page_sections in docs.values():
            for section in page_sections:
                code_blocks = re.findall(r'```[\s\S]*?```', section.content)
                prose = re.sub(r'```[\s\S]*?```', '', section.content)
                searchable = ""
                if affects_code:
                    searchable += "\n".join(code_blocks)
                if affects_prose:
                    searchable += prose
                if any(term in searchable for term in terms):
                    hits.append(section.id)
        self.logger.info(f"Exact scan | terms={terms} | hits={len(hits)}")
        return hits

    async def _rag_fallback(self, query: str, reason: str) -> List[str]:
        """Fall back to RAG retrieval and log the reason.

        Args:
            query: User's change-request string.
            reason: Human-readable explanation for why exact scan was bypassed.

        Returns:
            Top-k section IDs from the RAG retriever.
        """
        self.logger.warning(f"Exact scan {reason}, falling back to RAG")
        results = await self._rag.retrieve_scored(query, top_k=self._rag_top_k)
        ids = [sid for sid, _ in results]
        self.logger.info(f"Auto | RAG fallback retrieved {len(ids)} sections")
        return ids

    async def _triage_fallback(self, query: str, section_index: List[Dict]) -> List[str]:
        """Use an LLM triage agent to identify sections for structural changes.

        Args:
            query: User's change-request string.
            section_index: Flat list of ``{id, page, section}`` dicts.

        Returns:
            Section IDs selected by the triage agent.
        """
        max_s = 328
        compact_index = "\n".join(
            f"{s['id']} | {s['page']} | {s['section']}"
            for s in section_index[:max_s]
        )
        remaining = len(section_index) - max_s
        note = f"\n... and {remaining} more sections." if remaining > 0 else ""

        agent = Agent(
            name="Triage Agent",
            model=self._model,
            output_type=_TriageResult,
            instructions=f"""Identify which documentation sections need updating for this change request.

Available sections (ID | page | title):
{compact_index}{note}

Return section_ids (exact IDs) and reasoning.""",
        )
        result = await Runner.run(agent, input=query)
        if result.final_output:
            data: _TriageResult = result.final_output
            self.logger.info(f"Auto | triage identified {len(data.section_ids)} sections")
            return data.section_ids
        return []

    async def retrieve(
        self,
        query: str,
        docs: Dict[str, List[DocSection]],
        section_index: List[Dict],
    ) -> List[str]:
        """Extract the query signal and dispatch to the appropriate retrieval strategy."""
        signal = await self._extract_signal(query)
        self.logger.info(
            f"Auto | change_type={signal.change_type} | "
            f"old_terms={signal.old_terms} | new_terms={signal.new_terms} | "
            f"affects_code={signal.affects_code} | affects_prose={signal.affects_prose} | "
            f"{signal.reasoning}"
        )

        if signal.change_type in ("rename", "removal"):
            ids = self._exact_scan(signal.old_terms, docs, signal.affects_code, signal.affects_prose)
            if not ids:
                return await self._rag_fallback(query, "returned 0 hits")
            if len(ids) > self._max_exact_scan_hits:
                return await self._rag_fallback(query, f"hit cap ({len(ids)} > {self._max_exact_scan_hits})")
            return ids

        elif signal.change_type in ("addition", "behavior_change"):
            results = await self._rag.retrieve_scored(query, top_k=self._rag_top_k)
            ids = [sid for sid, _ in results]
            self.logger.info(f"Auto | RAG retrieved {len(ids)} sections")
            return ids

        else:  # structural
            return await self._triage_fallback(query, section_index)
