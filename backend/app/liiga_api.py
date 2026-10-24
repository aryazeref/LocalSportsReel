"""Liiga Stats API v1 adapter for LocalSportsReel.

This router intentionally does not modify the existing synthetic /api/feed
or /api/stories endpoints. It exposes a small, stable JSON format to Next.js.

Swagger: https://prod.liiga-backend.liiga.fi/stats/swagger-ui/index.html?urls.primaryName=v1
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/liiga", tags=["Liiga (real data)"])
logger = logging.getLogger(__name__)

# Keep the host configurable: use the exact Request URL shown by Swagger if
# your deployment uses a different proxy prefix (for example /stats or /api).
LIIGA_API_BASE_URL = os.getenv(
    "LIIGA_API_BASE_URL", "https://prod.liiga-backend.liiga.fi/stats"
).rstrip("/")

# Only normalized (small) responses are kept in this cache, not enormous
# upstream JSON documents. Cache is in-memory, so it is per backend process.
CACHE_SECONDS = 120
_cache: dict[tuple[Any, ...], tuple[float, dict[str, Any]]] = {}


def _team(raw: Any) -> dict[str, Any]:
    """Extract fields our UI needs from a nested Liiga team object."""
    team = raw if isinstance(raw, dict) else {}
    goals = team.get("goals")
    logos = team.get("logos") if isinstance(team.get("logos"), dict) else {}

    return {
        "name": team.get("teamName") or team.get("teamPlaceholder") or "To be decided",
        "team_id": team.get("teamId"),
        "goals": goals if isinstance(goals, int) and not isinstance(goals, bool) else None,
        "logo_url": logos.get("lightBg") or logos.get("darkBg"),
    }


def _goal_events(raw: Any, side: str) -> list[dict[str, Any]]:
    """Extract goal event summaries when they are present in the API result."""
    if not isinstance(raw, dict):
        return []

    result = []
    for event in raw.get("goalEvents") or []:
        if not isinstance(event, dict):
            continue
        player = event.get("scorerPlayer") or {}
        if not isinstance(player, dict):
            player = {}
        player_name = " ".join(
            str(name) for name in (player.get("firstName"), player.get("lastName"))
            if name
        )
        result.append(
            {
                "team_side": side,
                "scorer": player_name or "Unknown scorer",
                "period": event.get("period"),
                "game_time_seconds": event.get("gameTime"),
                # Some returned events have video metadata, but the frontend
                # doesn't embed copyrighted clips automatically.
                "has_video": bool(event.get("videoClipUrl")),
            }
        )
    return result


def normalize_game(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert the verbose Liiga v1 shape into our own frontend contract.

    We deliberately do NOT call this a Moment or Story: those existing model
    types represent synthetic demo highlights with different semantics.
    """
    home = raw.get("homeTeam") or {}
    away = raw.get("awayTeam") or {}

    events = _goal_events(home, "home") + _goal_events(away, "away")
    events.sort(key=lambda ev: ev.get("game_time_seconds") or 0)

    started = bool(raw.get("started"))
    ended = bool(raw.get("ended"))
    return {
        "id": raw.get("id"),
        "season": raw.get("season"),
        "start": raw.get("start"),
        "status": "finished" if ended else ("live" if started else "upcoming"),
        "home_team": _team(home),
        "away_team": _team(away),
        "venue": (raw.get("iceRink") or {}).get("name") if isinstance(raw.get("iceRink"), dict) else None,
        "city": (raw.get("iceRink") or {}).get("city") if isinstance(raw.get("iceRink"), dict) else None,
        "goal_events": events,
    }


@router.get("/games")
async def get_liiga_games(
    season: int = Query(default=2027, ge=2000, le=2100),
    limit: int = Query(default=12, ge=1, le=30),
    from_date: date | None = Query(default=None),
) -> dict[str, Any]:
    """Get a shortlist of real Liiga regular-season games.

    Example: GET /api/liiga/games?season=2027&limit=12

    When no date is supplied, request games starting seven days ago so the UI
    can include recent results and coming fixtures. This is NOT live streaming.
    """
    if from_date is None:
        from_date = date.today() - timedelta(days=7)

    key = (season, limit, from_date.isoformat())
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]

    url = f"{LIIGA_API_BASE_URL}/api/v1/games"
    params = {
        "season": season,
        "serie": "RUNKOSARJA",
        "fromDate": from_date.isoformat(),
        # Fetch a little more than we display so we can sort chronologically.
        "limit": min(limit * 3, 90),
    }

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url, params=params, headers={"Accept": "application/json"})
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        logger.warning("Liiga API request failed: %s", error)
        raise HTTPException(
            status_code=502,
            detail="Unable to load real Liiga matches from the upstream API.",
        ) from error

    # This V1 endpoint documents {"games": [...]}. It is deliberately
    # different from the other /api/v2 endpoint whose result was a bare list.
    if not isinstance(payload, dict) or not isinstance(payload.get("games"), list):
        raise HTTPException(status_code=502, detail="Unexpected Liiga API response format.")

    games = [normalize_game(item) for item in payload["games"] if isinstance(item, dict)]
    games.sort(key=lambda item: item.get("start") or "")
    result = {
        "source": "Liiga Stats API v1",
        "data_mode": "real",
        "season": season,
        "count": min(limit, len(games)),
        "games": games[:limit],
    }

    # Keep the cache bounded on a long-running development server.
    if len(_cache) >= 32:
        _cache.clear()
    _cache[key] = (time.monotonic(), result)
    return result
