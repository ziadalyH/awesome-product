"""Pydantic models shared across the application."""

from pydantic import BaseModel
from typing import List, Optional
from enum import Enum
from datetime import datetime


class DocSection(BaseModel):
    """A single parsed section of a documentation page.

    Attributes:
        id: Unique slug identifier in the form ``<page_id>#<section-slug>``.
        file: The page identifier (e.g. ``"tools"``).
        section_title: Human-readable heading of the section.
        content: Full text content of the section.
        line_start: Approximate start line within the scraped page.
        line_end: Approximate end line within the scraped page.
    """

    id: str
    file: str
    section_title: str
    content: str
    line_start: int
    line_end: int


class SuggestionStatus(str, Enum):
    """Lifecycle state of an edit suggestion."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class EditSuggestion(BaseModel):
    """An AI-generated proposal to update a documentation section.

    Attributes:
        id: UUID assigned at creation.
        file: Page identifier of the affected section.
        section_title: Title of the affected section.
        current_content: Verbatim content before the edit.
        suggested_content: Proposed replacement content.
        reason: Short explanation of why the change is needed.
        status: Approval workflow state (default ``PENDING``).
    """

    id: str
    file: str
    section_title: str
    current_content: str
    suggested_content: str
    reason: str
    status: SuggestionStatus = SuggestionStatus.PENDING


class Session(BaseModel):
    """A user query session containing all generated suggestions.

    Attributes:
        session_id: UUID for the session.
        query: The original user change-request string.
        suggestions: All edit suggestions produced by the pipeline.
        created_at: UTC timestamp of creation.
        saved: Whether approved suggestions have been persisted to cache.
        retrieval_mode: The retrieval strategy used (triage/rag/hybrid/auto).
    """

    session_id: str
    query: str
    suggestions: List[EditSuggestion]
    created_at: datetime
    saved: bool = False
    retrieval_mode: str = "triage"  # which mode produced this session


class QueryRequest(BaseModel):
    """Request body for the ``POST /api/query`` endpoint.

    Attributes:
        query: Natural-language description of what changed in the API/SDK.
        retrieval_mode: Strategy used to find relevant doc sections.
    """

    query: str
    retrieval_mode: str = "triage"  # "triage" or "rag"


class UpdateSuggestionRequest(BaseModel):
    """Partial-update body for ``PATCH /api/sessions/{id}/suggestions/{id}``.

    Attributes:
        status: New approval status, if changing.
        suggested_content: Edited suggestion text, if changing.
    """

    status: Optional[SuggestionStatus] = None
    suggested_content: Optional[str] = None
