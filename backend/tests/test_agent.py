"""Safety, retrieval, ranking and API smoke tests."""
from fastapi.testclient import TestClient
from app.agent import build_feed, create_story, haversine_km, verify_moment
from app.data import load_moments
from app.main import app
import pytest

client = TestClient(app)


def test_local_discovery():
    local = build_feed("Oulu", radius_km=25)
    assert local.total == 3
    assert all(m.city == "Oulu" for m in local.moments)
    assert local.moments == sorted(local.moments,
        key=lambda m: (-m.relevance_score, m.id))


def test_sport_filter():
    data = build_feed("Oulu", radius_km=25, sport="Football")
    assert data.total == 1
    assert data.moments[0].sport == "Football"


def test_distance():
    assert haversine_km(65.0121, 25.4651, 65.0121, 25.4651) == 0
    assert 150 < haversine_km(65.0121, 25.4651, 66.5039, 25.7294) < 180


def test_provenance_is_required():
    moment = load_moments()[0]
    moment.facts[0].source_id = "unrelated-source"
    with pytest.raises(ValueError, match="Evidence"):
        verify_moment(moment)


def test_unauthorized_video_is_blocked():
    moment = load_moments()[0]
    moment.video_url = "https://example.org/video.mp4"
    with pytest.raises(ValueError, match="authorization"):
        verify_moment(moment)


def test_grounded_story_offline(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = create_story("oulu-001")
    assert result.mode == "template"
    assert result.publication_status == "demo_only"
    assert "Aino Virtanen" in result.narration
    assert result.evidence


def test_api_endpoints():
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/feed", params={"city": "Oulu"}).status_code == 200
    assert client.get("/api/feed", params={"city": "Atlantis"}).status_code == 422
    assert client.post("/api/stories/missing").status_code == 404
