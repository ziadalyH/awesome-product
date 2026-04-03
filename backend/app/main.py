from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.suggestions import router as suggestions_router
from app.config import settings

app = FastAPI(title="Doc Update Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(suggestions_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
