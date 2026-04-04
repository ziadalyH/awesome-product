import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from app.models import QueryRequest, Session, UpdateSuggestionRequest
from app import store
from app.agent_pipeline import run_pipeline
from app.pipeline_config import PipelineConfig

router = APIRouter(tags=["suggestions"])
logger = logging.getLogger(__name__)


@router.post("/query")
async def submit_query(request: QueryRequest):
    """Submit a query to generate documentation update suggestions.
    Set retrieval_mode to 'triage' (default) or 'rag' to compare approaches."""
    from app.main import doc_fetcher, rag_retriever, hybrid_retriever

    if request.retrieval_mode not in ("triage", "rag", "hybrid"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="retrieval_mode must be 'triage' or 'rag'")

    # Check if this exact query was already processed recently
    recent_sessions = [s for s in store.get_all_sessions() if s.saved and s.query == request.query]
    if recent_sessions:
        logger.warning(f"Query already processed recently: '{request.query}'")

    # Log the current state of docs for debugging
    total_sections = sum(len(sections) for sections in doc_fetcher.docs.values())
    logger.info(
        f"Query received | mode={request.retrieval_mode} | "
        f"docs_loaded={len(doc_fetcher.docs)} pages | total_sections={total_sections}"
    )

    if request.retrieval_mode in ("rag", "hybrid") and not rag_retriever._ready:
        raise HTTPException(
            status_code=503,
            detail="RAG index is not ready. The embeddings build may have failed on startup — check backend logs."
        )

    config = PipelineConfig(retrieval_mode=request.retrieval_mode)

    try:
        suggestions = await run_pipeline(
            query=request.query,
            docs=doc_fetcher.docs,
            logger=logger,
            config=config,
            retriever=rag_retriever if request.retrieval_mode == "rag" else None,
            hybrid_retriever=hybrid_retriever if request.retrieval_mode == "hybrid" else None,
        )
        
        if not suggestions:
            # Return empty session but with helpful message
            session = Session(
                session_id=str(uuid.uuid4()),
                query=request.query,
                suggestions=[],
                created_at=datetime.now(timezone.utc),
                retrieval_mode=request.retrieval_mode,
            )
            store.save_session(session)
            logger.info(f"No suggestions generated for query: '{request.query}'")

            # Check if it might be a validation issue
            if len(request.query.strip()) < 10:
                raise HTTPException(
                    status_code=400,
                    detail="Query too short. Please describe what changed in the codebase."
                )

            return session

        session = Session(
            session_id=str(uuid.uuid4()),
            query=request.query,
            suggestions=suggestions,
            created_at=datetime.now(timezone.utc),
            retrieval_mode=request.retrieval_mode,
        )
        store.save_session(session)
        logger.info(f"Session created | id={session.session_id} | suggestions={len(suggestions)}")
        return session
        
    except Exception as e:
        logger.error(f"Query processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process query: {str(e)}"
        )


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
    """Mark session as saved and apply approved suggestions to docs_cache.json"""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.saved = True
    store.update_session(session)
    
    # Apply approved suggestions to the documentation
    from app.main import doc_fetcher
    import copy
    
    updated_docs = copy.deepcopy(doc_fetcher.docs)
    approved_count = 0
    
    for suggestion in session.suggestions:
        if suggestion.status == "approved":
            # Find and update the section
            if suggestion.file in updated_docs:
                for section in updated_docs[suggestion.file]:
                    if section.section_title == suggestion.section_title:
                        section.content = suggestion.suggested_content
                        approved_count += 1
                        break
    
    # Save to docs_cache.json
    import json
    import os
    from app.doc_fetcher import CACHE_PATH
    
    cache = os.path.abspath(CACHE_PATH)
    with open(cache, "w") as f:
        json.dump(
            {pid: [s.model_dump() for s in secs] for pid, secs in updated_docs.items()},
            f,
            indent=2
        )
    
    # IMPORTANT: Update in-memory docs so future queries use the updated content
    doc_fetcher.docs = updated_docs

    # Rebuild RAG index so it reflects the updated content
    from app.main import rag_retriever
    await rag_retriever.build(doc_fetcher.docs)
    
    # Verify the update by checking a sample
    sample_page = list(updated_docs.keys())[0] if updated_docs else None
    if sample_page:
        sample_sections = len(updated_docs[sample_page])
        logger.info(f"In-memory docs updated | pages={len(updated_docs)} | sample_page={sample_page} has {sample_sections} sections")
    
    logger.info(f"Applied {approved_count} approved suggestions to {cache}")
    
    return {
        "message": "Session saved",
        "session_id": session_id,
        "approved_count": approved_count,
        "cache_updated": cache
    }
