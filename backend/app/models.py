from pydantic import BaseModel
from typing import List, Optional
from enum import Enum
from datetime import datetime


class DocSection(BaseModel):
    id: str
    file: str
    section_title: str
    content: str
    line_start: int
    line_end: int


class SuggestionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class EditSuggestion(BaseModel):
    id: str
    file: str
    section_title: str
    current_content: str
    suggested_content: str
    reason: str
    status: SuggestionStatus = SuggestionStatus.PENDING


class Session(BaseModel):
    session_id: str
    query: str
    suggestions: List[EditSuggestion]
    created_at: datetime
    saved: bool = False
    retrieval_mode: str = "triage"  # which mode produced this session


class QueryRequest(BaseModel):
    query: str
    retrieval_mode: str = "triage"  # "triage" or "rag"


class UpdateSuggestionRequest(BaseModel):
    status: Optional[SuggestionStatus] = None
    suggested_content: Optional[str] = None
