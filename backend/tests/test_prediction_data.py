"""Prediction ingestion contracts with controlled public-provider responses."""

import asyncio
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.prediction import data
from app.prediction.domain import EXTRA_TIME, REGULATION

REAL_ASYNC_CLIENT = httpx.AsyncClient
NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)


def game(game_id=1, *, season=2027, home=3, away=1, finish=REGULATION,
         ended=True, regulation=None):
    regulation = regulation if regulation is not None else (home, away)
    return {
        "id": game_id, "season": season, "serie": "RUNKOSARJA",
        "start": f"{season - 1}-09-01T15:30:00Z", "started": ended, "ended": ended,
        "finishedType": finish,
        "homeTeam": {"teamId": "100:alpha", "teamName": "Alpha", "goals": home, "expectedGoals": 2.5},
        "awayTeam": {"teamId": "200:beta", "teamName": "Beta", "goals": away, "expectedGoals": 1.2},
        "periods": [
            {"index": 1, "category": "NORMAL", "homeTeamGoals": regulation[0], "awayTeamGoals": regulation[1]},
            {"index": 2, "category": "NORMAL", "homeTeamGoals": 0, "awayTeamGoals": 0},
            {"index": 3, "category": "NORMAL", "homeTeamGoals": 0, "awayTeamGoals": 0},
            {"index": 4, "category": "OVERTIME", "homeTeamGoals": 1, "awayTeamGoals": 0},
            {"index": 5, "category": "WINNING_SHOT_COMPETITION", "homeTeamGoals": 1, "awayTeamGoals": 0},
        ],
    }


def standings_row(team_id="100:alpha", **changes):
    return {
        "teamId": team_id, "teamName": "Alpha", "serie": "RUNKOSARJA", "points": 9,
        "games": 5, "wins": 2, "overtimeWins": 1, "overtimeLosses": 1, "losses": 1,
        "ties": 2, "goals": 15, "goalsAgainst": 10, "powerPlayPercentage": "0.333333",
        **changes,
    }


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(data, "_now", lambda: NOW)

    def reject(request):
        pytest.fail(f"Unexpected provider request to {request.url.path}")

    monkeypatch.setattr(data.httpx, "AsyncClient", lambda **kwargs: REAL_ASYNC_CLIENT(
        transport=httpx.MockTransport(reject), **kwargs,
    ))


@pytest.fixture
def upstream(monkeypatch):
    def configure(payload=None, *, status=200, handler=None):
        calls = []

        def respond(request):
            calls.append(request)
            return handler(request) if handler else httpx.Response(status, json=payload)

        monkeypatch.setattr(data.httpx, "AsyncClient", lambda **kwargs: REAL_ASYNC_CLIENT(
            transport=httpx.MockTransport(respond), **kwargs,
        ))
        return calls
    return configure


@pytest.mark.parametrize("home,away,finish,regulation,outcome", [
    (3, 1, REGULATION, (3, 1), 0),
    (1, 3, REGULATION, (1, 3), 3),
    (4, 3, "ENDED_DURING_EXTENDED_GAME_TIME", (3, 3), 1),
    (2, 3, "ENDED_DURING_EXTENDED_GAME_TIME", (2, 2), 2),
    (4, 3, "ENDED_DURING_WINNING_SHOT_COMPETITION", (3, 3), 1),
])
def test_regulation_and_extra_time_labels(home, away, finish, regulation, outcome):
    match = data.parse_match(game(home=home, away=away, finish=finish, regulation=regulation), 2027)
    assert match.outcome == outcome
    assert (match.home_regulation_goals, match.away_regulation_goals) == regulation
    assert match.home_id == "100" and match.away_id == "200"
    assert match.start.tzinfo is not None
    assert match.home_expected_goals == 2.5


def test_period_placeholders_do_not_manufacture_overtime():
    match = data.parse_match(game(), 2027)
    assert match.outcome == 0
    assert (match.home_regulation_goals, match.away_regulation_goals) == (3, 1)


def test_regulation_final_score_fallback_is_counted(upstream):
    raw = game()
    raw.pop("periods")
    upstream({"games": [raw]})
    result = asyncio.run(data.load_season(2027))
    assert result.matches[0].outcome == 0
    assert result.diagnostics["regulation_score_fallbacks"] == 1


def test_missing_overtime_periods_remain_unknown_instead_of_using_shootout_score(upstream):
    raw = game(home=4, away=3, finish="ENDED_DURING_WINNING_SHOT_COMPETITION")
    raw.pop("periods")
    upstream({"games": [raw]})
    result = asyncio.run(data.load_season(2027))
    assert result.matches[0].home_regulation_goals is None
    assert result.matches[0].outcome is None
    assert result.diagnostics["unusable_finished"] == 1


def test_future_placeholder_scores_and_xg_are_unknown():
    match = data.parse_match(game(home=99, away=0, finish="ACTIVE_OR_NOT_STARTED", ended=False), 2027)
    assert match.status == "upcoming"
    assert match.home_goals is match.home_regulation_goals is match.home_expected_goals is None
    assert match.outcome is None


def test_cancelled_game_is_not_a_zero_zero_draw():
    match = data.parse_match(game(home=0, away=0, finish="CANCELLED"), 2027)
    assert match.status == "cancelled" and match.outcome is None
    assert match.home_goals is None


def test_live_score_is_retained_but_never_becomes_a_training_label():
    raw = game(home=2, away=0, ended=False)
    raw["started"] = True
    match = data.parse_match(raw, 2027)
    assert match.status == "live" and match.home_goals == 2
    assert match.home_regulation_goals is None and match.outcome is None


@pytest.mark.parametrize("invalid", [None, -1, True, "3", 2.5])
def test_invalid_score_is_not_coerced_to_a_valid_label(invalid):
    match = data.parse_match(game(home=invalid), 2027)
    assert match.home_goals is None and match.outcome is None


def test_unresolved_fixture_is_preserved_and_explicitly_counted(upstream):
    raw = game(ended=False)
    raw["homeTeam"] = {"teamPlaceholder": "Winner QF1", "teamId": None}
    upstream({"games": [raw]})
    result = asyncio.run(data.load_season(2027))
    assert len(result.matches) == 1 and result.matches[0].home_id == ""
    assert result.diagnostics["unresolved_team_records"] == 1
    assert result.diagnostics["total_records"] == 1


@pytest.mark.parametrize("changes", [
    {"season": 2026}, {"serie": "PLAYOFFS"}, {"id": "1"}, {"ended": "true"},
    {"start": "2026-09-01T15:30:00"}, {"homeTeam": []},
])
def test_malformed_identity_status_or_time_is_rejected(changes):
    with pytest.raises(data.PredictionDataError):
        data.parse_match({**game(), **changes}, 2027)


def test_cache_is_reusable_raw_json_and_omits_display_filters(upstream):
    calls = upstream({"games": [game()]})
    first = asyncio.run(data.load_season(2027))
    second = asyncio.run(data.load_season(2027))
    assert first == second and len(calls) == 1
    assert dict(calls[0].url.params) == {"season": "2027", "serie": "RUNKOSARJA"}
    saved = json.loads((data.CACHE_DIR / "seasons" / "2027.json").read_text())
    assert saved["payload"]["games"][0]["id"] == 1
    assert saved["source_hash"] == first.source_hash
    assert saved["schema_version"] == 1
    assert not list(data.CACHE_DIR.rglob("*.tmp"))


@pytest.mark.parametrize("corruption", ["json", "hash", "payload", "future_time"])
def test_corrupt_cache_is_refetched_not_trusted(upstream, corruption):
    calls = upstream({"games": [game()]})
    asyncio.run(data.load_season(2027))
    path = data.CACHE_DIR / "seasons" / "2027.json"
    if corruption == "json":
        path.write_text("{not JSON")
    else:
        stored = json.loads(path.read_text())
        if corruption == "hash": stored["source_hash"] = "wrong"
        elif corruption == "payload": stored["payload"]["games"][0]["id"] = "invalid"
        else: stored["fetched_at"] = (NOW + timedelta(days=1)).isoformat()
        path.write_text(json.dumps(stored))
    assert asyncio.run(data.load_season(2027)).matches[0].game_id == 1
    assert len(calls) == 2


def test_current_cache_expires_after_two_minutes(upstream, monkeypatch):
    payload = {"games": [game()]}
    calls = upstream(handler=lambda _: httpx.Response(200, json=deepcopy(payload)))
    first = asyncio.run(data.load_season(2027))
    payload["games"].append(game(2))
    monkeypatch.setattr(data, "_now", lambda: NOW + timedelta(seconds=121))
    refreshed = asyncio.run(data.load_season(2027))
    assert len(refreshed.matches) == 2 and refreshed.fetched_at > first.fetched_at
    assert len(calls) == 2


def test_historical_cache_has_a_one_day_ttl(upstream, monkeypatch):
    calls = upstream({"games": [game(season=2025)]})
    asyncio.run(data.load_season(2025))
    monkeypatch.setattr(data, "_now", lambda: NOW + timedelta(hours=1))
    asyncio.run(data.load_season(2025))
    assert len(calls) == 1
    monkeypatch.setattr(data, "_now", lambda: NOW + timedelta(days=1, seconds=1))
    asyncio.run(data.load_season(2025))
    assert len(calls) == 2


def test_explicit_refresh_requests_new_data_and_failure_never_overwrites_old_cache(upstream):
    upstream({"games": [game()]})
    asyncio.run(data.load_season(2027))
    path = data.CACHE_DIR / "seasons" / "2027.json"
    old_contents = path.read_text()
    upstream(status=503)
    with pytest.raises(data.PredictionDataError, match="HTTP 503"):
        asyncio.run(data.load_season(2027, refresh=True))
    assert path.read_text() == old_contents
    calls = upstream({"games": [game(), game(2)]})
    assert len(asyncio.run(data.load_season(2027, refresh=True)).matches) == 2
    assert len(calls) == 1


@pytest.mark.parametrize("payload", [[], {"games": "wrong"}, {"games": [None]}, {"games": [game(), game()]}])
def test_invalid_provider_payload_is_never_cached(upstream, payload):
    upstream(payload)
    with pytest.raises(data.PredictionDataError):
        asyncio.run(data.load_season(2027))
    assert not (data.CACHE_DIR / "seasons" / "2027.json").exists()


def test_standings_preserve_official_order_and_validate_points(upstream):
    calls = upstream({"items": [standings_row("200:beta"), standings_row("100:alpha")],
                      "playoffsLines": [1], "cacheUpdateDate": "2026-10-24T10:00:00Z"})
    table = asyncio.run(data.load_standings(2027))
    assert [team.team_id for team in table.standings] == ["200", "100"]
    assert table.standings[0].points == 9 and table.standings[0].played == 5
    assert table.playoff_lines == [1]
    assert table.source_updated_at == datetime(2026, 10, 24, 10, tzinfo=timezone.utc)
    assert dict(calls[0].url.params) == {"season": "2027", "isLive": "false"}


@pytest.mark.parametrize("changes", [{"points": 10}, {"games": 6}, {"ties": 0},
                                      {"wins": True}, {"goals": None}, {"teamId": None}])
def test_incompatible_or_incomplete_standings_are_rejected(upstream, changes):
    upstream({"items": [standings_row(**changes)]})
    with pytest.raises(data.PredictionDataError):
        asyncio.run(data.load_standings(2027))


def test_duplicate_standings_identity_is_rejected(upstream):
    upstream({"items": [standings_row(), standings_row("100:renamed")]})
    with pytest.raises(data.PredictionDataError, match="duplicate"):
        asyncio.run(data.load_standings(2027))
