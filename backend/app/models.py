from pydantic import BaseModel
from typing import List, Optional
from enum import Enum
from datetime import datetime


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


class QueryRequest(BaseModel):
    query: str


class UpdateSuggestionRequest(BaseModel):
    status: Optional[SuggestionStatus] = None
    suggested_content: Optional[str] = None
