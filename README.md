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

## Using the app

1. **Enter a query** — describe what changed in the SDK or what you want updated (e.g. *"We removed support for agents.as_tool()"*).
2. **Choose a retrieval mode** — pick how the AI finds relevant doc sections:
   - `triage` — LLM scans all section titles and picks the relevant ones (accurate, slower)
   - `rag` — vector similarity search (fast)
   - `hybrid` — RAG shortlists candidates, LLM re-ranks them (balanced)
   - `auto` — extracts signals from your query and picks the best strategy automatically
3. **Wait for the pipeline** — the AI validates your query, retrieves relevant sections, filters out ones that don't need changes, and generates edit suggestions for the rest (30–90 seconds depending on mode).
4. **Review suggestions** — each affected doc section appears with a suggestion panel. For each one:
   - Switch between **Current** and **Suggested** tabs to compare
   - Click **Approve** to accept, **Reject** to discard, or edit the suggested content inline before approving
5. **Save** — once you've reviewed all suggestions, click **Save**. Approved changes are written back to `docs_cache.json`.

---

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

## Trade-offs (conscious shortcuts)

### Storage

**What we did:** Sessions are stored in `InMemorySessionStore` — a plain Python dict. Everything is lost on restart.

**Production approach:** A persistent store (PostgreSQL or SQLite to start) with a proper `SessionStore` implementation. The `SessionStore` ABC is already in place — swapping the implementation is one class. Would also store `previous_content` per suggestion to enable rollback.

---

### Documentation source

**What we did:** Docs are scraped from the OpenAI Agents SDK website on first run and cached in `docs_cache.json` — a flat JSON file on disk. Approved suggestions overwrite this file directly.

**Production approach:** Store docs in a database table keyed by section ID. Refresh on a schedule or via webhook when the upstream SDK repo publishes a new release. Approved suggestions would open a pull request via the GitHub API rather than writing to a local file.

---

### Embeddings cache

**What we did:** RAG embeddings for all 329 sections are stored in `embeddings_cache.json` — a flat JSON file on disk. The cache is rebuilt from scratch every time approved suggestions are saved.

**Production approach:** Store embeddings in a vector database (Pinecone, ChromaDB, or pgvector). Invalidate and re-embed only the sections that changed, not the full corpus.

---

### Section matching

**What we did:** Suggestions are matched back to `DocSection` objects using `section_title` as the join key. If the AI slightly rephrases a title, the match silently fails and the section renders without a suggestion panel.

**Production approach:** Match on `section.id` (the stable `page#slug` key) end-to-end. The editor agent already receives section IDs — the suggestion should store and return the ID, not the title.

---

### Pipeline progress

**What we did:** The frontend shows a spinner for the full 30–90 second pipeline run with no intermediate feedback.

**Production approach:** Stream stage completion events via Server-Sent Events. The frontend would show a live progress indicator — validator done, retrieval done (N sections found), precheck done (M remaining), editor in progress (K/M sections processed).

---

### Authentication

**What we did:** No authentication. Any request to the API is accepted.

**Production approach:** JWT-based auth (e.g. `fastapi-users`). Sessions would be scoped to a user, and the suggestion approval workflow would carry an audit trail of who approved what.

---

### Frontend architecture

**What we did:** The entire frontend UI lives in a single `page.tsx` file — types, components, state, and API calls all co-located. No separate component files, no custom hooks.

**Production approach:** Split into proper component files (`SuggestionPanel`, `DocBlock`, `QueryBar`), extract API calls into a service layer or React Query hooks, and add a shared types file. This keeps each piece independently testable and maintainable.

---

### Diff view

**What we did:** The suggestion panel shows full `current_content` and `suggested_content` as plain text in a tab switcher. The reviewer has to mentally diff them.

**Production approach:** Word-level or line-level diff rendered inline, highlighting exactly what changed. TipTap is already installed in the frontend for this purpose but not yet wired up.

---

### Error handling & observability

**What we did:** Basic `try/except` blocks throughout the pipeline. Errors are logged to stdout. No retries, no alerting.

**Production approach:** Structured logging with a correlation ID per request, retry logic with exponential backoff for OpenAI API calls, dead-letter storage for failed pipeline runs, and an observability dashboard (Datadog, Grafana) for latency and error rates per pipeline stage.

---

### Tests

**What we did:** No automated tests.

**Production approach:** Unit tests for each pipeline stage in isolation (validator, retriever, precheck, editor) using mocked OpenAI responses. Integration tests for the full pipeline against a fixed doc fixture. Contract tests for the frontend API calls.

---

### Deployment

**What we did:** The backend and frontend are run as separate dev servers (`uvicorn --reload` and `pnpm dev`). No containerisation or production deployment config exists.

**Production approach:** Each service gets a production Dockerfile (multi-stage build, no `--reload`, `next build` + `next start`). A `docker-compose.yml` or Kubernetes manifests wire them together with health checks and proper secret injection. The `next.config.ts` API rewrite destination would be driven by a `BACKEND_URL` env var instead of the hardcoded `localhost:8000`.
