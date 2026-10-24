# LocalSportsReel — context for a ChatGPT Project

Repository: https://github.com/aryazeref/LocalSportsReel
Working branch: `feature/API_integration` (case-sensitive).

This file summarizes the repository so another conversation can continue from
its current state. It contains no credentials. GitHub remains the source of
truth; uploading files to a ChatGPT Project does not synchronize future commits
or run the application.

## Product goal

Build a compelling local sports interface with real Liiga results, evidence-backed
match forecasts, and explanations of how each possible result affects other clubs.
Paid subscriptions, accounts and notifications are future work.

## Current implementation

- Next.js/React/TypeScript frontend; FastAPI/Python backend.
- Shared navigation links to Home (`/`), Liiga (`/liiga`), and Predictions (`/predictions`).
- Home is a clearly labelled fictional local-story demo. Gemini or OpenAI can
  draft those fictional stories; neither creates the numerical predictions.
- Liiga page displays real provider fixtures/results and descriptive team statistics.
- Predictions page uses statistical models and regular-season points simulations.
- The optional LLM is not yet connected to real-match forecast explanations.

## Prediction method and evaluation

The implementation is inspired by Berrar, Lopes and Dubitzky (2024), DOI
10.1007/s10994-024-06625-9. It tests six- and 18-feature representations using
historical regulation goals scored/conceded and recent-form ranks. Candidates
include kNN, regularized logistic regression, Elo, and league priors.

Defaults: 10 ending-seasons of inputs, including current; 3 prior seasons evaluated
through rolling chronological origins. At each origin, tuning uses only earlier
validation data. The latest origin's validation choice is separately refitted
on all currently known history. Pooled evaluation describes a selection policy,
not one fixed model applied retrospectively to every year. Historical data has
already been inspected, so this is retrospective evaluation, not a fresh blind test.

The measured expanded run used 4,205 usable results from ending seasons 2018–2027
and 1,410 test predictions from 2024–2026. See PREDICTION_EVALUATION.md and the JSON
report for actual losses, accuracy, per-season selections and source hashes.
More data does not automatically imply better predictions.

All feature values and neighbor pools respect earlier Helsinki calendar-day
cutoffs. Same-day results are excluded. Low-history clubs use explicit priors.
Current injuries, starting goalies and xG are not inputs to this first model.

## Competition scenarios and limitations

Four modelled outcomes: home regulation win, home extra-time/shootout win,
away extra-time/shootout win, away regulation win. Current verified Liiga points
awards are respectively 3–0, 2–1, 1–2, 0–3.

Normal scenarios reconcile official current standings with completed results.
During today's live/started games, a first request can reconstruct standings
from real completed results before Helsinki midnight and simulate all matches
from that cutoff, including today's already-started/finished games. The UI labels
this pre-game snapshot and ignores live scores and today's final results.
Future strengths are frozen within simulations. Exact current
season tie-break/playoff rules have not been verified. The UI therefore reports
points-only rank midpoints and top-N lower/upper ranges for unresolved ties.
These are not exact qualification, relegation or championship probabilities.
Unresolved older fixtures, invalid teams/results, and inconsistent official
snapshots outside pre-game snapshot mode still block scenarios.

## Data and configuration

Provider: https://prod.liiga-backend.liiga.fi/stats
Public API requests currently need no key. Core snapshots request the selected
regular season without a match limit. The forecast display limit 12/API maximum 30
only limits output cards. It does not cap training or remaining-match simulations.
Candidate per-team form windows are 6, 12, 24, 40; this is separate from dataset size.

Backend environment settings:

```ini
PREDICTION_HISTORY_SEASONS=10
PREDICTION_TEST_SEASONS=3
```

History includes the current season. Keep at least two complete earlier seasons
for training/validation before the first test season. Input requests cannot
precede the supported ending-season 2000. Not all eras have equally complete data.
Snapshots/models are validated JSON under ignored `backend/.prediction-cache/`.
They are regenerated locally, not committed to Git. A settings or pipeline change
invalidates incompatible artifacts. Optional `PREDICTION_CACHE_DIR` relocates it.

## Local Windows workflow

From project root:

```powershell
git switch feature/API_integration
git pull --ff-only origin feature/API_integration
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000 --env-file .env
```

In another terminal, from `frontend`, run `npm run dev`. First prediction visit prepares the history
and model; later visits reuse the cache. Alternatively prepare from backend:

```powershell
.\.venv\Scripts\python.exe -m app.prediction.prepare --history-seasons 10 --test-seasons 3
```

CLI overrides apply to that preparation run; set the environment variables too
if the API should use the same non-default scope. The CLI loads backend `.env`.

Run automated tests from backend with `python -m pytest -q`; the root
`test_liiga.py` is a manual exploration script, not that suite. Frontend validation
is `npm run build`. Backend requirements include tzdata (needed on Windows),
numpy, scikit-learn and threadpoolctl. Use the same virtual-environment interpreter
for dependency installation and Uvicorn.

## Useful files to add to a ChatGPT Project

- This context file and README.md.
- docs/PREDICTION_DATA.md — API fields, endpoints and data-quality limitations.
- docs/PREDICTION_PAPER_REVIEW.md — paper analysis and hockey adaptation.
- docs/PREDICTION_EVALUATION.md and docs/prediction-evaluation.json — measured results.
- Relevant source files when requesting implementation changes.

Keep `.env` and API keys out of uploaded context and Git.
