"""Fetch and normalize Liiga's documented v1 regular-season game dataset."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import ValidationError

from ..models import LiigaGame

logger = logging.getLogger(__name__)
LIIGA_API_BASE_URL = os.getenv(
    "LIIGA_API_BASE_URL", "https://prod.liiga-backend.liiga.fi/stats"
).rstrip("/")
CACHE_SECONDS = 120
MAX_CACHED_SEASONS = 8


class LiigaAPIError(Exception):
    """The provider could not supply a valid, usable season dataset."""


@dataclass(frozen=True)
class SeasonGames:
    games: tuple[LiigaGame, ...]
    updated_at: datetime


_cache: OrderedDict[int, tuple[float, SeasonGames]] = OrderedDict()
# One fetch serves simultaneous match-list and analysis requests in a process.
_fetch_lock = asyncio.Lock()


def _nonnegative_int(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _team(raw: Any) -> dict[str, Any]:
    team = raw if isinstance(raw, dict) else {}
    logos = team.get("logos") if isinstance(team.get("logos"), dict) else {}
    team_id = team.get("teamId")
    return {
        "name": team.get("teamName") or team.get("teamPlaceholder") or "To be decided",
        "team_id": str(team_id) if isinstance(team_id, (str, int)) and not isinstance(team_id, bool) else None,
        "goals": _nonnegative_int(team.get("goals")),
        "logo_url": logos.get("lightBg") or logos.get("darkBg"),
    }


def _goal_events(raw: Any, side: str) -> list[dict[str, Any]]:
    if not isinstance(raw, dict) or not isinstance(raw.get("goalEvents"), list):
        return []
    events = []
    for event in raw["goalEvents"]:
        if not isinstance(event, dict):
            continue
        player = event.get("scorerPlayer")
        player = player if isinstance(player, dict) else {}
        name = " ".join(str(player[key]) for key in ("firstName", "lastName") if player.get(key))
        events.append({
            "team_side": side,
            "scorer": name or "Unknown scorer",
            "period": _nonnegative_int(event.get("period")),
            "game_time_seconds": _nonnegative_int(event.get("gameTime")),
            "has_video": bool(event.get("videoClipUrl")),
        })
    return events


def normalize_game(raw: dict[str, Any]) -> LiigaGame:
    """Keep the frontend contract independent of the provider's verbose schema."""
    home, away = raw.get("homeTeam"), raw.get("awayTeam")
    rink = raw.get("iceRink")
    rink = rink if isinstance(rink, dict) else {}
    events = _goal_events(home, "home") + _goal_events(away, "away")
    events.sort(key=lambda event: event["game_time_seconds"] or 0)
    if raw.get("finishedType") == "CANCELLED":
        status = "cancelled"
    elif raw.get("ended") is True:
        status = "finished"
    elif raw.get("started") is True:
        status = "live"
    else:
        status = "upcoming"
    return LiigaGame(
        id=raw.get("id"),
        season=raw.get("season"),
        start=raw.get("start"),
        status=status,
        home_team=_team(home),
        away_team=_team(away),
        venue=rink.get("name"),
        city=rink.get("city"),
        goal_events=events,
    )


def _cached(season: int) -> SeasonGames | None:
    cached = _cache.get(season)
    if cached is not None and time.monotonic() - cached[0] < CACHE_SECONDS:
        _cache.move_to_end(season)
        return cached[1]
    return None


async def fetch_season_games(season: int) -> SeasonGames:
    """Omit the optional upstream limit to analyze all returned season games.

    v1 documents a GamesDTO with games and navigation dates, without a page or
    cursor. No display limit or recent-date filter belongs in this request.
    The API does not provide a total for an independent completeness check.
    """
    cached = _cached(season)
    if cached is not None:
        return cached
    async with _fetch_lock:
        cached = _cached(season)
        if cached is not None:
            return cached
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                response = await client.get(
                    f"{LIIGA_API_BASE_URL}/api/v1/games",
                    params={"season": season, "serie": "RUNKOSARJA"},
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            logger.warning("Liiga request failed (%s)", type(error).__name__)
            raise LiigaAPIError("Unable to load real Liiga matches from the upstream API.") from error

        if not isinstance(payload, dict) or not isinstance(payload.get("games"), list):
            raise LiigaAPIError("Unexpected Liiga API response format.")
        try:
            games = []
            seen = set()
            for raw in payload["games"]:
                if not isinstance(raw, dict):
                    raise LiigaAPIError("Unexpected Liiga match format.")
                game = normalize_game(raw)
                if game.season != season or raw.get("serie") not in (None, "RUNKOSARJA"):
                    raise LiigaAPIError("Liiga returned games outside the requested regular season.")
                if game.id in seen:
                    raise LiigaAPIError("Liiga returned duplicate match IDs.")
                seen.add(game.id)
                games.append(game)
        except ValidationError as error:
            raise LiigaAPIError("Liiga returned a match with invalid fields.") from error
        games.sort(key=lambda game: (game.start, game.id))
        snapshot = SeasonGames(tuple(games), datetime.now(timezone.utc))
        _cache[season] = (time.monotonic(), snapshot)
        _cache.move_to_end(season)
        while len(_cache) > MAX_CACHED_SEASONS:
            _cache.popitem(last=False)
        return snapshot
