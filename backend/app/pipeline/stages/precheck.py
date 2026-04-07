"""Pre-check stage: filters out sections where the requested change is already applied."""

import logging
from typing import Dict, List
from pydantic import BaseModel
from agents import Agent, Runner
from app.pipeline.stages.base import BaseStage, StageAbortError
from app.pipeline.context import PipelineContext
from app.models import DocSection


class PreCheckResult(BaseModel):
    """Structured output from the pre-check agent.

    Attributes:
        already_applied_ids: Section IDs where the change is already fully reflected.
        reasoning: One-line explanation of the determination.
    """

    already_applied_ids: List[str]
    reasoning: str


class PreCheckStage(BaseStage):
    """Pipeline stage that removes sections already reflecting the requested change.

    Aborts the pipeline (via ``StageAbortError``) when all target sections are
    already up-to-date, avoiding unnecessary editor LLM calls.
    """

    def __init__(self, model: str, logger: logging.Logger):
        """
        Args:
            model: OpenAI chat model used by the pre-check agent.
            logger: Logger instance for diagnostic output.
        """
        self._model = model
        self._logger = logger

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        """Filter ``ctx.target_section_ids`` to those still needing updates.

        Args:
            ctx: Current pipeline context with target section IDs populated.

        Returns:
            Context with already-applied sections removed from ``target_section_ids``.

        Raises:
            StageAbortError: If all sections already reflect the requested change.
        """
        section_ids = ctx.target_section_ids
        if not section_ids:
            return ctx

        section_map: Dict[str, DocSection] = {
            s.id: s
            for page_sections in ctx.docs.values()
            for s in page_sections
        }

        sections_text = ""
        for sid in section_ids:
            sec = section_map.get(sid)
            if not sec:
                continue
            sections_text += f"\n---\nID: {sid}\nTitle: {sec.section_title}\nContent:\n{sec.content}\n"

        if not sections_text:
            return ctx

        agent = Agent(
            name="Pre-check Agent",
            model=self._model,
            output_type=PreCheckResult,
            instructions=f"""You are checking whether a documentation change has already been applied.

Change request: "{ctx.query}"

For each section below, determine if the change described in the request has ALREADY been fully applied to its content.

{sections_text}

Rules:
- Mark a section as already applied ONLY if its content clearly and fully reflects the requested change
- If the section partially reflects the change, or could still be improved to match the request, do NOT mark it as already applied
- Be strict: when in doubt, assume the change has NOT been applied yet

Return:
- already_applied_ids: list of section IDs where the change is already fully applied
- reasoning: one-line explanation""",
        )

        try:
            result = await Runner.run(agent, input=ctx.query)
            if result.final_output:
                pre_check: PreCheckResult = result.final_output
                already_applied = set(pre_check.already_applied_ids)
                remaining = [sid for sid in section_ids if sid not in already_applied]
                self._logger.info(
                    f"Pre-check | total={len(section_ids)} | "
                    f"already_applied={len(already_applied)} | remaining={len(remaining)} | "
                    f"{pre_check.reasoning}"
                )
                ctx.target_section_ids = remaining
        except Exception as e:
            self._logger.error(f"Pre-check failed, proceeding with all candidates: {e}")

        if not ctx.target_section_ids:
            raise StageAbortError("All sections already reflect the requested change")

        return ctx
