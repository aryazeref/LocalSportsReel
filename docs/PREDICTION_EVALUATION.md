# Initial Liiga prediction evaluation

This is a measured historical experiment, not a claim of future predictive accuracy.

Prepared: 2026-10-24T12:35:44.781518+00:00. Model version: `liiga-paper-v1-bfeb6464ad57`.
Dataset fingerprint: `054ecf5317c7ec7386ac67271e34c09d938f8c68c971c6baa39fbcd79fb63d52`.

The provider returned 2,439 usable completed regular-season results across ending seasons 2022, 2023, 2024, 2025, 2026, 2027.
Raw provider snapshots and their hashes are recorded in the JSON report. Completeness and revisions remain provider-dependent.

## Selection and test design

Candidates: 34; three expanding chronological validation blocks.
Validation: 2023-09-21 to 2025-03-15, 904 match predictions.
Selection: `logistic_total_n40` by four-outcome validation log loss, before looking at the held-out test.
Test season: 2026; 2025-09-09 to 2026-03-17, 480 matches.
The held-out season was not used to select the candidate, its scaler, window or neighbor count.
Features are updated with strictly earlier calendar-day outcomes during sequential evaluation; model parameters remain fitted to the earlier training period.

## Held-out results

| Candidate | Log loss (lower better) | Brier (lower better) | Final winner accuracy | Selected by validation |
|---|---:|---:|---:|---|
| `league_prior` | 1.2071 | 0.6624 | 56.04% | No |
| `elo` | 1.1706 | 0.6349 | 63.54% | No |
| `paper_knn_total_n24_k75` | 1.2114 | 0.6590 | 59.79% | No |
| `logistic_total_n40` | 1.1821 | 0.6451 | 61.25% | Yes |

**The Elo baseline outperformed the validation-selected statistical model on this held-out season.**
This experiment does not establish a performance advantage for paper-inspired kNN or logistic features over Elo. The selected model is retained as preselected; we do not retroactively choose a winner using the test season.
Probability calibration bins and all validation candidates are in [the JSON report](prediction-evaluation.json). Accuracy alone does not measure probability quality.

## Production versus evaluation

The production model is separately refitted on all 2,439 known results through 2026-10-23T16:30:00+00:00.
Its refit includes matches from the earlier test season. The displayed test metrics belong to the earlier held-out experiment, not an independent test of those refitted weights.
On first use, another machine downloads current provider data and regenerates the evaluation/artifact; refreshed data may produce different selections and numbers.

## Scope and limitations

- Four outcomes: home regulation win, home extra-time/shootout win, away extra-time/shootout win, away regulation win.
- Six- and 18-feature candidates; recent regulation goals scored/conceded plus explicitly defined form ranks. No current injuries, starters, xG or player tracking inputs in this version.
- New/limited-history teams use an earlier-history league prior; forecasts remain experimental.
- Points scenarios reconcile official standings with completed matches and simulate all provided remaining fixtures.
- Exact official tie-breakers/playoff meanings have not been verified. Top-N values are tied-points bounds, not qualification/title odds.
- Frozen future strengths, conditional fixture independence and finite simulation sampling limit the scenarios. Sampling margins exclude model uncertainty.

## Reproduce

From `backend`, install `requirements.txt` and run:

```powershell
.\.venv\Scripts\python.exe -m app.prediction.prepare
```

The command uses validated cached snapshots when fresh. Add `--refresh` to request current snapshots and retrain. Artifacts are JSON under ignored `backend/.prediction-cache/`; no provider key or LLM is required.

See [the paper review](PREDICTION_PAPER_REVIEW.md) and [input audit](PREDICTION_DATA.md) for methodology and source limitations.
