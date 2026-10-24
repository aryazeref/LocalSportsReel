"""Homepage discovery must use REAL normalized Liiga games, not demo moments.

Use fixed fixtures and the same FastAPI route that the Next.js homepage calls.
No external HTTP request or LLM is required.
"""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.models import LiigaGame, LiigaTeam
from app.services.liiga_client import SeasonGames


def game(id, status, day, city=None, home_goals=None, away_goals=None):
    return LiigaGame(
        id=id, season=2027,
        start=datetime.fromisoformat(f"2026-10-{day:02}T18:00:00+03:00"),
        status=status, city=city, venue=f"Rink {id}",
        home_team=LiigaTeam(name="Kärpät", team_id="101", goals=home_goals),
        away_team=LiigaTeam(name="JYP", team_id="102", goals=away_goals),
    )


def test_discovery_returns_real_recent_and_upcoming_and_city_filter(monkeypatch):
    fixture = SeasonGames((
        game(1, "finished", 10, city="Oulu", home_goals=3, away_goals=2),
        game(2, "finished", 15, city="Tampere", home_goals=5, away_goals=1),
        game(3, "finished", 20, city="Oulu", home_goals=2, away_goals=1),
        game(4, "upcoming", 25, city="Oulu"),
        game(5, "live", 24, city="Tampere", home_goals=1, away_goals=0),
        game(6, "cancelled", 24, city="Oulu"),
        game(7, "upcoming", 26, city=None),
    ), datetime(2026, 10, 24, 19, tzinfo=timezone.utc))

    async def fake_dataset(season):
        assert season == 2027
        return fixture
    monkeypatch.setattr("app.liiga_api._dataset", fake_dataset)
    client = TestClient(app)
    response = client.get("/api/liiga/discover?season=2027")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data_mode"] == "real"
    assert payload["source"] == "Liiga Stats API v1"
    assert payload["cities"] == ["Oulu", "Tampere"]
    assert [row["id"] for row in payload["recent"]] == [3, 2, 1]
    assert [row["id"] for row in payload["live"]] == [5]
    assert [row["id"] for row in payload["upcoming"]] == [4, 7]
    assert payload["recent"][0]["home_team"]["goals"] == 2
    assert payload["recent"][0]["away_team"]["goals"] == 1
    # The city filter is the MATCH VENUE, not the fan's approximate location.
    filtered = client.get("/api/liiga/discover?season=2027&city=oulu")
    assert filtered.status_code == 200
    assert filtered.json()["selected_city"] == "Oulu"
    assert [row["id"] for row in filtered.json()["recent"]] == [3, 1]
    assert [row["id"] for row in filtered.json()["upcoming"]] == [4]
    assert filtered.json()["live"] == []


def test_discovery_rejects_unknown_city(monkeypatch):
    async def fake_dataset(season):
        return SeasonGames((
            game(8, "upcoming", 25, city="Oulu"),
        ), datetime(2026, 10, 24, 19, tzinfo=timezone.utc))
    monkeypatch.setattr("app.liiga_api._dataset", fake_dataset)
    result = TestClient(app).get("/api/liiga/discover?city=Atlantis&season=2027")
    assert result.status_code == 422


def test_discovery_caps_each_group_separately(monkeypatch):
    data = SeasonGames(tuple([
        game(i, "finished", i, city="Oulu", home_goals=2, away_goals=1)
        for i in range(1, 13)
    ] + [
        game(100 + i, "upcoming", i, city="Oulu")
        for i in range(1, 12)
    ]), datetime(2026, 10, 24, 19, tzinfo=timezone.utc))
    async def fake_dataset(season):
        return data
    monkeypatch.setattr("app.liiga_api._dataset", fake_dataset)
    payload = TestClient(app).get("/api/liiga/discover?season=2027").json()
    assert len(payload["recent"]) == 6
    assert [row["id"] for row in payload["recent"]] == [12, 11, 10, 9, 8, 7]
    assert len(payload["upcoming"]) == 9
