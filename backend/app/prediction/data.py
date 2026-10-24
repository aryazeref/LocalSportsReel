"""Validated provider snapshots for forecasting and points-table reconciliation.

The cache stores raw public data, not trained Python objects or credentials.
Current snapshots refresh every two minutes; historical snapshots every day.
No stale or malformed cache is substituted when a refresh fails.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from weakref import WeakKeyDictionary

import httpx

from ..services.liiga_client import LIIGA_API_BASE_URL
from .domain import HELSINKI, REGULATION, Match, Standing, canonical_team_id

CACHE_DIR = Path(os.getenv("PREDICTION_CACHE_DIR", str(Path(__file__).resolve().parents[2] / ".prediction-cache")))
HISTORICAL_TTL_SECONDS = 86400
CURRENT_TTL_SECONDS = 120
SCHEMA_VERSION = 1
_locks: WeakKeyDictionary = WeakKeyDictionary()


class PredictionDataError(Exception):
    """Public provider data could not be loaded or validated safely."""


@dataclass(frozen=True)
class SeasonData:
    matches: tuple[Match, ...]
    fetched_at: datetime
    source_hash: str
    diagnostics: dict[str, int]


@dataclass(frozen=True)
class StandingsData:
    standings: tuple[Standing, ...]
    fetched_at: datetime
    playoff_lines: list[int]
    source_updated_at: datetime | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _season_year() -> int:
    today = _now().astimezone(HELSINKI).date()
    return today.year + (today.month >= 7)


def _validate_season(season: int) -> None:
    if type(season) is not int or not 2000 <= season <= 2100:
        raise PredictionDataError("Season must be an integer between 2000 and 2100.")


def _required_int(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise PredictionDataError(f"Liiga returned an invalid {field}.")
    return value


def _score(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _xg(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if math.isfinite(number) and number >= 0:
            return number
    return None


def _date(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise PredictionDataError(f"Liiga returned an invalid {field} timestamp.")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise PredictionDataError(f"Liiga returned an invalid {field} timestamp.") from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise PredictionDataError(f"Liiga returned {field} without a timezone.")
    return result.astimezone(timezone.utc)


def _team(raw: Any) -> tuple[str, str, dict]:
    if raw is None:
        return "", "To be decided", {}
    if not isinstance(raw, dict):
        raise PredictionDataError("Liiga returned an invalid match team.")
    value = raw.get("teamId")
    if value is None or value == "":
        team_id = ""
    elif isinstance(value, (str, int)) and not isinstance(value, bool):
        team_id = canonical_team_id(str(value).strip())
        if not team_id.isdecimal() or int(team_id) <= 0:
            team_id = ""
    else:
        raise PredictionDataError("Liiga returned an invalid team ID.")
    name = raw.get("teamName") or raw.get("teamPlaceholder")
    return team_id, name.strip() if isinstance(name, str) and name.strip() else "To be decided", raw


def _normal_period_totals(raw: dict) -> tuple[int, int] | None:
    periods = raw.get("periods")
    if not isinstance(periods, list):
        return None
    normal = [period for period in periods if isinstance(period, dict) and period.get("category") == "NORMAL"]
    if len(normal) != 3 or {period.get("index") for period in normal if type(period.get("index")) is int} != {1, 2, 3}:
        return None
    home = [_score(period.get("homeTeamGoals")) for period in normal]
    away = [_score(period.get("awayTeamGoals")) for period in normal]
    if any(value is None for value in home + away):
        return None
    return sum(home), sum(away)


def parse_match(raw: dict, expected_season: int) -> Match:
    """Normalize a match without interpreting unplayed placeholder scores.

    Unresolved identities remain empty so dataset diagnostics can block an
    incomplete simulation. A finished match lacking usable regulation scores
    is retained but its domain outcome is None, excluding it from training.
    """
    if not isinstance(raw, dict):
        raise PredictionDataError("Liiga returned a match that is not an object.")
    if raw.get("season") != expected_season or type(raw.get("season")) is not int:
        raise PredictionDataError("Liiga returned a match from a different season.")
    if raw.get("serie") != "RUNKOSARJA":
        raise PredictionDataError("Liiga returned a match outside the regular season.")
    game_id = _required_int(raw.get("id"), "match ID")
    if game_id == 0:
        raise PredictionDataError("Liiga returned an invalid match ID.")
    for flag in ("started", "ended"):
        if raw.get(flag) is not None and type(raw[flag]) is not bool:
            raise PredictionDataError("Liiga returned a non-boolean match status.")
    finish_type = raw.get("finishedType")
    if finish_type is not None and not isinstance(finish_type, str):
        raise PredictionDataError("Liiga returned an invalid finished type.")
    status = (
        "cancelled" if finish_type == "CANCELLED" else
        "finished" if raw.get("ended") is True else
        "live" if raw.get("started") is True else "upcoming"
    )
    home_id, home_name, home = _team(raw.get("homeTeam"))
    away_id, away_name, away = _team(raw.get("awayTeam"))
    played = status in {"finished", "live"}
    home_goals = _score(home.get("goals")) if played else None
    away_goals = _score(away.get("goals")) if played else None
    regulation = _normal_period_totals(raw) if status == "finished" else None
    if regulation is None and status == "finished" and finish_type == REGULATION:
        # A regulation-ended final score is itself a valid regulation score.
        regulation = home_goals, away_goals
    return Match(
        season=expected_season,
        game_id=game_id,
        start=_date(raw.get("start"), "match start"),
        home_id=home_id,
        away_id=away_id,
        home_name=home_name,
        away_name=away_name,
        status=status,
        home_goals=home_goals,
        away_goals=away_goals,
        home_regulation_goals=regulation[0] if regulation else None,
        away_regulation_goals=regulation[1] if regulation else None,
        finish_type=finish_type,
        home_expected_goals=_xg(home.get("expectedGoals")) if status == "finished" else None,
        away_expected_goals=_xg(away.get("expectedGoals")) if status == "finished" else None,
    )


def _digest(payload: dict) -> str:
    try:
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError) as error:
        raise PredictionDataError("Liiga returned non-JSON numerical data.") from error
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _season_data(payload: Any, season: int, fetched_at: datetime) -> SeasonData:
    if not isinstance(payload, dict) or not isinstance(payload.get("games"), list):
        raise PredictionDataError("Unexpected Liiga season response format.")
    diagnostics = {name: 0 for name in (
        "total_records", "usable_finished", "unusable_finished", "finished_records",
        "upcoming_records", "live_records", "cancelled_records", "unresolved_team_records",
        "duplicate_team_records", "regulation_score_fallbacks",
    )}
    matches, seen = [], set()
    for raw in payload["games"]:
        match = parse_match(raw, season)
        if match.key in seen:
            raise PredictionDataError("Liiga returned duplicate season/match IDs.")
        seen.add(match.key)
        matches.append(match)
        diagnostics["total_records"] += 1
        diagnostics[f"{match.status}_records"] += 1
        if not match.home_id or not match.away_id:
            diagnostics["unresolved_team_records"] += 1
        if match.home_id and match.home_id == match.away_id:
            diagnostics["duplicate_team_records"] += 1
        if match.status == "finished":
            diagnostics["usable_finished" if match.outcome is not None else "unusable_finished"] += 1
            if match.finish_type == REGULATION and _normal_period_totals(raw) is None and match.outcome is not None:
                diagnostics["regulation_score_fallbacks"] += 1
    matches.sort(key=lambda match: (match.start, match.game_id))
    return SeasonData(tuple(matches), fetched_at, _digest(payload), diagnostics)


def _cache_path(season: int) -> Path:
    return CACHE_DIR / "seasons" / f"{season}.json"


def _read_cache(season: int) -> SeasonData | None:
    try:
        envelope = json.loads(_cache_path(season).read_text(encoding="utf-8"))
        if (
            not isinstance(envelope, dict)
            or type(envelope.get("schema_version")) is not int
            or envelope["schema_version"] != SCHEMA_VERSION
            or type(envelope.get("season")) is not int
            or envelope["season"] != season
        ):
            return None
        fetched_at = _date(envelope.get("fetched_at"), "cached fetch")
        ttl = CURRENT_TTL_SECONDS if season >= _season_year() else HISTORICAL_TTL_SECONDS
        age = (_now() - fetched_at).total_seconds()
        if not 0 <= age < ttl:
            return None
        result = _season_data(envelope.get("payload"), season, fetched_at)
        return result if envelope.get("source_hash") == result.source_hash else None
    except (OSError, ValueError, TypeError, PredictionDataError):
        return None


def _write_cache(season: int, payload: dict, data: SeasonData) -> None:
    target = _cache_path(season)
    temporary = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        envelope = {"schema_version": SCHEMA_VERSION, "season": season,
                    "fetched_at": data.fetched_at.isoformat(), "payload": payload,
                    "source_hash": data.source_hash}
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                         prefix=f".{season}-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(envelope, handle, ensure_ascii=False, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except OSError as error:
        raise PredictionDataError("Unable to persist the prediction history cache.") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _lock(season: int) -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    by_season = _locks.setdefault(loop, {})
    return by_season.setdefault(season, asyncio.Lock())


async def _request(path: str, params: dict) -> Any:
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(f"{LIIGA_API_BASE_URL}{path}", params=params,
                                        headers={"Accept": "application/json"})
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as error:
        raise PredictionDataError(f"Liiga returned HTTP {error.response.status_code} while loading prediction data.") from error
    except (httpx.HTTPError, ValueError) as error:
        raise PredictionDataError("Unable to load valid prediction data from Liiga.") from error


async def load_season(season: int, *, refresh: bool = False) -> SeasonData:
    _validate_season(season)
    if not refresh:
        cached = _read_cache(season)
        if cached is not None:
            return cached
    async with _lock(season):
        if not refresh:
            cached = _read_cache(season)
            if cached is not None:
                return cached
        payload = await _request("/api/v1/games", {"season": season, "serie": "RUNKOSARJA"})
        result = _season_data(payload, season, _now())
        _write_cache(season, payload, result)
        return result


async def load_standings(season: int) -> StandingsData:
    """Fetch the non-live official table; reject incompatible point semantics."""
    _validate_season(season)
    payload = await _request("/api/v1/standings/RUNKOSARJA", {"season": season, "isLive": "false"})
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list) or not payload["items"]:
        raise PredictionDataError("Official Liiga standings are unavailable for this season.")
    standings, seen = [], set()
    for row in payload["items"]:
        if not isinstance(row, dict) or row.get("serie") not in (None, "RUNKOSARJA"):
            raise PredictionDataError("Unexpected Liiga standings row.")
        team_id, name, _ = _team({"teamId": row.get("teamId"), "teamName": row.get("teamName")})
        if not team_id or team_id in seen:
            raise PredictionDataError("Liiga standings contain missing or duplicate team IDs.")
        seen.add(team_id)
        fields = {key: _required_int(row.get(key), f"standings {key}") for key in
                  ("points", "games", "wins", "overtimeWins", "overtimeLosses", "losses", "goals", "goalsAgainst")}
        if fields["points"] != 3 * fields["wins"] + 2 * fields["overtimeWins"] + fields["overtimeLosses"]:
            raise PredictionDataError("Liiga standings do not follow the supported 3-2-1-0 points rules.")
        if fields["games"] != fields["wins"] + fields["overtimeWins"] + fields["overtimeLosses"] + fields["losses"]:
            raise PredictionDataError("Liiga standings game counts do not reconcile with results.")
        if row.get("ties") is not None and _required_int(row["ties"], "standings ties") != fields["overtimeWins"] + fields["overtimeLosses"]:
            raise PredictionDataError("Liiga standings regulation ties do not reconcile.")
        standings.append(Standing(team_id, name, fields["points"], fields["games"],
                                  fields["wins"], fields["overtimeWins"], fields["overtimeLosses"],
                                  fields["losses"], fields["goals"], fields["goalsAgainst"]))
    lines = payload.get("playoffsLines")
    lines = [] if lines is None else lines
    if not isinstance(lines, list) or any(type(value) is not int or value < 0 for value in lines):
        raise PredictionDataError("Liiga returned invalid standings boundary metadata.")
    source_updated_at = None
    if payload.get("cacheUpdateDate") is not None:
        source_updated_at = _date(payload["cacheUpdateDate"], "standings update")
    return StandingsData(tuple(standings), _now(), lines, source_updated_at)
