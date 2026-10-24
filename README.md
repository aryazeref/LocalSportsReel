# Local SportsReel · Hackathon MVP 0.1

**Pitch:** Discover the best sports moments happening nearby, even if you don't normally follow a league. A bounded agent discovers and ranks local structured match events, validates provenance, and creates a short grounded story.

> **Data sources:** The homepage remains a fictional sports-story demo. The separate `/liiga` page fetches real Liiga fixtures and results and displays backend-calculated team statistics. No real video clips or location tracking are included. Do not publish sample stories from the homepage as real news.

## What works in this first milestone

- City selector (Oulu, Rovaniemi, Tampere, Helsinki) and adjustable distance radius.
- Sport filter and transparent relevance ranking.
- Source-evidence integrity checks and media authorization gate.
- Story generation from facts, with an optional AI-assisted draft mode.
- Browser UI with interactive local moment cards and traceable evidence.
- Automated backend tests, mock data, and interactive API documentation.
- Real Liiga match cards, season/team filters, goals, goal difference, historical win percentage, and recent form on `/liiga`.
- Experimental pre-match probabilities, chronological model comparisons, and regular-season points scenarios on `/predictions`.

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
npm ci
npm run dev
```

Open <http://localhost:3000>. The browser calls the Python API at `http://localhost:8000`. If you change the backend URL, create `frontend/.env.local` with:

```ini
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Try the real Liiga integration

With both servers running, use the shared **Home / Liiga / Predictions** navigation bar to
switch between the fictional story homepage and real Liiga match centre. The
current page is highlighted, and all links stay visible on mobile.
On `/liiga`, select a season
and team to see fixtures and statistics calculated by FastAPI. The default is
the current Helsinki season, identified by its ending year (2027 means 2026–27;
the automatic default switches in July). Older seasons can be selected too.

The backend calls `https://prod.liiga-backend.liiga.fi/stats/api/v1/games`
with `season` and `serie=RUNKOSARJA`. No API key is required by the current public
endpoint. Set `LIIGA_API_BASE_URL` in the backend process only if the provider's
base URL changes. The default works without a local environment file. Match
and analysis endpoints share a per-process, 120-second cache. “Refresh” reloads
the page data; it may still receive a cached dataset until that expires. The
displayed fetch timestamp does not change on a cache hit.

Useful backend endpoints (also available in `/docs`):

- `GET /api/liiga/games?season=2027&limit=12`: a chronological match shortlist.
  Optional `team_id` and `from_date=YYYY-MM-DD` filters apply before the display
  limit. Current-season cards start seven days ago; other seasons start in July
  of the preceding year. This date window affects cards only.
- `GET /api/liiga/analysis?season=2027`: all teams' calculated statistics.
- `GET /api/liiga/teams/{team_id}/analysis?season=2027`: one team's statistics.
  Use the provider's complete team ID, for example `238306801:jokerit`.

Calculations use **all regular-season games returned by the provider**, without
the card limit or recent-date window. The documented v1 response has no page,
cursor, or total field, so independent completeness cannot be guaranteed. Only
completed results with valid scores and distinct team IDs count. Cancelled,
live, and upcoming games do not count. Unusable completed results are reported
as excluded. Wins include overtime and shootouts; recent form shows up to five
results, newest first. Teams without completed games have no win percentage.

After pulling backend updates, reinstall dependencies using the backend's
virtual-environment Python: `python -m pip install -r requirements.txt` (with
the virtual environment activated). Requirements include `tzdata`, which
supplies the Helsinki timezone database on Windows and systems without an
OS-provided IANA database. If startup reports `No module named 'tzdata'` or
`No time zone found with key Europe/Helsinki`, install the updated requirements
in the same virtual environment used to run Uvicorn, then restart the backend.

The `/liiga` statistics are descriptive, not forecasts. The separate `/predictions`
page provides experimental statistical forecasts and points scenarios described
below. Provider failures appear as errors; real-data routes never substitute the
fictional demo data or `json_data.json`.

The implementation is split into:

- `backend/app/services/liiga_client.py`: fetching, validation, normalization, cache.
- `backend/app/services/liiga_analysis.py`: team calculations independent of HTTP.
- `backend/app/liiga_api.py`: FastAPI routes and request validation.
- `backend/app/models.py`: typed API responses.
- `frontend/app/liiga/page.tsx`: match and analysis interface.

Run regression tests **from `backend`** with `python -m pytest -q`, and validate
the frontend from `frontend` with `npm run build`. The root `test_liiga.py` is
a manual API exploration script that writes `json_data.json`; it is not the
automated test suite.

## Match predictions and points scenarios

After pulling this feature, update Python dependencies from `backend` before
restarting the server. No additional frontend dependency or LLM key is needed:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000 --env-file .env
```

If you do not use a backend `.env`, omit `--env-file .env`. Start the frontend
as before and select **Predictions** in the navigation bar.

The first visit downloads six ending-seasons of regular-season results and
prepares the model. Later requests reuse persistent, validated raw snapshots
and a JSON model in ignored `backend/.prediction-cache/`. The cache can be
relocated using `PREDICTION_CACHE_DIR` in the backend process environment.
Historical snapshots refresh after a day; the current season after two minutes.
The model refreshes when its completed-results fingerprint changes or its
pipeline version changes. No credentials are required for the public Liiga API.

To prepare explicitly before opening the page, run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m app.prediction.prepare
```

Use `--refresh` to refresh snapshots and retrain. This prints model provenance
and evaluation; JSON artifacts and `evaluation.json` remain in the ignored cache.
The application also prepares on demand, so this command is optional.

The paper-inspired model compares recent regulation goals scored/conceded and
form ranks (six/18-feature variants) with historical-prior and Elo baselines.
Regularized logistic and kNN candidates are selected using earlier chronological
validation; the most recent prior ending-season is held out for evaluation.
Production weights are then refitted on all known results from earlier Helsinki
calendar dates. Same-day results are excluded. Cold-start clubs use a prior,
and current injuries, starting goalies and xG are not model inputs yet.

**The first measured test did not establish superiority over Elo.** The UI shows
all tested model families and probability-calibration bins. See
[the initial evaluation](docs/PREDICTION_EVALUATION.md) for actual scores and
[the JSON report](docs/prediction-evaluation.json) for provenance.

Forecasts distinguish final home/away wins from four regulation/extra-time
outcomes. Select a match and an outcome to compare baseline versus forced-result
points projections for every club. Top-N targets are **points-finish bounds**:
ties remain unresolved, so these are not exact qualification or championship
odds. Official season-specific tie-break/playoff rules are not encoded. Future
fixture probabilities stay fixed within each simulation. Sampling margins do
not include model or data uncertainty.

League scenarios require official standings to reconcile with completed results.
They pause while matches are live, past fixtures remain unresolved, or standings
and results disagree. Upcoming-match forecasts remain independently available.
Forecast/model versions are checked so a stale browser page cannot mix an old
forecast with a newly prepared scenario model.

New endpoints:

- `GET /api/liiga/predictions?limit=12`: current-season upcoming forecasts,
  evidence and historical model comparisons; optional `team_id`, limit 1–30.
- `GET /api/liiga/predictions/{game_id}/impact?top_n=4&simulations=4000`:
  baseline plus all four forced outcomes. Simulations are bounded to 1,000–10,000;
  `top_n` must be valid for the standings. Optional `model_version` rejects stale
  callers with 409. Live/unreconciled scenarios also return 409; unavailable data
  returns 502 and insufficient training history 503. No fabricated forecasts.

## Step 4 — See how the agent works

1. Open `backend/app/data.py` to inspect fake sports events and source facts.
2. Open `backend/app/agent.py`: `build_feed()` is discover → verify → rank.
3. Open `backend/app/agent.py`: `create_story()` adds optional bounded language generation.
4. Open `backend/app/main.py`: HTTP routes make those functions available to Next.js.
5. Open `frontend/app/page.tsx`: React state calls the API and renders moments.

**Optional LLM:** Story drafting supports Gemini or OpenAI. Calculations and
Liiga data do not need either provider. These drafts still describe the
**fictional homepage moments**, not real Liiga matches or predictions.

For Gemini, get a key from [Google AI Studio](https://aistudio.google.com/apikey).
Check the selected model's current [pricing](https://ai.google.dev/gemini-api/docs/pricing)
and [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits): free-tier
availability depends on model, account eligibility, and quota. The application
does not select your Google billing tier or guarantee free usage. Do not enable
paid billing if you intend to use only the available free tier.

Create or edit your ignored `backend/.env` locally (never commit or share keys):

```ini
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
```

The model is configurable; use a currently available model supporting structured
JSON output if Google changes model availability. Restart the backend from its
directory with explicit environment-file loading:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000 --env-file .env
```

On Linux/macOS, use `.venv/bin/python -m uvicorn app.main:app --reload --port 8000 --env-file .env`.

If Google returns 404 saying a model is no longer available to new users,
update `GEMINI_MODEL` in your local `.env` to the replacement specified in that
error, then restart the backend. Listing a model does not guarantee generation
access for your account. Pulling repository updates does not change an existing,
ignored `.env` file. The replacement's free-tier eligibility still needs to be
checked in your Google account.

For OpenAI instead, set `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, and optionally
`OPENAI_MODEL=gpt-4.1-mini`. If `LLM_PROVIDER` is absent, the existing OpenAI
behavior is preserved. Set `LLM_PROVIDER=template` to make no LLM calls even if
keys are present. The checked-in `.env.example` defaults to template mode.
Selecting Gemini never falls back to OpenAI or uses an OpenAI key.

Test with **Explore story** on the homepage or `POST /api/stories/oulu-001` in
`/docs`. A valid generated response has `mode=llm_draft` and
`publication_status=review_required`. Missing keys, rate limits, provider errors,
incomplete JSON, or invalid fact references use the existing template fallback
(`mode=template`). Failures log only their exception class, not keys or response
bodies. Template fallback does not prove the provider request succeeded.

Both providers must return a headline, narration, and supplied fact IDs. Schema
and ID checks do **not** guarantee factual accuracy; editorial review is still
required. Real-provider calls require a key and network access to
`generativelanguage.googleapis.com` for Gemini or `api.openai.com` for OpenAI.

## Step 5 — Upcoming milestones

Read [docs/ROADMAP.md](docs/ROADMAP.md) for an incremental plan covering official Liiga ingestion, event-to-video synchronization, trust controls, personalization, and the hackathon demo.

For the prediction feature, [docs/PREDICTION_DATA.md](docs/PREDICTION_DATA.md)
inventories the available Liiga inputs, live verification, data-quality limits,
competition rules still needed, and the proposed modelling sequence. It includes
endpoint and field appendices; richer player/xG inputs remain future extensions.
The [paper review](docs/PREDICTION_PAPER_REVIEW.md) maps Berrar, Lopes and
Dubitzky's 2024 soccer framework to a proposed Liiga feature set, evaluation
design and competition-impact extension.

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
