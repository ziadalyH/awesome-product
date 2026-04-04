# Doc Updater

AI-powered documentation update assistant for the OpenAI Agents SDK.

## What it does

1. User enters a query describing what changed or what to update
2. AI analyzes the cached documentation (`docs_cache.json`), finds relevant sections, and suggests edits
3. User reviews each suggestion in the editor: approve, reject, or edit
4. Approved changes are saved back to `docs_cache.json`

## Architecture

```
Next.js (port 3000) → FastAPI Backend (port 8000) → AI Agent Pipeline
```

- **backend/**: REST API, loads docs from `docs_cache.json`, calls AI agent pipeline, stores sessions in memory
- **frontend/**: Query input, documentation editor with inline suggestions, approve/reject/edit UI
- **docs_cache.json**: Cached documentation scraped from OpenAI Agents SDK (updated when suggestions are approved)

## Running locally

> **macOS Users:** See [SETUP_MACOS.md](SETUP_MACOS.md) for detailed setup instructions.

### Prerequisites

- Python 3.12+
- Node.js 22+ & pnpm
- OpenAI API key

### Backend

```bash
cd backend
cp .env.example .env  # add your OPENAI_API_KEY
pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

Open http://localhost:3000

### Refreshing the documentation cache

The `docs_cache.json` file contains scraped documentation from the OpenAI Agents SDK. To refresh it:

```bash
cd backend
python3 scripts/refresh_docs_cache.py
```

### Testing the AI pipeline

To test the agent pipeline locally without running the full app:

```bash
cd backend
python3 scripts/test_pipeline.py "Your query here"

# Example:
python3 scripts/test_pipeline.py "We removed support for agents.as_tool() method"
```

This will show you what sections the AI identifies and what suggestions it generates.

### Docker

```bash
cp .env.example .env  # add your OPENAI_API_KEY
docker compose up --build
```

## Trade-offs (conscious shortcuts)

| Decision       | What was done                                | Production approach                                     |
| -------------- | -------------------------------------------- | ------------------------------------------------------- |
| Storage        | Sessions stored in memory                    | PostgreSQL with Alembic migrations                      |
| Auth           | No authentication                            | JWT auth via fastapi-users                              |
| Doc source     | Cached in `docs_cache.json` at startup       | Cache in DB, refresh on webhook/schedule                |
| Relevance      | Two-step GPT-4o prompting with section index | Vector embeddings + semantic search (ChromaDB/Pinecone) |
| Doc updates    | Manual approval, saved to `docs_cache.json`  | Git commit/PR creation via GitHub API                   |
| Error handling | Basic try/except                             | Retry logic, dead-letter queue, observability           |
