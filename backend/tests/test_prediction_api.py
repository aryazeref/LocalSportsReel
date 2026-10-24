"""Offline HTTP/service contracts for forecasts and regular-season scenarios."""

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.prediction import data, service
from app.prediction.domain import Match, OUTCOMES, REGULATION, Standing
from app.prediction.engine import ModelBundle
from app.prediction.schemas import OutcomeProbabilities

NOW = datetime(2026, 10, 24, 10, tzinfo=timezone.utc)


def game(game_id, start, *, home="1", away="2", season=2027, outcome=None):
    values = dict(season=season, game_id=game_id, start=datetime.fromisoformat(start),
                  home_id=home, away_id=away, home_name=f"Club {home}", away_name=f"Club {away}",
                  status="upcoming" if outcome is None else "finished")
    if outcome is not None:
        final, normal, finish = {
            0: ((3, 1), (3, 1), REGULATION),
            1: ((3, 2), (2, 2), "ENDED_DURING_WINNING_SHOT_COMPETITION"),
            2: ((2, 3), (2, 2), "ENDED_DURING_EXTENDED_GAME_TIME"),
            3: ((1, 3), (1, 3), REGULATION),
        }[outcome]
        values.update(home_goals=final[0], away_goals=final[1],
                      home_regulation_goals=normal[0], away_regulation_goals=normal[1], finish_type=finish)
    return Match(**values)


def completed_games():
    return [game(1, "2026-10-01T15:00:00+00:00", outcome=0),
            game(2, "2026-10-02T15:00:00+00:00", home="2", away="3", outcome=2)]


def upcoming_games():
    return [game(100, "2026-10-25T15:00:00+00:00"),
            game(101, "2026-10-26T15:00:00+00:00", home="3", away="1"),
            game(102, "2026-10-27T15:00:00+00:00", home="2", away="3")]


def official_standings():
    return [Standing("1", "Club 1", 3, 1, regulation_wins=1, goals_for=3, goals_against=1),
            Standing("3", "Club 3", 2, 1, overtime_wins=1, goals_for=3, goals_against=2),
            Standing("2", "Club 2", 1, 2, overtime_losses=1, regulation_losses=1, goals_for=3, goals_against=6)]


def snapshot(matches, source_hash="controlled-public-data"):
    return data.SeasonData(tuple(matches), NOW, source_hash, {"total_records": len(matches)})


class ControlledBundle:
    """Known predictions isolate service mapping from separately tested models."""
    def __init__(self):
        self.metadata = {
            "selected_model": "paper_knn_total_n12_k15", "algorithm": "knn", "model_version": "controlled-v1",
            "feature_set": "total", "window": 12, "training_cutoff": "2026-10-23T15:00:00+00:00",
            "usable_matches": 800, "created_at": NOW.isoformat(),
        }
        self.report = {"selected_model": self.metadata["selected_model"],
                       "validation": {"count": 100, "candidates": []},
                       "test": {"count": 80, "used_for_selection": False, "metrics": []}}
        self.calls = []

    def predict_many(self, history, fixtures, *, cutoff=None):
        self.calls.append((tuple(fixture.key for fixture in fixtures), cutoff))
        return [{"probabilities": [0.4, 0.2, 0.1, 0.3], "home_win": 0.6, "away_win": 0.4,
                 "features": [3, 2, 0.6, 2, 3, 0.4],
                 "feature_names": ["home_total_goals_for", "home_total_goals_against", "home_total_form_rank",
                                   "away_total_goals_for", "away_total_goals_against", "away_total_form_rank"],
                 "home_history": 10, "away_history": 12, "cold_start": False,
                 "history_cutoff": "2026-10-23"} for _ in fixtures]


@pytest.fixture(autouse=True)
def isolate_forecasts(monkeypatch, tmp_path):
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(service, "_prepare_lock", asyncio.Lock())
    monkeypatch.setattr(service, "_simulation_lock", asyncio.Semaphore(2))
    monkeypatch.setattr(service, "_cached_context", None)
    monkeypatch.setattr(service, "_forecast_cache", {})
    monkeypatch.setattr(service, "utc_now", lambda: NOW)
    monkeypatch.setattr(service, "current_season", lambda: 2027)
    async def reject_request(*args, **kwargs):
        pytest.fail("Prediction API tests must not contact an external provider")
    monkeypatch.setattr(data, "_request", reject_request)


@pytest.fixture
def controlled_context(monkeypatch):
    bundle = ControlledBundle()
    ctx = service.PredictionContext(2027, bundle, completed_games(), snapshot([*completed_games(), *upcoming_games()]), NOW)
    async def current_context(**kwargs):
        return ctx
    async def standings(season):
        assert season == 2027
        return data.StandingsData(tuple(official_standings()), NOW, [1, 2])
    monkeypatch.setattr(service, "context", current_context)
    monkeypatch.setattr(data, "load_standings", standings)
    return ctx


@pytest.fixture
def client():
    with TestClient(app) as instance:
        yield instance


def test_predictions_return_valid_probabilities_and_historical_evidence(client, controlled_context):
    response = client.get("/api/liiga/predictions?limit=2")
    assert response.status_code == 200
    result = response.json()
    assert result["season"] == 2027 and result["source"] == "Liiga Stats API v1"
    assert result["model"]["display_name"] == "Paper-inspired nearest neighbors"
    assert result["evaluation"]["test"]["used_for_selection"] is False
    assert [fixture["game_id"] for fixture in result["fixtures"]] == [100, 101]
    forecast = result["fixtures"][0]
    assert forecast["home_team"] == {"team_id": "1", "name": "Club 1"}
    p = forecast["probabilities"]
    assert sum(p[name] for name in OUTCOMES) == pytest.approx(1)
    assert p["home_win"] == pytest.approx(p["home_regulation"] + p["home_overtime"])
    assert p["away_win"] == pytest.approx(1 - p["home_win"])
    assert len(forecast["features"]["names"]) == len(forecast["features"]["values"]) == 6
    assert controlled_context.bundle.calls[0][1] == NOW


def test_team_filter_accepts_external_identity_before_display_limit(client, controlled_context):
    response = client.get("/api/liiga/predictions", params={"team_id": "3:club-three", "limit": 1})
    assert response.status_code == 200
    assert [fixture["game_id"] for fixture in response.json()["fixtures"]] == [101]
    assert controlled_context.bundle.calls[0][0] == ((2027, 101),)


def test_forecast_list_excludes_started_cancelled_unknown_and_past_fixtures(client, controlled_context):
    extra = [replace(upcoming_games()[0], game_id=200, status="live"),
             replace(upcoming_games()[0], game_id=201, status="cancelled"),
             replace(upcoming_games()[0], game_id=202, home_id=""),
             replace(upcoming_games()[0], game_id=203, away_id="1"),
             game(204, "2026-10-23T15:00:00+00:00")]
    controlled_context.current = snapshot([*controlled_context.current.matches, *extra])
    response = client.get("/api/liiga/predictions?limit=30")
    assert response.status_code == 200
    assert [fixture["game_id"] for fixture in response.json()["fixtures"]] == [100, 101, 102]


def test_no_upcoming_games_returns_empty_forecasts_not_invented_predictions(client, controlled_context):
    controlled_context.current = snapshot(completed_games())
    response = client.get("/api/liiga/predictions")
    assert response.status_code == 200 and response.json()["fixtures"] == []


@pytest.mark.parametrize("path", [
    "/api/liiga/predictions?limit=0", "/api/liiga/predictions?limit=31", "/api/liiga/predictions?team_id=",
    "/api/liiga/predictions/not-a-number/impact", "/api/liiga/predictions/100/impact?simulations=999",
    "/api/liiga/predictions/100/impact?simulations=10001", "/api/liiga/predictions/100/impact?top_n=0",
    "/api/liiga/predictions/100/impact?top_n=31",
])
def test_query_validation_rejects_bad_controls_before_preparation(client, path):
    assert client.get(path).status_code == 422


def test_impact_exposes_all_four_outcomes_and_bounds(client, controlled_context):
    response = client.get("/api/liiga/predictions/100/impact?top_n=2&simulations=1000")
    assert response.status_code == 200
    result = response.json()
    assert result["scope"] == "regular_season_points" and result["remaining_fixtures"] == 3
    assert result["simulations"] == 1000 and result["top_n"] == 2
    assert len(result["baseline"]) == 3
    assert [(row["outcome"], row["home_points"], row["away_points"]) for row in result["scenarios"]] == [
        ("home_regulation", 3, 0), ("home_overtime", 2, 1), ("away_overtime", 1, 2), ("away_regulation", 0, 3)]
    assert all(0 <= row["top_n_lower"] <= row["top_n_upper"] <= 1 for row in result["baseline"])
    assert sum(row["expected_points"] for row in result["baseline"]) == pytest.approx(15)
    for scenario in result["scenarios"]:
        assert sum(row["expected_points"] for row in scenario["teams"]) == pytest.approx(15)
        assert sum(row["delta_points"] for row in scenario["teams"]) == pytest.approx(0)
    assert any("tie-breakers" in warning for warning in result["warnings"])
    assert not any("championship_probability" in row for row in result["baseline"])


def test_unknown_or_completed_selected_match_is_404(client, controlled_context):
    assert client.get("/api/liiga/predictions/999/impact?top_n=2").status_code == 404
    assert client.get("/api/liiga/predictions/1/impact?top_n=2").status_code == 404


@pytest.mark.parametrize("kind", ["live", "past", "unknown_team", "duplicate_team"])
def test_unresolved_schedule_pauses_scenarios_but_not_forecasts(client, controlled_context, kind):
    extra = replace(upcoming_games()[0], game_id=200)
    if kind == "live":
        extra = replace(extra, status="live")
    elif kind == "past":
        extra = replace(extra, start=datetime(2026, 10, 23, 15, tzinfo=timezone.utc))
    elif kind == "unknown_team":
        extra = replace(extra, home_id="")
    else:
        extra = replace(extra, away_id=extra.home_id)
    controlled_context.current = snapshot([*controlled_context.current.matches, extra])
    blocked = client.get("/api/liiga/predictions/100/impact?top_n=2")
    assert blocked.status_code == 409 and "paused" in blocked.json()["detail"]
    assert client.get("/api/liiga/predictions").status_code == 200


def test_mismatched_official_table_is_not_simulated(client, controlled_context, monkeypatch):
    async def altered_standings(season):
        rows = official_standings()
        rows[0] = replace(rows[0], points=4)
        return data.StandingsData(tuple(rows), NOW, [])
    monkeypatch.setattr(data, "load_standings", altered_standings)
    response = client.get("/api/liiga/predictions/100/impact?top_n=2")
    assert response.status_code == 409 and "do not yet agree" in response.json()["detail"]
    assert controlled_context.bundle.calls == []


def test_unusable_finished_result_blocks_points_scenarios(client, controlled_context):
    bad = replace(completed_games()[0], home_regulation_goals=None)
    controlled_context.current = snapshot([bad, *controlled_context.current.matches[1:]])
    response = client.get("/api/liiga/predictions/100/impact?top_n=2")
    assert response.status_code == 409 and "incomplete result data" in response.json()["detail"]


def test_top_n_cannot_exceed_actual_league_size(client, controlled_context):
    response = client.get("/api/liiga/predictions/100/impact?top_n=4")
    assert response.status_code == 422 and "number of teams" in response.json()["detail"]


def test_standings_provider_failure_does_not_invent_scenario(client, controlled_context, monkeypatch):
    async def unavailable(season):
        raise data.PredictionDataError("Official standings are temporarily unavailable.")
    monkeypatch.setattr(data, "load_standings", unavailable)
    response = client.get("/api/liiga/predictions/100/impact?top_n=2")
    assert response.status_code == 502 and "temporarily unavailable" in response.json()["detail"]
    assert client.get("/api/liiga/predictions").status_code == 200


def test_model_time_guard_returns_readiness_error_instead_of_forecast(client, controlled_context, monkeypatch):
    def reject_historical(*args, **kwargs):
        raise ValueError("artifact contains later training outcomes")
    monkeypatch.setattr(controlled_context.bundle, "predict_many", reject_historical)
    response = client.get("/api/liiga/predictions")
    assert response.status_code == 503 and "historical cutoff" in response.json()["detail"]


@pytest.mark.parametrize("change", [{"home_win": 0.7}, {"home_regulation": 0.5},
                                     {"away_overtime": float("nan")}, {"away_win": 1.1}])
def test_response_schema_rejects_inconsistent_or_nonfinite_probabilities(change):
    values = dict(home_regulation=0.4, home_overtime=0.2, away_overtime=0.1,
                  away_regulation=0.3, home_win=0.6, away_win=0.4)
    with pytest.raises(ValidationError):
        OutcomeProbabilities(**{**values, **change})


def prior_bundle(history):
    return ModelBundle(
        {"spec": {"name": "league_prior", "algorithm": "prior", "window": 12, "feature_set": "total"},
         "prior": [0.4, 0.1, 0.1, 0.4], "training_rows": len(history)},
        {"outcomes": list(OUTCOMES), "selected_model": "league_prior", "algorithm": "prior",
         "model_version": "offline-prior", "feature_set": "total", "window": 12,
         "training_cutoff": max(match.start for match in history).isoformat(),
         "usable_matches": len(history), "created_at": NOW.isoformat()},
        {"selected_model": "league_prior", "test": {"used_for_selection": False, "metrics": []}})


@pytest.fixture
def preparation_sources(monkeypatch):
    monkeypatch.setattr(service, "HISTORY_SEASONS", 2)
    records = {
        2026: snapshot([game(1, "2025-10-01T15:00:00+00:00", season=2026, outcome=0)], "old-season"),
        2027: snapshot([*completed_games(), *upcoming_games(),
                        game(3, "2026-10-24T08:00:00+00:00", outcome=3)], "current-season")}
    calls, fits = [], []
    async def source(season, *, refresh=False):
        calls.append((season, refresh))
        return records[season]
    def fit(history, test_season):
        fits.append((tuple(history), test_season))
        return prior_bundle(history)
    monkeypatch.setattr(data, "load_season", source)
    monkeypatch.setattr(service, "_train", fit)
    return records, calls, fits


def test_preparation_excludes_same_day_and_reuses_json_artifact(preparation_sources, monkeypatch):
    _, calls, fits = preparation_sources
    first = asyncio.run(service.context())
    assert len(fits) == 1 and fits[0][1] == 2026
    assert all(match.day < NOW.date() for match in fits[0][0])
    assert len(fits[0][0]) == 3
    artifact = data.CACHE_DIR / "model-v1.json"
    assert artifact.exists() and (data.CACHE_DIR / "evaluation.json").exists()
    saved = json.loads(artifact.read_text())
    assert len(saved["metadata"]["dataset_manifest"]) == 2
    assert saved["metadata"]["service_fingerprint"]
    cached = asyncio.run(service.context())
    assert cached.bundle is first.bundle and len(fits) == 1
    monkeypatch.setattr(service, "_cached_context", None)
    restored = asyncio.run(service.context())
    assert isinstance(restored.bundle, ModelBundle)
    assert restored.bundle.metadata == first.bundle.metadata and len(fits) == 1
    assert all(path.suffix != ".pkl" for path in data.CACHE_DIR.iterdir())


def test_changed_result_invalidates_model_fingerprint(preparation_sources):
    records, _, fits = preparation_sources
    asyncio.run(service.context())
    corrected = game(1, "2026-10-01T15:00:00+00:00", outcome=3)
    records[2027] = snapshot([corrected, *records[2027].matches[1:]], "corrected-current")
    updated = asyncio.run(service.context())
    assert len(fits) == 2 and updated.history[1].outcome == 3


def test_new_day_includes_previously_excluded_results(preparation_sources, monkeypatch):
    _, _, fits = preparation_sources
    asyncio.run(service.context())
    monkeypatch.setattr(service, "utc_now", lambda: datetime(2026, 10, 25, 10, tzinfo=timezone.utc))
    updated = asyncio.run(service.context())
    assert len(fits) == 2
    assert any(match.game_id == 3 and match.season == 2027 for match in updated.history)


@pytest.mark.parametrize("contents", ["not JSON", '{"artifact_version": 0}'])
def test_broken_artifact_is_rebuilt_from_valid_data(preparation_sources, contents):
    _, _, fits = preparation_sources
    (data.CACHE_DIR / "model-v1.json").write_text(contents)
    result = asyncio.run(service.context())
    assert len(fits) == 1 and result.bundle.metadata["service_fingerprint"]
    assert json.loads((data.CACHE_DIR / "model-v1.json").read_text())["artifact_version"] == 1


def test_provider_failure_is_not_hidden_by_old_context(client, preparation_sources, monkeypatch):
    asyncio.run(service.context())
    async def failure(season, *, refresh=False):
        raise data.PredictionDataError("Cannot load current public match data.")
    monkeypatch.setattr(data, "load_season", failure)
    response = client.get("/api/liiga/predictions")
    assert response.status_code == 502 and "current public match data" in response.json()["detail"]
    assert "fixtures" not in response.json()


def test_insufficient_history_is_reported_and_not_saved(client, preparation_sources, monkeypatch):
    def insufficient(*args, **kwargs):
        raise ValueError("At least 250 completed matches are required")
    monkeypatch.setattr(service, "_train", insufficient)
    response = client.get("/api/liiga/predictions")
    assert response.status_code == 503 and "more usable history" in response.json()["detail"]
    assert not (data.CACHE_DIR / "model-v1.json").exists()


def test_fixture_starting_during_preparation_is_not_returned(client, preparation_sources, monkeypatch):
    from datetime import timedelta
    records, _, _ = preparation_sources
    soon = replace(upcoming_games()[0], start=NOW + timedelta(seconds=1))
    records[2027] = snapshot([*completed_games(), soon, *upcoming_games()[1:]])
    clock = [NOW]
    monkeypatch.setattr(service, "utc_now", lambda: clock[0])
    original_fit = service._train
    def slow_preparation(history, test_season):
        result = original_fit(history, test_season)
        clock[0] = NOW + timedelta(seconds=2)
        return result
    monkeypatch.setattr(service, "_train", slow_preparation)
    response = client.get("/api/liiga/predictions")
    assert response.status_code == 200
    assert 100 not in [fixture["game_id"] for fixture in response.json()["fixtures"]]
    assert datetime.fromisoformat(response.json()["generated_at"].replace("Z", "+00:00")) == clock[0]


def test_cached_model_still_excludes_newly_started_fixture(client, preparation_sources, monkeypatch):
    from datetime import timedelta
    records, _, fits = preparation_sources
    soon = replace(upcoming_games()[0], start=NOW + timedelta(seconds=1))
    records[2027] = snapshot([*completed_games(), soon, *upcoming_games()[1:]])
    first = client.get("/api/liiga/predictions")
    assert first.status_code == 200
    assert 100 in [fixture["game_id"] for fixture in first.json()["fixtures"]]
    monkeypatch.setattr(service, "utc_now", lambda: NOW + timedelta(seconds=2))
    second = client.get("/api/liiga/predictions")
    assert second.status_code == 200
    assert 100 not in [fixture["game_id"] for fixture in second.json()["fixtures"]]
    assert len(fits) == 1


def test_concurrent_forecast_requests_keep_their_own_results(controlled_context, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading

    barrier = threading.Barrier(4, timeout=10)
    def synchronized_predictions(history, fixtures, *, cutoff=None):
        result = [{"fixture_key": fixture.key} for fixture in fixtures]
        barrier.wait()
        return result
    monkeypatch.setattr(controlled_context.bundle, "predict_many", synchronized_predictions)
    fixtures = [replace(upcoming_games()[0], game_id=1000 + index) for index in range(40)]
    def forecast(fixture):
        rows = service._forecast_rows(controlled_context, [fixture])
        return fixture.key, rows
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(forecast, fixtures))
    assert all(rows == [{"fixture_key": key}] for key, rows in results)


@pytest.mark.parametrize("model_version,expected_status", [("controlled-v1", 200), ("stale-v0", 409)])
def test_scenario_matches_the_displayed_forecast_version(client, controlled_context, model_version, expected_status):
    response = client.get("/api/liiga/predictions/100/impact", params={
        "top_n": 2, "simulations": 1000, "model_version": model_version,
    })
    assert response.status_code == expected_status
    if expected_status == 200:
        assert response.json()["model_version"] == "controlled-v1"
        assert response.json()["forecast_cutoff"] == "2026-10-24"
    else:
        assert "Refresh forecasts" in response.json()["detail"]
        assert controlled_context.bundle.calls == []


def test_incompatible_pipeline_artifact_is_retrained(preparation_sources, monkeypatch):
    _, _, fits = preparation_sources
    asyncio.run(service.context())
    artifact = data.CACHE_DIR / "model-v1.json"
    saved = json.loads(artifact.read_text())
    saved["metadata"]["pipeline_version"] = -1
    artifact.write_text(json.dumps(saved))
    monkeypatch.setattr(service, "_cached_context", None)
    restored = asyncio.run(service.context())
    assert len(fits) == 2
    assert restored.bundle.metadata["pipeline_version"] == service.PIPELINE_VERSION


def test_remaining_team_missing_from_standings_blocks_incomplete_simulation(client, controlled_context):
    foreign_team = replace(upcoming_games()[0], game_id=200, home_id="99")
    controlled_context.current = snapshot([*controlled_context.current.matches, foreign_team])
    response = client.get("/api/liiga/predictions/100/impact?top_n=2")
    assert response.status_code == 409
    assert "fixture teams must exist" in response.json()["detail"]
