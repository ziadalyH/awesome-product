from pydantic import BaseModel
from typing import List, Optional
from enum import Enum


class SuggestionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DocSection(BaseModel):
    file: str
    section_title: str
    content: str
    line_start: int
    line_end: int


class EditSuggestion(BaseModel):
    id: str
    file: str
    section_title: str
    current_content: str
    suggested_content: str
    reason: str
    status: SuggestionStatus = SuggestionStatus.PENDING


class QueryRequest(BaseModel):
    query: str


class SuggestionsResponse(BaseModel):
    query: str
    suggestions: List[EditSuggestion]
