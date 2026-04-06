import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.routes.suggestions import router as suggestions_router
from app.routes.docs import router as docs_router
from app.config import settings
from app.doc_fetcher import DocFetcher
from app.store.memory import InMemorySessionStore
from app.pipeline.config import DEFAULT_CONFIG
from app.pipeline.retrieval.rag import RagRetriever
from app.pipeline.retrieval.triage import TriageRetriever
from app.pipeline.retrieval.hybrid import HybridRetriever
from app.pipeline.retrieval.auto import AutoRetriever

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    doc_fetcher = DocFetcher()
    logger.info("Loading documentation...")
    await doc_fetcher.fetch_docs()
    logger.info(f"Docs loaded — {len(doc_fetcher.docs)} pages")

    rag = RagRetriever(
        embedding_model=DEFAULT_CONFIG.rag_embedding_model,
        top_k=DEFAULT_CONFIG.rag_top_k,
    )
    logger.info("Building RAG embeddings index...")
    try:
        await rag.build(doc_fetcher.docs)
        logger.info("RAG index ready")
    except Exception as e:
        logger.warning(f"RAG index build failed (RAG/hybrid/auto modes will be unavailable): {e}")

    app.state.doc_fetcher = doc_fetcher
    app.state.store = InMemorySessionStore()
    app.state.config = DEFAULT_CONFIG
    app.state.rag = rag
    app.state.retrievers = {
        "triage": TriageRetriever(
            model=DEFAULT_CONFIG.model,
            logger=logger,
            max_sections_in_prompt=DEFAULT_CONFIG.max_sections_in_prompt,
        ),
        "rag": rag,
        "hybrid": HybridRetriever(
            rag=rag,
            model=DEFAULT_CONFIG.model,
            rag_top_k=DEFAULT_CONFIG.hybrid_rag_top_k,
        ),
        "auto": AutoRetriever(
            rag=rag,
            model=DEFAULT_CONFIG.model,
            rag_top_k=DEFAULT_CONFIG.rag_top_k,
        ),
    }

    yield


app = FastAPI(title="Doc Update Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(suggestions_router, prefix="/api")
app.include_router(docs_router, prefix="/api")


@app.get("/health")
async def health(request: Request):
    return {"status": "ok", "docs_loaded": len(request.app.state.doc_fetcher.docs)}
