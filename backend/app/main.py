import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.suggestions import router as suggestions_router
from app.routes.docs import router as docs_router
from app.config import settings
from app.doc_fetcher import DocFetcher
from app.rag_retriever import RagRetriever
from app.hybrid_retriever import HybridRetriever

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

doc_fetcher = DocFetcher()
rag_retriever = RagRetriever()
hybrid_retriever = HybridRetriever(rag_retriever)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading documentation...")
    await doc_fetcher.fetch_docs()
    logger.info(f"Docs loaded — {len(doc_fetcher.docs)} pages")

    logger.info("Building RAG embeddings index...")
    try:
        await rag_retriever.build(doc_fetcher.docs)
        logger.info("RAG index ready")
    except Exception as e:
        logger.warning(f"RAG index build failed (RAG mode will be unavailable): {e}")

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
async def health():
    return {"status": "ok", "docs_loaded": len(doc_fetcher.docs)}
