"""
Pipeline runner: composes stages into an ordered execution chain.

Execution order:
  1. ValidatorStage  — reject invalid / malicious queries
  2. Retrieval       — find sections to edit (pluggable: triage / rag / hybrid / auto)
  3. PreCheckStage   — skip sections where the change is already applied
  4. EditorStage     — generate edit suggestions

StageAbortError from any stage halts execution cleanly (not an error).
"""
import logging
from typing import Dict, List

from app.models import DocSection, EditSuggestion
from app.pipeline.config import PipelineConfig
from app.pipeline.context import PipelineContext
from app.pipeline.retrieval.base import BaseRetriever
from app.pipeline.stages.base import StageAbortError
from app.pipeline.stages.validator import ValidatorStage
from app.pipeline.stages.precheck import PreCheckStage
from app.pipeline.stages.editor import EditorStage


class Pipeline:
    """Orchestrates the four-stage documentation-update pipeline.

    Stages: ValidatorStage → retriever.retrieve → PreCheckStage → EditorStage.
    A ``StageAbortError`` from any stage halts the pipeline and returns an
    empty suggestion list.
    """

    def __init__(
        self,
        retriever: BaseRetriever,
        config: PipelineConfig,
        logger: logging.Logger,
    ):
        self._retriever = retriever
        self._validator = ValidatorStage(model=config.model, logger=logger)
        self._precheck = PreCheckStage(model=config.model, logger=logger)
        self._editor = EditorStage(model=config.editor_model, logger=logger)
        self._logger = logger

    async def run(
        self,
        query: str,
        docs: Dict[str, List[DocSection]],
    ) -> List[EditSuggestion]:
        """Execute the full pipeline and return generated edit suggestions.

        Args:
            query: User's natural-language change description.
            docs: All loaded documentation sections keyed by page ID.

        Returns:
            List of ``EditSuggestion`` objects; empty if aborted or on error.
        """
        section_index = [
            {"id": s.id, "page": s.file, "section": s.section_title}
            for page_sections in docs.values()
            for s in page_sections
        ]

        self._logger.info(
            f"Pipeline start | query='{query}' | total_sections={len(section_index)}"
        )

        ctx = PipelineContext(
            query=query,
            docs=docs,
            section_index=section_index,
        )

        try:
            ctx = await self._validator.run(ctx)

            ctx.target_section_ids = await self._retriever.retrieve(query, docs, section_index)
            self._logger.info(f"Retrieval complete | sections={len(ctx.target_section_ids)}")

            if not ctx.target_section_ids:
                self._logger.warning("No sections identified for update")
                return []

            ctx = await self._precheck.run(ctx)
            ctx = await self._editor.run(ctx)

        except StageAbortError as e:
            self._logger.info(f"Pipeline aborted: {e.reason}")
            return []
        except Exception as e:
            self._logger.error(f"Pipeline error: {e}", exc_info=True)
            return []

        return ctx.suggestions
