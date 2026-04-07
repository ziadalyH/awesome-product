"""Editor stage: generates edit suggestions by driving an LLM agent with tool calls."""

import uuid
import logging
from typing import Dict, List
from agents import Agent, Runner, function_tool, RunContextWrapper
from app.pipeline.stages.base import BaseStage
from app.pipeline.context import PipelineContext
from app.models import DocSection, EditSuggestion, SuggestionStatus


@function_tool
def get_section(ctx: RunContextWrapper[PipelineContext], section_id: str) -> str:
    """
    Fetch the full content of a documentation section by its ID.
    ID format: '<page>#<slug>'  e.g. 'tools#agents-as-tools'
    """
    for page_sections in ctx.context.docs.values():
        for section in page_sections:
            if section.id == section_id:
                return (
                    f"File: {section.file}\n"
                    f"Section: {section.section_title}\n\n"
                    f"{section.content}"
                )
    return f"Section '{section_id}' not found."


@function_tool
def submit_suggestion(
    ctx: RunContextWrapper[PipelineContext],
    section_id: str,
    current_content: str,
    suggested_content: str,
    reason: str,
) -> str:
    """
    Submit a documentation edit suggestion for a section.

    Args:
        section_id:        The section ID (e.g. 'tools#agents-as-tools')
        current_content:   The exact current text of the section
        suggested_content: The full updated text with changes applied
        reason:            Brief explanation of why this change is needed
    """
    file_name = section_id.split("#")[0] if "#" in section_id else section_id
    section_title = section_id

    for page_sections in ctx.context.docs.values():
        for section in page_sections:
            if section.id == section_id:
                file_name = section.file
                section_title = section.section_title
                break

    ctx.context.suggestions.append(EditSuggestion(
        id=str(uuid.uuid4()),
        file=file_name,
        section_title=section_title,
        current_content=current_content,
        suggested_content=suggested_content,
        reason=reason,
        status=SuggestionStatus.PENDING,
    ))
    return f"✓ Suggestion saved for '{section_id}'"


class EditorStage(BaseStage):
    """Pipeline stage that generates documentation edit suggestions.

    The editor agent calls ``get_section`` to read each target section and
    ``submit_suggestion`` to record proposed changes into ``ctx.suggestions``.
    """

    def __init__(self, model: str, logger: logging.Logger):
        """
        Args:
            model: OpenAI chat model used by the editor agent.
            logger: Logger instance for diagnostic output.
        """
        self._model = model
        self._logger = logger

    def _build_agent(self, target_sections: List[str]) -> Agent:
        """Construct the editor agent with the target section list in its instructions.

        Args:
            target_sections: Ordered list of section IDs to process.
        """
        section_list = "\n".join(f"- {sid}" for sid in target_sections)
        return Agent(
            name="Editor Agent",
            model=self._model,
            instructions=f"""You are a precise technical documentation editor for the OpenAI Agents SDK.

You must process these specific sections:
{section_list}

For EACH section above:
1. Call get_section(section_id) to read the current content
2. Analyze what needs to change based on the user's request
3. **IMPORTANT**: Check if the change has ALREADY been applied to the current content
4. If the change is already present, SKIP that section (do not submit a suggestion)
5. Only call submit_suggestion() if the section actually needs updating

CRITICAL RULES:
- Process ALL sections listed above
- current_content must be EXACTLY what get_section returns (verbatim)
- suggested_content must be the COMPLETE updated section text
- Only change what's necessary - preserve structure, tone, and unrelated content
- **DO NOT suggest changes that are already present in the current content**
- If a section already reflects the requested change, skip it

After processing all sections, respond with "Done processing all sections."
""",
            tools=[get_section, submit_suggestion],
        )

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        """Run the editor agent and populate ``ctx.suggestions`` with edit proposals.

        Args:
            ctx: Current pipeline context with ``target_section_ids`` populated.

        Returns:
            Context with ``suggestions`` filled in by the agent's tool calls.
        """
        target_section_ids = ctx.target_section_ids
        agent = self._build_agent(target_section_ids)
        max_turns = len(target_section_ids) * 3 + 5

        await Runner.run(
            agent,
            input=f"User request: {ctx.query}\n\nProcess the sections listed in your instructions.",
            context=ctx,
            max_turns=max_turns,
        )

        self._logger.info(f"Editor complete | suggestions={len(ctx.suggestions)}")
        if not ctx.suggestions:
            self._logger.warning("Editor agent generated no suggestions")

        return ctx
