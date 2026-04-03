import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .models import QueryRequest, SuggestionsResponse
from .doc_fetcher import DocFetcher
from .suggestion_generator import SuggestionGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

doc_fetcher = DocFetcher()
suggestion_generator: SuggestionGenerator = None  # type: ignore


@asynccontextmanager
async def lifespan(app: FastAPI):
    global suggestion_generator
    suggestion_generator = SuggestionGenerator(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        logger=logger,
    )
    logger.info("Fetching OpenAI Agents SDK documentation from GitHub...")
    await doc_fetcher.fetch_docs()
    logger.info(f"Documentation loaded: {len(doc_fetcher.docs)} files")
    yield


app = FastAPI(title="Doc Update AI Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/agent/suggest", response_model=SuggestionsResponse)
async def generate_suggestions(request: QueryRequest):
    if not doc_fetcher.docs:
        raise HTTPException(status_code=503, detail="Documentation not loaded yet")
    suggestions = await suggestion_generator.generate(
        query=request.query, docs=doc_fetcher.docs
    )
    return SuggestionsResponse(query=request.query, suggestions=suggestions)


@app.get("/health")
async def health():
    return {"status": "ok", "docs_loaded": len(doc_fetcher.docs)}
