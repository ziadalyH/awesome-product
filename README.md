# Doc Updater

AI-powered documentation update assistant for the OpenAI Agents SDK.

## What it does

1. User enters a query describing what changed or what to update
2. AI fetches the OpenAI Agents SDK docs from GitHub, finds relevant sections, and suggests edits
3. User reviews each suggestion: approve, reject, or edit
4. Results are saved

## Architecture

```
Next.js (port 3000) → FastAPI Backend (port 8000) → AI Agent (port 8001)
```

- **ai-agent/**: Fetches docs from GitHub, uses GPT-4o to find relevant sections and generate edit suggestions
- **backend/**: Receives queries, calls AI agent, stores sessions in memory, exposes REST API
- **frontend/**: Query input, suggestion review UI, saved results

## Running locally

### Prerequisites
- Python 3.12+
- Node.js 22+ & pnpm
- OpenAI API key

### Backend & AI Agent

```bash
# AI Agent
cd ai-agent
cp .env.example .env  # add your OPENAI_API_KEY
pip install -r requirements.txt
uvicorn src.main:app --port 8001 --reload

# Backend (new terminal)
cd backend
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

### Docker

```bash
cp .env.example .env  # add your OPENAI_API_KEY
docker compose up --build
```

## Trade-offs (conscious shortcuts)

| Decision | What was done | Production approach |
|---|---|---|
| Storage | Sessions stored in memory | PostgreSQL with Alembic migrations |
| Auth | No authentication | JWT auth via fastapi-users |
| Doc fetching | Fetch from GitHub API at startup | Cache in DB, refresh on webhook/schedule |
| Relevance | Two-step GPT-4o prompting | Vector embeddings + semantic search (ChromaDB/Pinecone) |
| Doc writing back | Suggestions stored only in app | Git commit/PR creation via GitHub API |
| Error handling | Basic try/except | Retry logic, dead-letter queue, observability |
