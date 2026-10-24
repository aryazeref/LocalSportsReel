"""Chronological selection/evaluation and JSON-only model artifacts.

Validation chooses the candidate. The held-out test season is never used for
selection. A separately marked production refit uses all supplied known history.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
from typing import Iterable

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from .domain import HELSINKI, Match, OUTCOMES
from .features import MIN_HISTORY, build_feature_rows, build_state, effective_day, validated_history

ARTIFACT_VERSION = 1
WINDOWS = (6, 12, 24, 40)
NEIGHBORS = (15, 35, 75)
MIN_TRAIN_ROWS = 80


def _distribution(value) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.shape != (4,) or not np.isfinite(array).all() or (array < 0).any() or array.sum() <= 0:
        raise ValueError("Invalid four-outcome probability distribution")
    array = np.maximum(array, 1e-12)
    return array / array.sum()


def probability_metrics(labels: Iterable[int], probabilities) -> dict:
    y = np.asarray(list(labels), dtype=int)
    p = np.asarray([_distribution(row) for row in probabilities])
    if not len(y) or len(p) != len(y):
        raise ValueError("Metrics require completed predictions and labels")
    truth = np.eye(4)[y]
    home = p[:, :2].sum(axis=1)
    regulation_p = np.column_stack((p[:, 0], p[:, 1] + p[:, 2], p[:, 3]))
    regulation_y = np.where(y == 0, 0, np.where(y == 3, 2, 1))
    regulation_truth = np.eye(3)[regulation_y]
    bins = []
    bin_indices = np.minimum((home * 5).astype(int), 4)
    for index in range(5):
        low = index / 5
        mask = bin_indices == index
        count = int(mask.sum())
        bins.append({
            "lower": round(float(low), 1), "upper": round(float(low + 0.2), 1),
            "count": count,
            "predicted": float(home[mask].mean()) if count else None,
            "observed": float((y[mask] < 2).mean()) if count else None,
        })
    return {
        "count": len(y),
        "log_loss": float(-np.log(p[np.arange(len(y)), y]).mean()),
        "brier": float(((p - truth) ** 2).sum(axis=1).mean()),
        "final_winner_accuracy": float(((home >= 0.5) == (y < 2)).mean()),
        "outcome_accuracy": float((p.argmax(axis=1) == y).mean()),
        "regulation_rps": float(0.5 * ((np.cumsum(regulation_p, axis=1)[:, :2]
                                        - np.cumsum(regulation_truth, axis=1)[:, :2]) ** 2).sum(axis=1).mean()),
        "calibration_bins": bins,
        "expected_calibration_error": float(sum(
            row["count"] / len(y) * abs(row["predicted"] - row["observed"])
            for row in bins if row["count"]
        )),
    }


def _specs() -> list[dict]:
    candidates = [
        {"name": "league_prior", "algorithm": "prior", "window": 12, "feature_set": "total"},
        {"name": "elo", "algorithm": "elo", "window": 12, "feature_set": "total"},
    ]
    for feature_set in ("total", "homeaway"):
        for window in WINDOWS:
            candidates.append({
                "name": f"logistic_{feature_set}_n{window}", "algorithm": "logistic",
                "window": window, "feature_set": feature_set, "C": 0.5,
            })
            for k in NEIGHBORS:
                candidates.append({
                    "name": f"paper_knn_{feature_set}_n{window}_k{k}", "algorithm": "knn",
                    "window": window, "feature_set": feature_set, "k": k,
                })
    return candidates


def _fit(spec: dict, rows: list[dict]) -> dict:
    eligible = [row for row in rows if not row["cold_start"]]
    if len(eligible) < MIN_TRAIN_ROWS:
        raise ValueError(f"At least {MIN_TRAIN_ROWS} training matches with six prior games per club are required")
    prior = np.bincount([row["label"] for row in rows], minlength=4).astype(float) + 1
    prior /= prior.sum()
    model = {"spec": dict(spec), "prior": prior.tolist(), "training_rows": len(eligible)}
    if spec["algorithm"] in ("prior", "elo"):
        return model
    x = np.asarray([row["features"] for row in eligible], dtype=float)
    y = np.asarray([row["label"] for row in eligible])
    scaler = StandardScaler().fit(x)
    x = scaler.transform(x)
    model.update(mean=scaler.mean_.tolist(), scale=scaler.scale_.tolist())
    if spec["algorithm"] == "knn":
        model.update(training_features=x.tolist(), labels=y.tolist())
    else:
        if len(np.unique(y)) < 2:
            raise ValueError("Logistic training requires at least two outcome classes")
        with threadpool_limits(limits=2):
            regression = LogisticRegression(C=spec.get("C", 0.5), max_iter=500, solver="lbfgs").fit(x, y)
        model.update(coefficients=regression.coef_.tolist(), intercept=regression.intercept_.tolist(),
                     classes=regression.classes_.tolist())
    return model


def _predict_row(model: dict, row: dict) -> np.ndarray:
    spec = model["spec"]
    if row["cold_start"] or spec["algorithm"] == "prior":
        return _distribution(row["prior"])
    if spec["algorithm"] == "elo":
        return _distribution(row["elo"])
    vector = (np.asarray(row["features"]) - np.asarray(model["mean"])) / np.asarray(model["scale"])
    prior = np.asarray(model["prior"])
    if spec["algorithm"] == "knn":
        training = model.get("_training_array")
        if training is None:
            training = np.asarray(model["training_features"])
        distances = ((training - vector) ** 2).sum(axis=1)
        k = min(spec["k"], len(training))
        nearest = np.argsort(distances, kind="stable")[:k]
        labels = model.get("_labels_array")
        if labels is None:
            labels = np.asarray(model["labels"])
        counts = np.bincount(labels[nearest], minlength=4)
        return _distribution((counts + 3 * prior) / (k + 3))
    scores = np.asarray(model["coefficients"]) @ vector + np.asarray(model["intercept"])
    classes = np.asarray(model["classes"], dtype=int)
    if len(classes) == 2:
        positive = 1 / (1 + np.exp(-np.clip(scores[0], -700, 700)))
        values = np.array([1 - positive, positive])
    else:
        values = np.exp(scores - np.max(scores))
        values /= values.sum()
    result = 0.02 * prior
    result[classes] += 0.98 * values
    return _distribution(result)


def _runtime_model(model: dict) -> dict:
    runtime = dict(model)
    if model["spec"]["algorithm"] == "knn":
        runtime["_training_array"] = np.asarray(model["training_features"])
        runtime["_labels_array"] = np.asarray(model["labels"], dtype=int)
    return runtime


def _predict_rows(model: dict, rows: list[dict]) -> list[np.ndarray]:
    runtime = _runtime_model(model)
    return [_predict_row(runtime, row) for row in rows]


def _range(rows: list[dict]) -> dict:
    return {
        "start": min(row["match"].day for row in rows).isoformat(),
        "end": max(row["match"].day for row in rows).isoformat(),
        "count": len(rows),
        "cold_start_matches": sum(row["cold_start"] for row in rows),
    }


def _folds(rows: list[dict]) -> list[tuple[list[dict], list[dict]]]:
    days = sorted({row["match"].day for row in rows})
    if len(days) < 20:
        raise ValueError("At least 20 distinct pre-test match dates are required")
    # Expanding fits, three disjoint later validation blocks; no random split.
    cuts = [int(len(days) * fraction) for fraction in (0.55, 0.70, 0.85, 1.0)]
    result = []
    for left, right in zip(cuts, cuts[1:]):
        train = [row for row in rows if row["match"].day < days[left]]
        selected = set(days[left:right])
        valid = [row for row in rows if row["match"].day in selected]
        if sum(not row["cold_start"] for row in train) >= MIN_TRAIN_ROWS and valid:
            result.append((train, valid))
    if not result:
        raise ValueError("Insufficient earlier history for chronological validation")
    return result


@dataclass
class ModelBundle:
    model: dict
    metadata: dict
    report: dict

    def to_dict(self) -> dict:
        return {"artifact_version": ARTIFACT_VERSION, "model": self.model,
                "metadata": self.metadata, "report": self.report}

    @classmethod
    def from_dict(cls, value: dict) -> "ModelBundle":
        if not isinstance(value, dict) or any(not isinstance(value.get(key), dict) for key in ("model", "metadata", "report")):
            raise ValueError("Prediction artifact must contain model, metadata and report objects")
        if value.get("artifact_version") != ARTIFACT_VERSION:
            raise ValueError("Unsupported prediction artifact version")
        if tuple(value["metadata"].get("outcomes", ())) != OUTCOMES:
            raise ValueError("Prediction artifact outcome order differs")
        model = value["model"]
        spec = model.get("spec")
        if not isinstance(spec, dict):
            raise ValueError("Prediction artifact must contain a model specification")
        if spec["algorithm"] not in ("knn", "logistic", "prior", "elo"):
            raise ValueError("Unsupported prediction algorithm")
        if spec.get("feature_set") not in ("total", "homeaway") or not isinstance(spec.get("window"), int) or spec["window"] < 6:
            raise ValueError("Invalid prediction feature specification")
        _distribution(model["prior"])
        trained = datetime.fromisoformat(value["metadata"]["training_cutoff"])
        if trained.tzinfo is None:
            raise ValueError("Artifact training cutoff must include a timezone")
        if spec["algorithm"] in ("knn", "logistic"):
            dimension = 6 if spec["feature_set"] == "total" else 18
            mean, scale = np.asarray(model["mean"], dtype=float), np.asarray(model["scale"], dtype=float)
            if mean.shape != (dimension,) or scale.shape != (dimension,) or not np.isfinite(mean).all() or not np.isfinite(scale).all() or (scale <= 0).any():
                raise ValueError("Invalid artifact scaling parameters")
            if spec["algorithm"] == "knn":
                matrix, labels = np.asarray(model["training_features"]), np.asarray(model["labels"])
                if matrix.ndim != 2 or matrix.shape[1] != dimension or len(matrix) != len(labels) or not len(labels) or not np.isfinite(matrix).all() or labels.dtype.kind not in "iu" or (labels < 0).any() or (labels > 3).any() or spec.get("k", 0) <= 0:
                    raise ValueError("Invalid artifact neighbor data")
            else:
                matrix, intercept, classes = np.asarray(model["coefficients"]), np.asarray(model["intercept"]), np.asarray(model["classes"])
                rows = 1 if len(classes) == 2 else len(classes)
                if len(classes) < 2 or len(classes) > 4 or len(np.unique(classes)) != len(classes) or classes.dtype.kind not in "iu" or (classes < 0).any() or (classes > 3).any() or matrix.shape != (rows, dimension) or intercept.shape != (rows,) or not np.isfinite(matrix).all() or not np.isfinite(intercept).all():
                    raise ValueError("Invalid artifact regression parameters")
        return cls(value["model"], value["metadata"], value["report"])

    def _guard(self, fixture: Match, cutoff: datetime | None) -> date:
        day = effective_day(fixture, cutoff)
        trained = datetime.fromisoformat(self.metadata["training_cutoff"]).astimezone(HELSINKI).date()
        if day <= trained:
            raise ValueError("This artifact contains later training outcomes; retrain with an earlier cutoff for historical forecasts")
        if fixture.status != "upcoming" or not fixture.home_id or not fixture.away_id or fixture.home_id == fixture.away_id:
            raise ValueError("Pre-match predictions require a scheduled match between distinct known teams")
        if cutoff is not None and fixture.start <= cutoff:
            raise ValueError("The selected match has already started at the prediction cutoff")
        return day

    def predict(self, history: list[Match], fixture: Match, *, cutoff: datetime | None = None) -> dict:
        return self.predict_many(history, [fixture], cutoff=cutoff)[0]

    def predict_many(self, history: list[Match], fixtures: list[Match], *, cutoff: datetime | None = None) -> list[dict]:
        if not fixtures:
            return []
        states, results = {}, []
        spec = self.model["spec"]
        runtime = _runtime_model(self.model)
        for fixture in fixtures:
            day = self._guard(fixture, cutoff)
            if day not in states:
                states[day] = build_state(history, day)
            state = states[day]
            profile = state.profile(fixture, spec["window"], spec["feature_set"])
            row = {**profile, "prior": state.prior, "elo": state.elo_probability(fixture)}
            probabilities = _predict_row(runtime, row)
            results.append({
                **profile, "probabilities": probabilities.tolist(),
                "home_win": float(probabilities[:2].sum()),
                "away_win": float(probabilities[2:].sum()),
                "regulation_tie": float(probabilities[1:3].sum()),
                "model_name": spec["name"], "model_version": self.metadata["model_version"],
                "cutoff": day.isoformat(),
            })
        return results


def _evaluate_origin(
    rows_by_key: dict[tuple, list[dict]], specs: list[dict], season: int,
) -> tuple[dict, dict, dict[str, tuple[list[int], list[np.ndarray]]]]:
    """Select exclusively on earlier dates, then evaluate one subsequent season."""
    first_rows = next(iter(rows_by_key.values()))
    test_start = min(row["match"].day for row in first_rows if row["match"].season == season)
    prior_history = [row for row in first_rows if row["match"].day < test_start]
    if len(prior_history) < 150:
        raise ValueError(f"Insufficient completed matches before held-out season {season}")
    candidates: list[dict] = []
    validation_predictions: dict[str, tuple[list, list, list]] = {}
    for spec in specs:
        rows = rows_by_key[spec["window"], spec["feature_set"]]
        prior_rows = [row for row in rows if row["match"].day < test_start]
        labels, probabilities, valid_rows = [], [], []
        try:
            for training, validation in _folds(prior_rows):
                model = _fit(spec, training)
                probabilities.extend(_predict_rows(model, validation))
                labels.extend(row["label"] for row in validation)
                valid_rows.extend(validation)
        except ValueError:
            continue
        metrics = probability_metrics(labels, probabilities)
        candidates.append({**spec, **{k: v for k, v in metrics.items() if k != "calibration_bins"}})
        validation_predictions[spec["name"]] = (labels, probabilities, valid_rows)
    if not candidates:
        raise ValueError(f"No model could be evaluated before held-out season {season}")
    candidates.sort(key=lambda item: (item["log_loss"], item["brier"], item["name"]))
    specs_by_name = {spec["name"]: spec for spec in specs}
    selected = specs_by_name[candidates[0]["name"]]
    policy_specs = {"selected_policy": selected}
    for algorithm, policy in (("prior", "league_prior"), ("elo", "elo"),
                              ("knn", "knn_policy"), ("logistic", "logistic_policy")):
        best = next((item for item in candidates if item["algorithm"] == algorithm), None)
        if best:
            policy_specs[policy] = specs_by_name[best["name"]]
    compared = {spec["name"] for spec in policy_specs.values()}
    test_metrics, predictions_by_spec = [], {}
    test_rows_selected = None
    for spec in specs:
        if spec["name"] not in compared:
            continue
        rows = rows_by_key[spec["window"], spec["feature_set"]]
        training = [row for row in rows if row["match"].day < test_start]
        testing = [row for row in rows if row["match"].season == season]
        fitted = _fit(spec, training)
        probabilities = _predict_rows(fitted, testing)
        labels = [row["label"] for row in testing]
        metrics = probability_metrics(labels, probabilities)
        test_metrics.append({**spec, **metrics, "selected": spec["name"] == selected["name"]})
        predictions_by_spec[spec["name"]] = labels, probabilities
        if spec["name"] == selected["name"]:
            test_rows_selected = testing
    selected_rows = rows_by_key[selected["window"], selected["feature_set"]]
    _, _, valid_rows = validation_predictions[selected["name"]]
    validation = {
        **_range(valid_rows),
        "folds": len(_folds([row for row in selected_rows if row["match"].day < test_start])),
        "candidates": candidates,
    }
    test = {
        **_range(test_rows_selected), "season": season, "metrics": test_metrics,
        "used_for_selection": False,
        "training_end": max(row["match"].day for row in prior_history).isoformat(),
    }
    evaluation = {
        **test, "selected_model": selected["name"], "feature_set": selected["feature_set"],
        "window": selected["window"], "k": selected.get("k"), "validation": validation,
        "policy_models": {policy: spec["name"] for policy, spec in policy_specs.items()},
    }
    policy_predictions = {
        policy: predictions_by_spec[spec["name"]] for policy, spec in policy_specs.items()
    }
    return evaluation, selected, policy_predictions


_POLICY_NAMES = (
    ("selected_policy", "selection_policy", "Validation-selected model policy"),
    ("league_prior", "prior", "Historical league prior"),
    ("elo", "elo", "Elo baseline"),
    ("knn_policy", "knn", "Validation-selected kNN policy"),
    ("logistic_policy", "logistic", "Validation-selected logistic policy"),
)


def train_model(
    matches: list[Match], *, test_season: int | None = None, test_seasons: int = 1,
) -> ModelBundle:
    """Run one or multiple retrospective rolling-origin test seasons.

    Every origin tunes on its own earlier validation history. A later origin may
    learn from matches in earlier test years because those outcomes are known by
    then. Neither pooled nor individual test scores choose the production model:
    the latest origin's pre-test validation selection is refitted for production.
    """
    if type(test_seasons) is not int or test_seasons < 1:
        raise ValueError("test_seasons must be a positive integer")
    if test_season is not None and type(test_season) is not int:
        raise ValueError("test_season must be an ending-season integer")
    usable = validated_history(matches)
    if len(usable) < 250:
        raise ValueError("At least 250 valid completed matches across training and test periods are required")
    seasons = sorted({game.season for game in usable})
    now = datetime.now(HELSINKI)
    current_year = now.year + (now.month >= 7)
    if test_season is None:
        completed = [season for season in seasons if season < current_year]
        test_season = completed[-1] if completed else seasons[-1]
    if test_season not in seasons:
        raise ValueError("The requested held-out season has no usable results")
    if test_seasons > len(seasons):
        raise ValueError("The requested number of held-out seasons exceeds the available history")
    requested_seasons = list(range(test_season - test_seasons + 1, test_season + 1))
    missing = [season for season in requested_seasons if season not in seasons]
    if missing:
        raise ValueError(f"Requested held-out seasons have no usable results: {missing}")
    first_start = min(game.day for game in usable if game.season == requested_seasons[0])
    if sum(game.day < first_start for game in usable) < 150:
        raise ValueError("Insufficient completed matches before the earliest held-out season")
    # Shared across every retrospective origin: extracting a row never uses a
    # later label, even though the full historical dataset is present in memory.
    specs = _specs()
    rows_by_key: dict[tuple, list[dict]] = {}
    for spec in specs:
        key = spec["window"], spec["feature_set"]
        if key not in rows_by_key:
            rows_by_key[key] = build_feature_rows(usable, *key)
    evaluations, selections = [], []
    pooled_predictions: dict[str, tuple[list, list]] = {
        name: ([], []) for name, _, _ in _POLICY_NAMES
    }
    for season in requested_seasons:
        evaluation, selected, policy_predictions = _evaluate_origin(rows_by_key, specs, season)
        if test_seasons > 1:
            absent = set(pooled_predictions) - set(policy_predictions)
            if absent:
                raise ValueError(f"Insufficient earlier data to evaluate policies {sorted(absent)} for season {season}")
        evaluations.append(evaluation)
        selections.append(selected)
        for name, (labels, probabilities) in policy_predictions.items():
            pooled_predictions[name][0].extend(labels)
            pooled_predictions[name][1].extend(probabilities)
    latest, selected = evaluations[-1], selections[-1]
    selected_rows = rows_by_key[selected["window"], selected["feature_set"]]
    production = _fit(selected, selected_rows)
    digest_input = [(m.season, m.game_id, m.start.isoformat(), m.home_id, m.away_id,
                     m.home_goals, m.away_goals, m.home_regulation_goals, m.away_regulation_goals,
                     m.finish_type) for m in usable]
    digest = hashlib.sha256(json.dumps(digest_input, separators=(",", ":")).encode()).hexdigest()
    model_digest = hashlib.sha256(json.dumps({
        "dataset": digest, "spec": selected, "evaluation_test_seasons": requested_seasons,
    }, sort_keys=True).encode()).hexdigest()
    metadata = {
        "model_version": f"liiga-paper-v1-{model_digest[:12]}",
        "dataset_sha256": digest,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "training_cutoff": max(match.start for match in usable).isoformat(),
        "history_start": min(match.start for match in usable).isoformat(),
        "training_seasons": seasons,
        "usable_matches": len(usable),
        "excluded_matches": len(matches) - len(usable),
        "training_rows": production["training_rows"],
        "outcomes": list(OUTCOMES),
        "algorithm": selected["algorithm"], "selected_model": selected["name"],
        "feature_set": selected["feature_set"], "window": selected["window"],
        "k": selected.get("k"), "status": "experimental",
        "evaluation_test_seasons": requested_seasons,
        "evaluation_kind": "retrospective_rolling_origin",
        "evaluation_independent_blind": False,
        "production_selection_origin": latest["season"],
        "production_refit": "Latest origin's pre-test validation choice, refitted on all supplied usable known results; distinct from retrospective evaluation fits",
        "cutoff_policy": "Only results from strictly earlier Helsinki calendar dates; same-day results excluded",
        "rank_definition": "Recent points-per-game form table among clubs known in the season; midranks for statistical ties; not official standings",
        "cold_start_policy": "Fewer than six prior results for either club uses the historical league-prior distribution",
    }
    if test_seasons == 1:
        # Preserve the established single-season actual-configuration rows.
        test = {
            key: value for key, value in latest.items()
            if key not in ("selected_model", "feature_set", "window", "k", "validation", "policy_models")
        }
        test.update(
            seasons=requested_seasons, kind="retrospective_rolling_origin",
            independent_blind=False,
        )
    else:
        test_rows = [row for row in selected_rows if row["match"].season in requested_seasons]
        metrics = []
        for name, algorithm, display_name in _POLICY_NAMES:
            labels, probabilities = pooled_predictions[name]
            metrics.append({
                "name": name, "algorithm": algorithm, "display_name": display_name,
                **probability_metrics(labels, probabilities), "selected": name == "selected_policy",
            })
        test = {
            **_range(test_rows), "season": test_season, "seasons": requested_seasons,
            "kind": "retrospective_rolling_origin", "independent_blind": False,
            "used_for_selection": False,
            "training_end": latest["training_end"], "training_end_scope": "latest_origin_only",
            "initial_training_end": evaluations[0]["training_end"],
            "metrics": metrics, "per_season": evaluations,
        }
    report = {
        "selected_model": selected["name"],
        "selection_metric": "chronological validation four-outcome log loss",
        "production_selection_origin": latest["season"],
        "feature_set": selected["feature_set"], "window": selected["window"], "k": selected.get("k"),
        "validation": latest["validation"], "test": test,
        "limitations": [
            "Experimental probabilities; historical performance is not a guarantee of future accuracy.",
            "Evaluation is a retrospective rolling-origin backtest on historical data already examined during development, not an independent blind test.",
            "Each origin selects configuration only on earlier validation dates; aggregate test performance is not used to choose the production model.",
            "Current roster, injury and announced-goalie information are not inputs to this first model.",
            "History is carried across seasons; changing squads, schedule formats and new clubs affect reliability.",
            "Smoothing and calibration diagnostics are provided; no claim of perfect probability calibration is made.",
            "The production model is refitted on later known results after retrospective evaluation; its in-sample fit is not a new test score.",
        ],
    }
    return ModelBundle(production, metadata, report)
