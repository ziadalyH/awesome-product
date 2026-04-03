import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from app.models import QueryRequest, Session, UpdateSuggestionRequest
from app import store, agent_client

router = APIRouter(tags=["suggestions"])


@router.post("/query")
async def submit_query(request: QueryRequest):
    """Submit a query and get AI-generated documentation update suggestions."""
    suggestions = await agent_client.get_suggestions(request.query)
    session = Session(
        session_id=str(uuid.uuid4()),
        query=request.query,
        suggestions=suggestions,
        created_at=datetime.now(timezone.utc),
    )
    store.save_session(session)
    return session


@router.get("/sessions")
async def list_sessions():
    """List all sessions (saved and unsaved)."""
    return store.get_all_sessions()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.patch("/sessions/{session_id}/suggestions/{suggestion_id}")
async def update_suggestion(
    session_id: str, suggestion_id: str, body: UpdateSuggestionRequest
):
    """Update the status or suggested_content of a single suggestion."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    for s in session.suggestions:
        if s.id == suggestion_id:
            if body.status is not None:
                s.status = body.status
            if body.suggested_content is not None:
                s.suggested_content = body.suggested_content
            store.update_session(session)
            return s

    raise HTTPException(status_code=404, detail="Suggestion not found")


@router.post("/sessions/{session_id}/save")
async def save_session(session_id: str):
    """Mark session as saved (user has finished reviewing)."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.saved = True
    store.update_session(session)
    return {"message": "Session saved", "session_id": session_id}
