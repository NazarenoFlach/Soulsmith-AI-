# SoulSmith AI

SoulSmith AI is a Dark Souls 1 build generator with conversational refinement. Ask for a build, then keep editing it in natural language: "make the weapon lighter", "add more poise", "give it pyromancy", or "explain why this works."

The project is intentionally small enough to demo, but it is structured like a service you could keep extending.

## What It Does

- Generates complete DS1 builds with stats, equipment, rings, spells, upgrade path, and playstyle notes.
- Maintains build state per conversation so follow-up edits preserve the rest of the build.
- Uses a split JSON item catalog with Chroma-backed retrieval when `OPENAI_API_KEY` is available.
- Streams assistant responses to the UI.
- Serves item images through the backend, with generated SVG fallbacks for missing source images.

## Architecture

```text
backend/
  app/
    api/          FastAPI routers
    agent/        LangChain orchestration and prompts
    core/         config and error handling
    data/         DS1 item catalog, split item files, and build notes
    models/       Pydantic schemas
    services/     build crafting, state, RAG, images
    tools/        small domain tools used by the agent
frontend/
  app/            Next.js app shell
  components/    chat, build panel, item cards, shadcn-style primitives
  lib/           API client, shared types, utilities
```

The backend keeps deterministic build consistency in services. The item catalog is split by category under `backend/app/data/items/` so weapons, armor, rings, spells, consumables, and key items can grow independently. The agent uses LangChain for planning and final response generation, while retrieval and item lookup stay in small domain tools. If no OpenAI key is configured, the app still runs with deterministic local responses so the demo is not blocked.

## Run Locally

Fast path on Windows:

```powershell
.\start-dev.ps1
```

This starts the FastAPI backend and the Next.js frontend in separate PowerShell windows. It also creates the backend virtual environment or installs frontend dependencies when they are missing.

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

Open `http://localhost:3000`.

## OpenAI Setup

Set `OPENAI_API_KEY` in `backend/.env`.

Defaults:

```env
OPENAI_MODEL=gpt-5.4-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Without a key, RAG falls back to lexical retrieval and responses come from the deterministic build service.

## Docker

For LLM-backed responses, export `OPENAI_API_KEY` first. The stack still runs without it.

```bash
docker compose up --build
```

Frontend: `http://localhost:3000`

Backend health check: `http://localhost:8000/api/health`

## Tests

```bash
cd backend
pytest
```

The current tests cover state patching, conversational routing, fuzzy item lookup, and split catalog loading. The highest-value next tests would exercise the streaming endpoint and a full generate-then-refine conversation.

To inspect item coverage and alias conflicts:

```bash
cd backend
python scripts/audit_catalog.py
```

To stress typo-heavy item lookup:

```bash
cd backend
python scripts/stress_item_lookup.py 1000
```
