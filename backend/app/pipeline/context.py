"""Mutable state object passed through each pipeline stage."""

from dataclasses import dataclass, field
from typing import Dict, List
from app.models import DocSection, EditSuggestion


@dataclass
class PipelineContext:
    """Shared state threaded through every stage of the pipeline.

    Attributes:
        query: Original user change-request string.
        docs: Full documentation keyed by page ID.
        section_index: Flat list of ``{id, page, section}`` dicts for LLM prompts.
        target_section_ids: Section IDs selected by the retriever for editing.
        suggestions: Edit suggestions accumulated by the editor stage.
        validation_reason: Explanation returned by the validator agent.
        is_documentation_related: False if the query is entirely off-topic.
    """

    query: str
    docs: Dict[str, List[DocSection]]
    section_index: List[Dict]
    target_section_ids: List[str] = field(default_factory=list)
    suggestions: List[EditSuggestion] = field(default_factory=list)
    validation_reason: str = ""
    is_documentation_related: bool = True
