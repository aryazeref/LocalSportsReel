# Local SportsReel · Hackathon MVP 0.1

**Pitch:** Discover the best sports moments happening nearby, even if you don't normally follow a league. A bounded agent discovers and ranks local structured match events, validates provenance, and creates a short grounded story.

> **Important:** This starter uses fictional athletes, teams, results, and match events. It contains *no real video clips*, *no location tracking*, and *no live Liiga connection*. Do not publish sample stories as real news.

## What works in this first milestone

- City selector (Oulu, Rovaniemi, Tampere, Helsinki) and adjustable distance radius.
- Sport filter and transparent relevance ranking.
- Source-evidence integrity checks and media authorization gate.
- Story generation from facts, with an optional AI-assisted draft mode.
- Browser UI with interactive local moment cards and traceable evidence.
- Automated backend tests, mock data, and interactive API documentation.

## Step 1 — Get your tools ready

Install **Node.js 22 LTS** (or any Next.js-supported recent Node), **Python 3.11+**, and VS Code. The official [Next.js App Router guide](https://nextjs.org/docs/app/getting-started) describes the framework used here.

## Step 2 — Start the Python backend

Open a terminal in `local-sportsreel/backend`. Commands:

**Linux/macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Windows PowerShell:**
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Open <http://localhost:8000/docs> for an interactive FastAPI explorer. Try `GET /api/feed?city=Oulu&radius_km=50`.

To run backend tests (same terminal, from `backend`):
```bash
python -m pytest -q
```

## Step 3 — Start the Next.js frontend

In a **second terminal**, enter `local-sportsreel/frontend`:

```bash
npm install
npm run dev
```

Open <http://localhost:3000>. The browser calls the Python API at `http://localhost:8000`. If you change the backend URL, create `frontend/.env.local` with:

```ini
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Step 4 — See how the agent works

1. Open `backend/app/data.py` to inspect fake sports events and source facts.
2. Open `backend/app/agent.py`: `build_feed()` is discover → verify → rank.
3. Open `backend/app/agent.py`: `create_story()` adds optional bounded language generation.
4. Open `backend/app/main.py`: HTTP routes make those functions available to Next.js.
5. Open `frontend/app/page.tsx`: React state calls the API and renders moments.

**Optional LLM:** Set `OPENAI_API_KEY` in the *backend process environment* (do not put it in Next.js, Git, or browser code). You can also set `OPENAI_MODEL`. Without a key, the app works offline using verified templates. With a key, the output is marked `review_required`; structured output and evidence IDs do **not** guarantee full factual validity. Editorial review is still mandatory.

Example on Linux/macOS (run before launching uvicorn):
```bash
export OPENAI_API_KEY="your-secret-key"
export OPENAI_MODEL="gpt-4.1-mini"
```

**Windows PowerShell:** `$env:OPENAI_API_KEY="your-secret-key"`.

## Step 5 — Upcoming milestones

Read [docs/ROADMAP.md](docs/ROADMAP.md) for an incremental plan covering official Liiga ingestion, event-to-video synchronization, trust controls, personalization, and the hackathon demo.

## Technical shape

```text
frontend/app/page.tsx    UI, filters, and story modal
             |
             | HTTP (JSON)
             v
backend/app/main.py     FastAPI routes
             |
             v
backend/app/agent.py    discover → verify → rank → draft
             |
             v
backend/app/data.py     synthetic dataset, later the official API adapter
```

## Before any public launch

Real-world access requires source verification, content rights, a safe process for junior athletes' information, human editorial review, secrets management, authentication, abuse protection, rate limits, monitoring, a privacy policy, and deployment configuration. This starter is **not production-ready**.
