# macOS Setup Guide

## Quick Start

### 1. Check Python Installation

macOS comes with Python 3 pre-installed. Verify it:

```bash
python3 --version
# Should show: Python 3.9.6 or higher
```

If you see "command not found", install Python:

```bash
brew install python3
```

### 2. Set Up Backend

```bash
cd backend

# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 3. Set Up Frontend

```bash
cd frontend

# Install pnpm if you don't have it
npm install -g pnpm

# Install dependencies
pnpm install
```

### 4. Run the Application

Terminal 1 (Backend):

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --port 8000 --reload
```

Terminal 2 (Frontend):

```bash
cd frontend
pnpm dev
```

Open http://localhost:3000

## Testing the Pipeline

Test the AI pipeline without running the full app:

```bash
cd backend
source .venv/bin/activate
python3 scripts/test_pipeline.py "We removed support for agents.as_tool() method"
```

## Refreshing Documentation Cache

Update the cached documentation from the live site:

```bash
cd backend
source .venv/bin/activate
python3 scripts/refresh_docs_cache.py
```

## Common Issues

### "python: command not found"

Use `python3` instead of `python` on macOS.

### "pip: command not found"

Make sure you've activated the virtual environment:

```bash
source .venv/bin/activate
```

### "uvicorn: command not found"

Install dependencies first:

```bash
pip install -r requirements.txt
```

### Port already in use

Kill the process using the port:

```bash
# Find process on port 8000
lsof -ti:8000 | xargs kill -9

# Find process on port 3000
lsof -ti:3000 | xargs kill -9
```

## Environment Variables

Create `backend/.env` with:

```bash
OPENAI_API_KEY=sk-your-key-here
CORS_ORIGINS=["http://localhost:3000"]
```

## Troubleshooting

### Check if services are running

```bash
# Backend
curl http://localhost:8000/health

# Frontend
curl http://localhost:3000
```

### View backend logs

The backend logs will show in the terminal where you ran `uvicorn`. Look for:

- `Triage complete | identified=N sections` - Sections found
- `Editor complete | suggestions=N` - Suggestions generated
- Any ERROR lines indicate problems

### Test with curl

```bash
# Test the query endpoint
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "We removed support for agents.as_tool() method"}'
```
