from fastapi import APIRouter, HTTPException
from typing import Dict, List
from app.models import DocSection

router = APIRouter(tags=["docs"])


@router.get("/docs")
async def list_docs():
    from app.main import doc_fetcher
    return list(doc_fetcher.docs.keys())


@router.get("/docs/{page_id:path}")
async def get_doc(page_id: str):
    from app.main import doc_fetcher
    if page_id not in doc_fetcher.docs:
        raise HTTPException(status_code=404, detail="Page not found")
    return {
        "page_id": page_id,
        "sections": [s.model_dump() for s in doc_fetcher.docs[page_id]],
    }


@router.post("/docs/save")
async def save_docs(updated_docs: Dict[str, List[DocSection]]):
    """Save updated documentation to docs_cache.json"""
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
    
    # Reload docs in memory
    from app.main import doc_fetcher
    doc_fetcher.docs = updated_docs
    
    return {"status": "ok", "message": f"Saved {len(updated_docs)} pages to {cache}"}
