# Doc Updater

AI-powered documentation update assistant for the OpenAI Agents SDK.

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 22+ with pnpm
- OpenAI API key

### 1. Backend

```bash
cd backend
cp .env.example .env   # add your OPENAI_API_KEY
pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload
```

### 2. Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

Open http://localhost:3000

---

## How it works

1. Enter a query describing what changed in the SDK (e.g. *"We removed support for agents.as_tool()"*)
2. The AI pipeline validates your query, retrieves relevant doc sections, filters out unchanged ones, and generates edit suggestions
3. Review each suggestion — compare current vs. suggested content, then approve, reject, or edit inline
4. Click **Save** — approved changes are written back to `docs_cache.json`

The pipeline typically takes 30–90 seconds to complete.

---

## Useful scripts

**Refresh the documentation cache** (re-scrapes the OpenAI Agents SDK site):

```bash
cd backend
python3 scripts/refresh_docs_cache.py
```

**Test the AI pipeline without the UI:**

```bash
cd backend
python3 scripts/test_pipeline.py "Your query here"
```

---

## Architecture

```
Next.js (port 3000) → FastAPI backend (port 8000) → AI agent pipeline
```

- `backend/` — REST API, loads docs from `docs_cache.json`, runs the AI pipeline, stores sessions in memory
- `frontend/` — query input, doc editor with inline suggestions, approve/reject/edit UI
- `docs_cache.json` — scraped documentation from the OpenAI Agents SDK; updated when suggestions are approved

---

## Known shortcuts (not production-ready)

### Sessions stored in memory
Sessions live in a plain Python dict and are lost on restart. A production version would use a persistent store (PostgreSQL or SQLite) with the `SessionStore` ABC already in place — swapping the implementation is one class.

### Docs stored as a flat JSON file
Approved suggestions overwrite `docs_cache.json` directly. A production version would store docs in a database, refresh on a schedule or via webhook, and open a pull request via the GitHub API instead of writing to a local file.

### Embeddings stored as a flat JSON file
`embeddings_cache.json` is rebuilt from scratch on every save. A production version would use a vector database (Pinecone, ChromaDB, pgvector) and only re-embed changed sections.

### Section matching uses title as join key
Suggestions are matched back to doc sections by `section_title`. If the AI rephrases a title slightly, the match silently fails. A production version would match on `section.id` (the stable `page#slug` key) end-to-end.

### No streaming progress
The frontend shows a spinner for the full pipeline run with no intermediate feedback. A production version would stream stage completion events via SSE.

### No authentication
Any request to the API is accepted. A production version would use JWT-based auth with sessions scoped to a user and an audit trail of approvals.

### Single-file frontend
All UI lives in one `page.tsx` — types, components, state, and API calls co-located. A production version would split into component files, extract API calls into a service layer, and add a shared types file.

### No diff view
The suggestion panel shows full current and suggested content as plain text in a tab switcher. TipTap is already installed but not wired up — a production version would render a word-level or line-level diff inline.

### No tests
A production version would have unit tests per pipeline stage (using mocked OpenAI responses), integration tests against a fixed doc fixture, and contract tests for frontend API calls.

### Single documentation source
The pipeline is hardwired to one source. A production version would support multiple sources (e.g. OpenAI Agents SDK and Claude docs), each with its own cache and RAG index, selectable per query.
