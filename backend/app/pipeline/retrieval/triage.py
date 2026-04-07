"""LLM-based triage retriever: selects relevant sections from the full section index."""

import logging
from typing import Dict, List
from pydantic import BaseModel
from agents import Agent, Runner
from app.pipeline.retrieval.base import BaseRetriever
from app.models import DocSection


class _TriageResult(BaseModel):
    """Structured output from the triage agent."""

    section_ids: List[str]
    reasoning: str


class TriageRetriever(BaseRetriever):
    """Retriever that asks an LLM to select sections from the full section index.

    The entire section index (capped at ``max_sections_in_prompt`` entries) is
    embedded directly in the agent's system prompt.  Best for queries that
    require understanding of overall doc structure.
    """

    def __init__(self, model: str, logger: logging.Logger, max_sections_in_prompt: int = 328):
        """
        Args:
            model: OpenAI chat model to use for the triage agent.
            logger: Logger instance for diagnostic messages.
            max_sections_in_prompt: Maximum section entries shown in the prompt.
        """
        self._model = model
        self._logger = logger
        self._max_sections = max_sections_in_prompt

    def _build_agent(self, section_index: List[Dict]) -> Agent:
        """Construct the triage ``Agent`` with the section index baked into instructions."""
        max_s = self._max_sections
        compact_index = "\n".join(
            f"{s['id']} | {s['page']} | {s['section']}"
            for s in section_index[:max_s]
        )
        remaining = len(section_index) - max_s
        remaining_note = f"\n... and {remaining} more sections." if remaining > 0 else ""

        return Agent(
            name="Triage Agent",
            model=self._model,
            output_type=_TriageResult,
            instructions=f"""You are a documentation triage specialist for the OpenAI Agents SDK.

Your job: analyze the user's change request and identify which documentation sections need updating.

Available sections (showing first {max_s}, ID | page | title):
{compact_index}{remaining_note}

INSTRUCTIONS:
1. Carefully analyze what the user wants to change
2. Identify ALL section IDs that need updates (use exact IDs from the index)
3. Return section_ids (exact IDs) and reasoning

Be thorough but precise - only include sections that genuinely need changes.""",
        )

    async def retrieve(
        self,
        query: str,
        docs: Dict[str, List[DocSection]],
        section_index: List[Dict],
    ) -> List[str]:
        """Run the triage agent and return the list of selected section IDs."""
        agent = self._build_agent(section_index)
        result = await Runner.run(agent, input=query)

        if not result.final_output:
            self._logger.error("Triage agent returned no output")
            return []

        triage: _TriageResult = result.final_output
        self._logger.info(
            f"Triage complete | identified={len(triage.section_ids)} | {triage.reasoning}"
        )
        return triage.section_ids
