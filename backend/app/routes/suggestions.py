import copy
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from app.models import QueryRequest, Session, UpdateSuggestionRequest
from app.pipeline.runner import Pipeline

router = APIRouter(tags=["suggestions"])
logger = logging.getLogger(__name__)

VALID_MODES = ("triage", "rag", "hybrid", "auto")


@router.post("/query")
async def submit_query(request: Request, body: QueryRequest):
    state = request.app.state

    if body.retrieval_mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"retrieval_mode must be one of {VALID_MODES}")

    if body.retrieval_mode in ("rag", "hybrid", "auto") and not state.rag._ready:
        raise HTTPException(
            status_code=503,
            detail="RAG index is not ready. The embeddings build may have failed on startup — check backend logs.",
        )

    total_sections = sum(len(s) for s in state.doc_fetcher.docs.values())
    logger.info(
        f"Query received | mode={body.retrieval_mode} | "
        f"docs_loaded={len(state.doc_fetcher.docs)} pages | total_sections={total_sections}"
    )

    retriever = state.retrievers[body.retrieval_mode]
    pipeline = Pipeline(retriever=retriever, config=state.config, logger=logger)

    try:
        suggestions = await pipeline.run(body.query, state.doc_fetcher.docs)

        session = Session(
            session_id=str(uuid.uuid4()),
            query=body.query,
            suggestions=suggestions,
            created_at=datetime.now(timezone.utc),
            retrieval_mode=body.retrieval_mode,
        )
        state.store.save_session(session)

        if not suggestions:
            logger.info(f"No suggestions generated for query: '{body.query}'")
        else:
            logger.info(f"Session created | id={session.session_id} | suggestions={len(suggestions)}")

        return session

    except Exception as e:
        logger.error(f"Query processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process query: {str(e)}")


@router.get("/sessions")
async def list_sessions(request: Request):
    return request.app.state.store.get_all_sessions()


@router.get("/sessions/{session_id}")
async def get_session_by_id(request: Request, session_id: str):
    session = request.app.state.store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.patch("/sessions/{session_id}/suggestions/{suggestion_id}")
async def update_suggestion(
    request: Request, session_id: str, suggestion_id: str, body: UpdateSuggestionRequest
):
    store = request.app.state.store
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
async def save_session(request: Request, session_id: str):
    state = request.app.state
    session = state.store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.saved = True
    state.store.update_session(session)

    updated_docs = copy.deepcopy(state.doc_fetcher.docs)
    approved_count = 0

    for suggestion in session.suggestions:
        if suggestion.status == "approved":
            if suggestion.file in updated_docs:
                for section in updated_docs[suggestion.file]:
                    if section.section_title == suggestion.section_title:
                        section.content = suggestion.suggested_content
                        approved_count += 1
                        break

    from app.doc_fetcher import CACHE_PATH
    cache = os.path.abspath(CACHE_PATH)
    with open(cache, "w") as f:
        json.dump(
            {pid: [s.model_dump() for s in secs] for pid, secs in updated_docs.items()},
            f,
            indent=2,
        )

    state.doc_fetcher.docs = updated_docs
    await state.rag.build(state.doc_fetcher.docs)

    logger.info(f"Applied {approved_count} approved suggestions to {cache}")

    return {
        "message": "Session saved",
        "session_id": session_id,
        "approved_count": approved_count,
        "cache_updated": cache,
    }
