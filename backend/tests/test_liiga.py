"""Liiga adapter, historical calculations, and HTTP contract regressions.

All provider responses here are controlled fixtures; no network is needed.
Run from backend with `.venv/bin/python -m pytest -q`.
"""

import asyncio
import time
from copy import deepcopy
from urllib.parse import quote

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import liiga_client
from app.services.liiga_analysis import calculate_team_stats
from app.services.liiga_client import normalize_game


REAL_ASYNC_CLIENT = httpx.AsyncClient
TEAM_A = "100:alpha"
TEAM_B = "200:beta"


def raw_game(game_id=1, *, home=TEAM_A, away=TEAM_B, home_goals=3,
             away_goals=1, start="2026-09-01T15:30:00Z", ended=True):
    return {
        "id": game_id,
        "season": 2027,
        "serie": "RUNKOSARJA",
        "start": start,
        "started": ended,
        "ended": ended,
        "finishedType": "ENDED_DURING_REGULAR_GAME_TIME" if ended else "ACTIVE_OR_NOT_STARTED",
        "homeTeam": {"teamId": home, "teamName": home, "goals": home_goals},
        "awayTeam": {"teamId": away, "teamName": away, "goals": away_goals},
    }


@pytest.fixture(autouse=True)
def isolate_provider(monkeypatch):
    """No cache/async-loop state or accidental external requests cross tests."""
    liiga_client._cache.clear()
    monkeypatch.setattr(liiga_client, "_fetch_lock", asyncio.Lock())

    def reject_network(request):
        raise AssertionError(f"Unexpected provider request: {request.url.path}")

    monkeypatch.setattr(
        liiga_client.httpx, "AsyncClient",
        lambda **kwargs: REAL_ASYNC_CLIENT(
            transport=httpx.MockTransport(reject_network), **kwargs,
        ),
    )
    yield
    liiga_client._cache.clear()


@pytest.fixture
def upstream(monkeypatch):
    def configure(payload=None, *, status=200, handler=None):
        calls = []

        def respond(request):
            calls.append(request)
            if handler is not None:
                return handler(request)
            return httpx.Response(status, json=payload)

        monkeypatch.setattr(
            liiga_client.httpx, "AsyncClient",
            lambda **kwargs: REAL_ASYNC_CLIENT(
                transport=httpx.MockTransport(respond), **kwargs,
            ),
        )
        return calls

    return configure


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_statistics_count_final_scores_for_both_sides_and_ignore_unfinished():
    home_win = raw_game(1, home_goals=3, away_goals=1)
    away_win = raw_game(2, home=TEAM_B, away=TEAM_A, home_goals=2,
                        away_goals=4, start="2026-09-02T15:30:00Z")
    loss = raw_game(3, home_goals=1, away_goals=2, start="2026-09-03T15:30:00Z")
    overtime = raw_game(4, home_goals=2, away_goals=3, start="2026-09-04T15:30:00Z")
    overtime["finishedType"] = "ENDED_DURING_EXTENDED_GAME_TIME"
    shootout = raw_game(5, home_goals=3, away_goals=2, start="2026-09-05T15:30:00Z")
    shootout["finishedType"] = "ENDED_DURING_WINNING_SHOT_COMPETITION"
    upcoming = raw_game(6, ended=False, home_goals=99, away_goals=0)
    live = raw_game(7, ended=False, home_goals=99, away_goals=0)
    live["started"] = True

    teams, completed, excluded = calculate_team_stats(
        normalize_game(raw) for raw in [upcoming, away_win, live, loss, home_win, overtime, shootout]
    )
    stats = {team.team_id: team for team in teams}
    alpha, beta = stats[TEAM_A], stats[TEAM_B]
    assert completed == 5 and excluded == 0
    assert (alpha.matches_played, alpha.wins, alpha.losses) == (5, 3, 2)
    assert (alpha.goals_for, alpha.goals_against, alpha.goal_difference) == (13, 10, 3)
    assert alpha.win_percentage == 60.0
    assert (beta.wins, beta.losses, beta.goals_for, beta.goals_against) == (2, 3, 10, 13)
    assert beta.goal_difference == -3
    assert alpha.form == ["W", "L", "L", "W", "W"]


@pytest.mark.parametrize("invalid_score", [None, -1, True, "3", 2.5])
def test_unusable_score_excludes_whole_result(invalid_score):
    game = raw_game(home_goals=invalid_score)
    teams, completed, excluded = calculate_team_stats([normalize_game(game)])
    assert completed == 0 and excluded == 1
    assert all(team.matches_played == 0 and team.goals_for == 0 for team in teams)
    assert all(team.win_percentage is None and team.form == [] for team in teams)


@pytest.mark.parametrize("home_id,away_id", [(None, TEAM_B), ("", TEAM_B), (TEAM_A, TEAM_A)])
def test_missing_or_identical_team_ids_exclude_result(home_id, away_id):
    _, completed, excluded = calculate_team_stats([
        normalize_game(raw_game(home=home_id, away=away_id)),
    ])
    assert completed == 0 and excluded == 1


def test_cancelled_matches_do_not_become_draws_or_count_as_played():
    cancelled = raw_game(home_goals=0, away_goals=0)
    cancelled["finishedType"] = "CANCELLED"
    game = normalize_game(cancelled)
    assert game.status == "cancelled"
    teams, completed, excluded = calculate_team_stats([game])
    assert completed == excluded == 0
    assert all(team.matches_played == 0 and team.draws == 0 for team in teams)


def test_form_uses_only_newest_five_results_from_unsorted_input():
    games = [
        normalize_game(raw_game(
            day, home_goals=3 if day % 2 else 1, away_goals=2,
            start=f"2026-09-{day:02d}T15:30:00Z",
        ))
        for day in [4, 1, 7, 3, 6, 2, 5]
    ]
    teams, _, _ = calculate_team_stats(games)
    alpha = next(team for team in teams if team.team_id == TEAM_A)
    assert alpha.matches_played == 7
    assert alpha.form == ["W", "L", "W", "L", "W"]
    assert alpha.win_percentage == 57.1


def test_draws_and_zero_match_teams_have_explicit_statistics():
    tied = normalize_game(raw_game(home_goals=2, away_goals=2))
    future = normalize_game(raw_game(2, home="300:future", ended=False))
    teams, completed, _ = calculate_team_stats([tied, future])
    by_id = {team.team_id: team for team in teams}
    assert completed == 1
    assert by_id[TEAM_A].draws == 1
    assert by_id[TEAM_A].form == ["D"]
    assert by_id[TEAM_A].win_percentage == 0.0
    assert by_id["300:future"].win_percentage is None


def test_normalizer_handles_malformed_optional_nested_fields():
    raw = raw_game(ended=False)
    raw["started"] = "false"
    raw["ended"] = "false"
    raw["iceRink"] = []
    raw["homeTeam"]["goalEvents"] = "not a list"
    raw["awayTeam"]["goalEvents"] = [
        None,
        {"gameTime": "120", "scorerPlayer": []},
        {"gameTime": 90, "period": 1, "scorerPlayer": {"firstName": "Ada", "lastName": "Player"}},
    ]
    game = normalize_game(raw)
    assert game.status == "upcoming"
    assert game.city is None and game.venue is None
    assert len(game.goal_events) == 2
    assert game.goal_events[0].game_time_seconds is None
    assert game.goal_events[1].scorer == "Ada Player"
    raw["homeTeam"] = []
    assert normalize_game(raw).home_team.team_id is None


def test_analysis_uses_season_history_independent_of_display_limits(client, upstream):
    games = [raw_game(day, start=f"2026-09-{day:02d}T15:30:00Z") for day in range(1, 16)]
    calls = upstream({"games": list(reversed(games))})
    cards = client.get("/api/liiga/games", params={
        "season": 2027, "limit": 1, "from_date": "2026-09-15",
    })
    assert cards.status_code == 200
    assert cards.json()["count"] == 1
    assert cards.json()["games"][0]["id"] == 15

    response = client.get("/api/liiga/analysis?season=2027")
    assert response.status_code == 200
    result = response.json()
    assert result["games_in_dataset"] == result["completed_games"] == 15
    assert result["excluded_games"] == 0
    assert result["data_mode"] == "real"
    assert result["scope"] == "regular_season_games_returned_by_provider"
    assert all(team["matches_played"] == 15 for team in result["teams"])
    assert result["updated_at"] == cards.json()["updated_at"]
    assert len(calls) == 1
    assert dict(calls[0].url.params) == {"season": "2027", "serie": "RUNKOSARJA"}


def test_match_filtering_happens_before_limit_and_uses_helsinki_date(client, upstream):
    upstream({"games": [
        raw_game(1, home="300:other", away="400:other", start="2026-09-01T12:00:00Z"),
        raw_game(2, start="2026-09-01T21:30:00Z"),  # Sep 2 in Helsinki.
        raw_game(3, start="2026-09-02T12:00:00Z"),
    ]})
    response = client.get("/api/liiga/games", params={
        "season": 2027, "limit": 1, "from_date": "2026-09-02", "team_id": TEAM_A,
    })
    assert response.status_code == 200
    assert [game["id"] for game in response.json()["games"]] == [2]


def test_single_team_analysis_and_unknown_team(client, upstream):
    upstream({"games": [raw_game()]})
    response = client.get(f"/api/liiga/teams/{quote(TEAM_A, safe='')}/analysis?season=2027")
    assert response.status_code == 200
    assert response.json()["team_id"] == TEAM_A
    assert response.json()["wins"] == 1
    assert response.json()["goal_difference"] == 2
    assert client.get("/api/liiga/teams/missing/analysis?season=2027").status_code == 404


@pytest.mark.parametrize("path", [
    "/api/liiga/games?season=1999",
    "/api/liiga/games?limit=31",
    "/api/liiga/games?from_date=invalid",
    "/api/liiga/analysis?season=2101",
    "/api/liiga/teams/alpha/analysis?season=invalid",
])
def test_invalid_parameters_rejected_without_provider_request(client, path):
    assert client.get(path).status_code == 422


@pytest.mark.parametrize("payload", [
    [],
    {"games": "not a list"},
    {"games": [None]},
    {"games": [{"id": 1}]},
    {"games": [raw_game(), raw_game()]},
    {"games": [{**raw_game(), "season": 2026}]},
    {"games": [{**raw_game(), "serie": "PLAYOFFS"}]},
])
def test_malformed_provider_responses_return_502_without_caching(client, upstream, payload):
    calls = upstream(payload)
    assert client.get("/api/liiga/analysis?season=2027").status_code == 502
    assert client.get("/api/liiga/analysis?season=2027").status_code == 502
    assert len(calls) == 2


@pytest.mark.parametrize("failure", ["http", "timeout", "json"])
def test_provider_failure_returns_502_and_next_request_can_recover(client, upstream, failure):
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            if failure == "timeout":
                raise httpx.ReadTimeout("provider timed out", request=request)
            if failure == "json":
                return httpx.Response(200, text="not JSON")
            return httpx.Response(503, text="unavailable")
        return httpx.Response(200, json={"games": [raw_game()]})

    upstream(handler=handler)
    assert client.get("/api/liiga/analysis?season=2027").status_code == 502
    recovered = client.get("/api/liiga/analysis?season=2027")
    assert recovered.status_code == 200
    assert recovered.json()["completed_games"] == 1
    assert attempts == 2


def test_expired_cache_fetches_new_results(client, upstream):
    games = [raw_game()]

    def handler(request):
        return httpx.Response(200, json={"games": deepcopy(games)})

    calls = upstream(handler=handler)
    first = client.get("/api/liiga/analysis?season=2027").json()
    games.append(raw_game(2))
    cached = client.get("/api/liiga/analysis?season=2027").json()
    assert cached == first
    assert len(calls) == 1

    _, snapshot = liiga_client._cache[2027]
    liiga_client._cache[2027] = (time.monotonic() - liiga_client.CACHE_SECONDS - 1, snapshot)
    refreshed = client.get("/api/liiga/analysis?season=2027").json()
    assert refreshed["completed_games"] == 2
    assert len(calls) == 2


def test_empty_provider_season_remains_empty_real_data(client, upstream):
    upstream({"games": []})
    result = client.get("/api/liiga/analysis?season=2027").json()
    assert result["teams"] == []
    assert result["completed_games"] == result["games_in_dataset"] == 0
    assert result["data_mode"] == "real"
