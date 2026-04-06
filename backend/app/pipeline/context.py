from dataclasses import dataclass, field
from typing import Dict, List
from app.models import DocSection, EditSuggestion


@dataclass
class PipelineContext:
    query: str
    docs: Dict[str, List[DocSection]]
    section_index: List[Dict]
    target_section_ids: List[str] = field(default_factory=list)
    suggestions: List[EditSuggestion] = field(default_factory=list)
    validation_reason: str = ""
    is_documentation_related: bool = True
