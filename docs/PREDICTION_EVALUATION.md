# Expanded Liiga rolling historical evaluation

This is a measured retrospective experiment, not a new independent blind test or a claim of future accuracy.

Prepared: 2026-10-24T13:05:05.858420+00:00. Model version: `liiga-paper-v1-2a607bee3d28`.
Dataset fingerprint: `e001e89c2bf9ad3315a9347390ff44568e463e805368eed8b54444ef13890997`.
Scope: 10 ending-seasons of inputs; 3 prior rolling evaluation seasons.

## Input coverage

| Ending season | Returned matches | Usable completed results | Unusable completed results |
|---|---:|---:|---:|
| 2018 | 450 | 450 | 0 |
| 2019 | 450 | 450 | 0 |
| 2020 | 443 | 443 | 0 |
| 2021 | 424 | 423 | 1 |
| 2022 | 448 | 448 | 0 |
| 2023 | 450 | 450 | 0 |
| 2024 | 450 | 450 | 0 |
| 2025 | 480 | 480 | 0 |
| 2026 | 480 | 480 | 0 |
| 2027 | 544 | 131 | 0 |

Total usable historical results: **4,205**. Current-season upcoming fixtures are not training outcomes.
Ending-season 2021 has one result whose final 0–1 score conflicts with its 0–0 normal-period totals; it was excluded instead of inventing a regulation score. Shortened seasons and source omissions are not filled with synthetic matches.
These are provider-returned snapshots, not independently established full historical coverage. Raw snapshot hashes/fetch times and diagnostics are in the JSON report.

## Chronological evaluation

Rolling test years: 2024, 2025, 2026; 2023-09-12 to 2026-03-17; **1,410** predictions.
For each year, candidate/window selection and scaling use only earlier training/validation data. Test-year features may update with earlier dates inside that year, while its fitted weights stay fixed. A later origin may use earlier test-year results because they are then historical knowledge.
Pooled losses, accuracy and calibration are computed from all individual predictions, not an unweighted average of seasonal scores.
The selected-policy row describes a selection procedure whose model may vary between years. It does not test today's fixed production model on every earlier season.

| Forecast policy | Four-outcome log loss (lower better) | Brier (lower better) | Final winner accuracy | Test matches |
|---|---:|---:|---:|---:|
| Validation-selected model policy | 1.2114 | 0.6579 | 60.50% | 1,410 |
| Historical league prior | 1.2267 | 0.6721 | 54.96% | 1,410 |
| Elo baseline | 1.2086 | 0.6548 | 60.14% | 1,410 |
| Validation-selected kNN policy | 1.2214 | 0.6639 | 57.87% | 1,410 |
| Validation-selected logistic policy | 1.2050 | 0.6558 | 60.07% | 1,410 |

## Per-season validation choices

| Test ending season | Predictions | Earlier fit cutoff | Validation-selected configuration |
|---|---:|---|---|
| 2024 | 450 | 2023-03-11 | `elo` |
| 2025 | 480 | 2024-03-12 | `logistic_total_n40` |
| 2026 | 480 | 2025-03-15 | `logistic_total_n40` |

Current production configuration: `logistic_total_n40`, chosen from the latest origin's earlier validation only.
It is separately refitted on all 4,205 usable known results through 2026-10-23T16:30:00+00:00.
Neither aggregate test losses nor any one test-year result chooses the production configuration. In-sample performance of the production refit is not reported as a new test.

## Comparison with the initial experiment

The initial six-season run had 2,439 usable results and 480 test matches in ending-season 2026. The selected logistic model had 61.25% final-winner accuracy versus 63.54% for Elo.
The new experiment changes both available training history and evaluated years and reports pooled policies. Its percentages are not a like-for-like improvement/regression comparison with that initial fixed-model score. Larger evaluation samples and feature/history choices do not establish statistical superiority or guarantee future returns.
[Initial report in Git history](https://github.com/aryazeref/LocalSportsReel/blob/b6e9ecb/docs/PREDICTION_EVALUATION.md).

## Configuration and reproducibility

In ignored backend `.env`, optional settings are:

```ini
PREDICTION_HISTORY_SEASONS=10
PREDICTION_TEST_SEASONS=3
```

Restart Uvicorn with `--env-file .env` after editing. The preparation CLI also loads backend `.env` and accepts per-run overrides:

```powershell
.\.venv\Scripts\python.exe -m app.prediction.prepare --history-seasons 10 --test-seasons 3
```

CLI flags do not rewrite `.env` or change the settings of an already running API. Set the environment variables too if the API should use non-default scope. Add `--refresh` to refresh provider snapshots and retrain. Valid cached snapshots and compatible models are reused otherwise.

History includes the current season; input requests cannot precede ending-season 2000. Evaluation must leave at least two older complete seasons for training/validation. Missing requested test years cause an explicit readiness error rather than a smaller, silently substituted test set.

## Other limits are separate

- Match history requests omit the API display limit; all returned games are inspected.
- The 12 forecast cards/API maximum 30 affect output only, not training or the remaining season simulated.
- Per-team form features currently compare windows 6, 12, 24, 40. This limits each recent-form calculation, not the number of training cases. Elo retains sequential historical ratings.
- kNN uses 15, 35, 75 neighbors as candidates; it is trained with the full eligible history rather than fetching only that many matches.
- Same-day/future results and unusable outcomes are deliberately excluded. No test season can train on its own or later labels.

## Limitations

- Retrospective data has already been inspected during development; these are not newly collected blind forecasts.
- No evidence establishes reliable superiority over Elo. Compare probability losses, calibration and accuracy together; small differences need uncertainty assessment.
- Cross-season roster changes, rule/format changes and sparse-team histories limit transfer from older matches.
- Six/18-form-feature models do not yet use current injuries, starting goalies, xG or player tracking.
- Points scenarios retain frozen future strengths and conditional independence. Exact official tie-breakers/playoff meanings remain unverified; top-N bounds are not qualification/title odds.
- Calibration bins, every origin's validation candidates, source hashes and exact metrics are in [the JSON report](prediction-evaluation.json).

See [the paper review](PREDICTION_PAPER_REVIEW.md) and [input audit](PREDICTION_DATA.md).
