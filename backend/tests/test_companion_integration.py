"""Regression checks for combining the teammate's Python logic with FastAPI.

No network, API key or Streamlit process is required.
"""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.models import LiigaGame, LiigaTeam
from app.services.liiga_client import SeasonGames
from app.services.companion_bridge import build_companion_snapshot, companion_response
from app.prediction.schemas import ForecastFixture


def example_data():
    games = (
        LiigaGame(
            id=701, season=2027, start=datetime(2026, 10, 14, 16, tzinfo=timezone.utc),
            status="finished", home_team=LiigaTeam(name="Kärpät", team_id="91:kärpät", goals=3),
            away_team=LiigaTeam(name="Tappara", team_id="92:tappara", goals=1),
            finished_type="ENDED_DURING_REGULAR_GAME_TIME",
            venue="Oulun Energia Areena", city="Oulu",
        ),
        LiigaGame(
            id=702, season=2027, start=datetime(2026, 11, 14, 16, tzinfo=timezone.utc),
            status="upcoming", home_team=LiigaTeam(name="Tappara", team_id="92:tappara"),
            away_team=LiigaTeam(name="Kärpät", team_id="91:kärpät"),
        ),
    )
    return SeasonGames(games, datetime(2026, 10, 24, 10, tzinfo=timezone.utc))


def example_forecast():
    return ForecastFixture.model_validate({
        "game_id": 702, "season": 2027,
        "start": "2026-11-14T16:00:00+00:00",
        "home_team": {"team_id": "92", "name": "Tappara"},
        "away_team": {"team_id": "91", "name": "Kärpät"},
        "probabilities": {
            "home_regulation": 0.4, "home_overtime": 0.1,
            "away_overtime": 0.1, "away_regulation": 0.4,
            "home_win": 0.5, "away_win": 0.5,
        },
        "features": {
            "names": [], "values": [], "home_history": 1,
            "away_history": 1, "cold_start": False, "history_cutoff": "2026-10-24",
        },
        "warnings": [],
    })


def test_shared_snapshot_keeps_provider_ids_and_result_type():
    snapshot = build_companion_snapshot(example_data())
    assert snapshot.is_mock is False
    assert set(snapshot.teams) == {"91:kärpät", "92:tappara"}
    assert snapshot.games[0]["status"] == "final"
    assert snapshot.games[0]["decided"] == "REG"
    assert snapshot.games[1]["status"] == "scheduled"


def test_fan_companion_reuses_facts_without_running_own_simulator(monkeypatch):
    from companion import scenarios

    def forbidden(*args, **kwargs):
        raise AssertionError("Do not call teammate's standalone prediction simulator")

    monkeypatch.setattr(scenarios, "simulate", forbidden)
    snapshot = build_companion_snapshot(example_data())
    reply = companion_response(
        snapshot, team_id="91:kärpät", message="What are our chances of winning?",
        history=[], kind="chat", persona="buddy", language="English",
        use_ai=False, forecast=example_forecast(), forecast_model="Existing tested model",
    )
    assert reply["forecast"]["away_win"] == 0.5
    assert reply["verification_status"] in ("verified", "corrected", "redacted")
    assert "50.0%" in reply["text"]
    assert reply["numbers_checked"] >= 2
    assert any(item["source"].startswith("LocalSportsReel evaluated prediction engine")
               for item in reply["receipts"])
    assert reply["is_mock"] is False


def test_companion_teams_are_exposed_through_existing_api(monkeypatch):
    async def fake_dataset(season):
        assert season == 2027
        return example_data()

    monkeypatch.setattr("app.companion_api._dataset", fake_dataset)
    client = TestClient(app)
    result = client.get("/api/companion/teams?season=2027")
    assert result.status_code == 200
    value = result.json()
    assert value["data_mode"] == "real"
    assert {item["id"] for item in value["teams"]} == {"91:kärpät", "92:tappara"}


def test_companion_rejects_invalid_chat_and_unknown_team(monkeypatch):
    async def fake_dataset(season):
        return example_data()

    monkeypatch.setattr("app.companion_api._dataset", fake_dataset)
    client = TestClient(app)
    invalid = client.post("/api/companion/respond", json={
        "season": 2027, "team_id": "91:kärpät", "message": "  ",
    })
    assert invalid.status_code == 422
    missing = client.post("/api/companion/respond", json={
        "season": 2027, "team_id": "made-up", "message": "Hello",
    })
    assert missing.status_code == 404
