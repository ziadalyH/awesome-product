"""Base classes for pipeline stages."""

from abc import ABC, abstractmethod
from app.pipeline.context import PipelineContext


class BaseStage(ABC):
    """Abstract base for a single pipeline processing step."""

    @abstractmethod
    async def run(self, ctx: PipelineContext) -> PipelineContext:
        """Process the context and return it. Raise StageAbortError to halt pipeline."""
        ...


class StageAbortError(Exception):
    """Raised by a stage to signal clean pipeline termination (not an error)."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)
