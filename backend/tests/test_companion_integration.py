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
        # Companion facts refer to the top-four race. Use at least five teams
        # to make the offline fixture representative of a real Liiga table.
        LiigaGame(
            id=703, season=2027, start=datetime(2026, 12, 1, 16, tzinfo=timezone.utc),
            status="upcoming", home_team=LiigaTeam(name="Ilves", team_id="93:ilves"),
            away_team=LiigaTeam(name="Jukurit", team_id="94:jukurit"),
        ),
        LiigaGame(
            id=704, season=2027, start=datetime(2026, 12, 2, 16, tzinfo=timezone.utc),
            status="upcoming", home_team=LiigaTeam(name="JYP", team_id="95:jyp"),
            away_team=LiigaTeam(name="Ilves", team_id="93:ilves"),
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
    assert set(snapshot.teams) == {"91:kärpät", "92:tappara", "93:ilves", "94:jukurit", "95:jyp"}
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
    assert len(value["teams"]) == 5
    assert {item["id"] for item in value["teams"]} >= {"91:kärpät", "92:tappara"}


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


def test_ai_status_explicitly_reports_offline_without_disclosing_keys(monkeypatch):
    from app.services.companion_ai import companion_ai_status
    monkeypatch.setenv("COMPANION_ENABLE_LLM", "false")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "top-secret-for-local-test")
    response = TestClient(app).get("/api/companion/status")
    assert response.status_code == 200
    assert response.json()["available"] is False
    assert "top-secret" not in response.text

    monkeypatch.setenv("COMPANION_ENABLE_LLM", "true")
    assert companion_ai_status()["available"] is True
    assert companion_ai_status()["provider"] == "OpenAI"
    assert "top-secret" not in str(companion_ai_status())


def test_ai_status_respects_explicit_provider_not_other_keys(monkeypatch):
    from app.services.companion_ai import companion_ai_status
    monkeypatch.setenv("COMPANION_ENABLE_LLM", "true")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "exists-but-wrong-provider")
    assert companion_ai_status()["available"] is False
    assert companion_ai_status()["provider"] == "Gemini"


def test_mode_indicates_actual_ai_generation_or_offline_fallback(monkeypatch):
    import app.services.companion_bridge as bridge

    class FakeAI:
        name = "Mock OpenAI provider"
        def generate(self, system, messages, max_tokens=700):
            return "Hi! Happy to talk about your team."

    snapshot = build_companion_snapshot(example_data())
    monkeypatch.setattr(bridge, "configured_backend", lambda: (FakeAI(), None))
    ai_reply = companion_response(
        snapshot, team_id="91:kärpät", message="test",
        history=[], kind="chat", persona="buddy", language="English", use_ai=True,
    )
    assert ai_reply["generation_mode"] == "ai"
    assert ai_reply["engine"] == "Mock OpenAI provider"
    assert "Happy to talk" in ai_reply["text"]

    class BrokenAI:
        name = "Unavailable mock provider"
        def generate(self, system, messages, max_tokens=700):
            raise RuntimeError("model server is unavailable")

    monkeypatch.setattr(bridge, "configured_backend", lambda: (BrokenAI(), None))
    offline = companion_response(
        snapshot, team_id="91:kärpät", message="test",
        history=[], kind="chat", persona="buddy", language="English", use_ai=True,
    )
    assert offline["generation_mode"] == "fallback"
    assert offline["engine"].startswith("Offline templates")
    assert offline["mode_message"].startswith("The AI service could not")
    assert "model server is unavailable" not in offline["mode_message"]


def test_companion_includes_named_rival_with_verified_receipts(monkeypatch):
    """Team names activate teammate find_teams/add_team_facts, not invented comparisons."""
    async def fake_dataset(season):
        return example_data()
    monkeypatch.setattr("app.companion_api._dataset", fake_dataset)
    response = TestClient(app).post("/api/companion/respond", json={
        "season": 2027, "team_id": "91:kärpät",
        "message": "How do we compare to Tappara?",
        "persona": "analyst", "use_ai": False,
    })
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["verification_status"] == "verified"
    assert "Tappara" in value["text"]
    assert any("Tappara" in item["label"] for item in value["receipts"])
    # Comparison follow-ups intentionally move to the next topic rather than
    # asking the same comparison question again.
    assert len(value["suggestions"]) >= 3
    assert all(item["label"] and item["question"] for item in value["suggestions"])


def test_companion_route_saves_alert_preference_without_scheduling(monkeypatch):
    async def fake_dataset(season):
        return example_data()
    monkeypatch.setattr("app.companion_api._dataset", fake_dataset)
    response = TestClient(app).post("/api/companion/respond", json={
        "season": 2027, "team_id": "91:kärpät",
        "message": "Set an alert if our chances fall below 15%",
        "use_ai": False,
    })
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["action"] == {
        "tool": "set_alert", "team_id": "91:kärpät", "season": 2027,
        "threshold": 15, "game_id": None, "home_team": None, "away_team": None,
        "home_goals": None, "away_goals": None,
    }
    assert value["generation_mode"] == "offline"
    assert value["verification_status"] == "verified"
    assert "not send notifications" in value["text"]
    assert "no background alerts" in value["mode_message"].lower()


def test_companion_route_saves_score_guess_for_next_fixture(monkeypatch):
    async def fake_dataset(season):
        return example_data()
    monkeypatch.setattr("app.companion_api._dataset", fake_dataset)
    response = TestClient(app).post("/api/companion/respond", json={
        "season": 2027, "team_id": "91:kärpät",
        "message": "My prediction is 3-2",
    })
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["action"]["tool"] == "save_prediction"
    assert value["action"]["game_id"] == "702"
    assert (value["action"]["home_goals"], value["action"]["away_goals"]) == (3, 2)
    assert (value["action"]["home_team"], value["action"]["away_team"]) == ("Tappara", "Kärpät")
    assert "not be published" in value["text"]


def test_companion_profile_name_and_length_reach_model(monkeypatch):
    import app.services.companion_bridge as bridge
    captured = {}

    class StubModel:
        name = "Mock Gemini"

        def generate(self, system, messages, max_tokens=700):
            captured["system"] = system
            return "Your club has plenty to discuss."

    async def fake_dataset(season):
        return example_data()
    monkeypatch.setattr("app.companion_api._dataset", fake_dataset)
    monkeypatch.setattr(bridge, "configured_backend", lambda: (StubModel(), None))
    reply = TestClient(app).post("/api/companion/respond", json={
        "season": 2027, "team_id": "91:kärpät", "message": "Hello",
        "user_name": "Taylor", "answer_length": "short",
        "use_ai": True,
    })
    assert reply.status_code == 200, reply.text
    assert reply.json()["generation_mode"] == "ai"
    assert "Taylor" in captured["system"]
    assert "Length: 2–3 sentences" in captured["system"]


def test_companion_overview_and_initial_suggestions_use_real_facts(monkeypatch):
    async def fake_dataset(season):
        return example_data()
    monkeypatch.setattr("app.companion_api._dataset", fake_dataset)
    client = TestClient(app)
    overview = client.get("/api/companion/overview?season=2027&team_id=91:kärpät")
    assert overview.status_code == 200, overview.text
    payload = overview.json()
    assert payload["points"].isdigit()
    assert payload["next_game"] is not None
    assert payload["name"] == "Kärpät"
    teams = client.get("/api/companion/teams?season=2027")
    assert teams.status_code == 200
    assert len(teams.json()["suggestions"]) >= 3


def test_alert_rejects_unusable_percent(monkeypatch):
    async def fake_dataset(season):
        return example_data()
    monkeypatch.setattr("app.companion_api._dataset", fake_dataset)
    value = TestClient(app).post("/api/companion/respond", json={
        "season": 2027, "team_id": "91:kärpät",
        "message": "Alert me if below 300%",
    })
    assert value.status_code == 422
