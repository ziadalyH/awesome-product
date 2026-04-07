"""API routes for reading and persisting documentation content."""

import json
import os
from typing import Dict, List

from fastapi import APIRouter, HTTPException, Request

from app.models import DocSection

router = APIRouter(tags=["docs"])


@router.get("/docs")
async def list_docs(request: Request):
    """Return a list of all loaded documentation page IDs."""
    return list(request.app.state.doc_fetcher.docs.keys())


@router.get("/docs/{page_id:path}")
async def get_doc(request: Request, page_id: str):
    """Return all sections for a single documentation page.

    Args:
        page_id: Path-style page identifier (e.g. ``"sessions/advanced_sqlite_session"``).

    Raises:
        HTTPException: 404 if the page ID is not found in the loaded docs.
    """
    docs = request.app.state.doc_fetcher.docs
    if page_id not in docs:
        raise HTTPException(status_code=404, detail="Page not found")
    return {"page_id": page_id, "sections": [s.model_dump() for s in docs[page_id]]}


@router.post("/docs/save")
async def save_docs(request: Request, updated_docs: Dict[str, List[DocSection]]):
    """Persist an updated docs map to ``docs_cache.json`` and update app state.

    Args:
        updated_docs: Full documentation payload keyed by page ID.
    """
    from app.doc_fetcher import CACHE_PATH
    cache = os.path.abspath(CACHE_PATH)
    with open(cache, "w") as f:
        json.dump(
            {pid: [s.model_dump() for s in secs] for pid, secs in updated_docs.items()},
            f,
            indent=2,
        )
    request.app.state.doc_fetcher.docs = updated_docs
    return {"status": "ok", "message": f"Saved {len(updated_docs)} pages to {cache}"}
