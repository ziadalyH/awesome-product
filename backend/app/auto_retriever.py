"""
Auto retrieval: signal extraction + strategy routing.

Stage 1 — Signal Extractor:
    Strips noise from the query and extracts:
      - change_type:     rename | removal | addition | behavior_change | structural
      - old_terms:       exact terms/APIs to find in docs (e.g. ["Agent.run", "assistant"])
      - new_terms:       what they become (e.g. ["Agent.execute", "agent"])
      - affects_code:    whether code blocks need updating
      - affects_prose:   whether prose/text needs updating

Stage 2 — Strategy Router:
    rename / removal    → exact string scan (fast, no API call)
    addition / behavior → RAG (semantic search)
    structural          → triage (LLM with section index)
"""

import logging
import re
from typing import Dict, List, Literal, Tuple

from pydantic import BaseModel
from agents import Agent, Runner

from .models import DocSection
from .rag_retriever import RagRetriever


# ------------------------------------------------------------------ #
# Signal model                                                         #
# ------------------------------------------------------------------ #

class QuerySignal(BaseModel):
    change_type: Literal["rename", "removal", "addition", "behavior_change", "structural"]
    old_terms: List[str]
    new_terms: List[str]
    affects_code: bool
    affects_prose: bool
    reasoning: str


# ------------------------------------------------------------------ #
# Stage 1 — Signal Extractor                                          #
# ------------------------------------------------------------------ #

async def extract_signal(query: str, model: str = "gpt-4o-mini") -> QuerySignal:
    """
    Extract the meaningful signal from a query, stripping instruction noise.

    Examples:
      "Rename 'handoff' to 'delegation'"
        → change_type=rename, old_terms=["handoff"], new_terms=["delegation"]

      "Agent.run() has been renamed to Agent.execute()"
        → change_type=rename, old_terms=["Agent.run", ".run("], new_terms=["Agent.execute", ".execute("]

      "Remove support for as_tool=True"
        → change_type=removal, old_terms=["as_tool"], new_terms=[]

      "We added support for retries with exponential backoff"
        → change_type=addition, old_terms=[], new_terms=["retries", "exponential backoff"]

      "Clarify that agents are stateless by default"
        → change_type=behavior_change, old_terms=[], new_terms=[]

      "Split the Getting Started guide into Quickstart and Core Concepts"
        → change_type=structural, old_terms=[], new_terms=[]
    """
    agent = Agent(
        name="Signal Extractor",
        model=model,
        output_type=QuerySignal,
        instructions="""You extract the meaningful signal from a documentation change request.

Your job is to strip away the instruction noise ("rename", "we no longer", "update all", etc.)
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
- For behavior_change and structural, both can be empty or contain relevant concepts
- Keep terms concise and exact — these will be used for string matching

affects_code: true if code examples/blocks need updating
affects_prose: true if prose text (not code) needs updating

Return reasoning as one line explaining your classification.""",
    )

    result = await Runner.run(agent, input=query)
    return result.final_output


# ------------------------------------------------------------------ #
# Stage 2 — Exact String Scan                                         #
# ------------------------------------------------------------------ #

def exact_scan(
    terms: List[str],
    docs: Dict[str, List[DocSection]],
    affects_code: bool,
    affects_prose: bool,
    logger: logging.Logger,
) -> List[str]:
    """
    Scan all sections for exact term matches.
    Searches code blocks, prose, or both based on signal flags.
    Returns deduplicated list of section IDs.
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

    logger.info(f"Exact scan | terms={terms} | hits={len(hits)}")
    return hits


# ------------------------------------------------------------------ #
# Public API                                                           #
# ------------------------------------------------------------------ #

async def auto_retrieve(
    query: str,
    docs: Dict[str, List[DocSection]],
    rag_retriever: RagRetriever,
    section_index: List[Dict],
    model: str,
    rag_top_k: int,
    logger: logging.Logger,
    max_exact_scan_hits: int = 15,
) -> Tuple[List[str], QuerySignal]:
    """
    Full auto retrieval pipeline.
    Returns (section_ids, signal) where signal contains extracted metadata.
    """
    # Stage 1: Extract signal
    signal = await extract_signal(query, model)
    logger.info(
        f"Auto | change_type={signal.change_type} | "
        f"old_terms={signal.old_terms} | new_terms={signal.new_terms} | "
        f"affects_code={signal.affects_code} | affects_prose={signal.affects_prose} | "
        f"{signal.reasoning}"
    )

    # Stage 2: Route to the right strategy
    if signal.change_type in ("rename", "removal"):
        # Exact string scan — precise, no API call needed
        section_ids = exact_scan(
            signal.old_terms, docs,
            signal.affects_code, signal.affects_prose,
            logger,
        )
        # Cap results to avoid overwhelming the editor
        if len(section_ids) > max_exact_scan_hits:
            logger.warning(f"Exact scan hit cap ({len(section_ids)} > {max_exact_scan_hits}), falling back to RAG for precision")
            results = await rag_retriever.retrieve(query, top_k=rag_top_k)
            section_ids = [sid for sid, _ in results]
            logger.info(f"Auto | RAG fallback retrieved {len(section_ids)} sections")
        # Fall back to RAG if exact scan found nothing
        elif not section_ids:
            logger.warning("Exact scan returned 0 hits, falling back to RAG")
            results = await rag_retriever.retrieve(query, top_k=rag_top_k)
            section_ids = [sid for sid, _ in results]
            logger.info(f"Auto | RAG fallback retrieved {len(section_ids)} sections")

    elif signal.change_type in ("addition", "behavior_change"):
        # Semantic RAG — find where the new concept belongs
        results = await rag_retriever.retrieve(query, top_k=rag_top_k)
        section_ids = [sid for sid, _ in results]
        logger.info(f"Auto | RAG retrieved {len(section_ids)} sections")

    else:
        # structural — delegate to triage agent
        from .agent_pipeline import _build_triage_agent, TriageResult
        from .pipeline_config import PipelineConfig
        config = PipelineConfig(triage_model=model)
        triage_agent = _build_triage_agent(section_index, config)
        result = await Runner.run(triage_agent, input=query)
        triage_data: TriageResult = result.final_output
        section_ids = triage_data.section_ids
        logger.info(f"Auto | triage identified {len(section_ids)} sections")

    return section_ids, signal
