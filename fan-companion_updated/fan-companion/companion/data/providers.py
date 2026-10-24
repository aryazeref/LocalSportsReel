"""Data providers. Everything downstream only sees the normalised shapes
described in DATA_CONTRACT.md, so switching mock -> real API is one class."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from companion.config import AS_OF, MOCK_DIR


@dataclass
class Snapshot:
    """Everything the companion knows about the league at one moment."""
    source: str
    is_mock: bool
    as_of: str
    teams: dict[str, dict]                  # id -> {id, name, city, roster?}
    games: list[dict]                       # see DATA_CONTRACT.md
    events: dict[str, list[dict]] = field(default_factory=dict)  # game_id -> events

    def name(self, team_id: str) -> str:
        return self.teams[team_id]["name"]

    def roster(self, team_id: str) -> list[dict]:
        roster = self.teams[team_id].get("roster")
        if roster:
            return roster
        # Fall back to players seen in event feeds
        seen: dict[str, int] = {}
        for evs in self.events.values():
            for e in evs:
                if e.get("team") == team_id and e.get("player"):
                    seen[e["player"]] = seen.get(e["player"], 0) + 1
        if not seen:
            return [{"name": f"{self.name(team_id)} skater", "weight": 1.0}]
        return [{"name": n, "weight": float(c)} for n, c in seen.items()]


class MockProvider:
    source_name = "Mock Liiga data"
    is_mock = True

    def __init__(self, path=MOCK_DIR):
        self.path = path
        if not (path / "games.json").exists():
            from companion.data.generate_mock import generate
            generate(path)

    def _load(self, name):
        return json.loads((self.path / name).read_text(encoding="utf-8"))

    def snapshot(self) -> Snapshot:
        meta = self._load("meta.json")
        teams = {t["id"]: t for t in self._load("teams.json")}
        return Snapshot(self.source_name, True, meta.get("as_of", AS_OF), teams,
                        self._load("games.json"), self._load("events.json"))


class LiigaApiProvider:
    """Adapter for the Liiga API provided by Kaleva.

    TODO (once you have the docs + key): set the endpoint paths below and adjust
    the three normalise_* functions to the real field names. Nothing else in the
    app needs to change.
    """
    source_name = "Liiga API"
    is_mock = False

    TEAMS_PATH = "/teams"
    GAMES_PATH = "/games"
    EVENTS_PATH = "/games/{game_id}/events"

    def __init__(self):
        self.base = os.getenv("LIIGA_API_BASE", "").rstrip("/")
        self.key = os.getenv("LIIGA_API_KEY", "")
        self.season = os.getenv("LIIGA_SEASON", "2027")
        if not self.base:
            raise RuntimeError("LIIGA_API_BASE is not set in .env")

    def _get(self, path: str, **params):
        import requests
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        r = requests.get(self.base + path, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        return r.json()

    def snapshot(self) -> Snapshot:
        teams = {t["id"]: t for t in map(normalise_team, self._get(self.TEAMS_PATH))}
        games = [normalise_game(g) for g in self._get(self.GAMES_PATH, season=self.season)]
        events = {}
        for g in games:
            if g["status"] == "final":
                raw = self._get(self.EVENTS_PATH.format(game_id=g["id"]))
                events[g["id"]] = [normalise_event(e, g) for e in raw]
        return Snapshot(self.source_name, False, AS_OF, teams, games, events)


def normalise_team(raw: dict) -> dict:
    # TODO: map real field names
    return {"id": str(raw.get("id") or raw.get("teamId")),
            "name": raw.get("name") or raw.get("teamName"),
            "city": raw.get("city", "")}


def normalise_game(raw: dict) -> dict:
    # TODO: map real field names
    start = str(raw.get("start") or raw.get("date") or "")
    finished = bool(raw.get("ended") or raw.get("finished") or raw.get("status") == "final")
    decided = raw.get("finishedType") or raw.get("decided") or "REG"
    decided = {"ENDED_DURING_REGULAR_GAME_TIME": "REG", "ENDED_DURING_EXTENDED_GAME_TIME": "OT",
               "ENDED_DURING_WINNING_SHOT_COMPETITION": "SO"}.get(decided, decided)
    return {"id": str(raw.get("id")), "round": raw.get("round"), "date": start[:10],
            "time": start[11:16] or "18:30",
            "home": str(raw.get("homeTeamId") or raw.get("home")),
            "away": str(raw.get("awayTeamId") or raw.get("away")),
            "status": "final" if finished else "scheduled",
            "home_goals": raw.get("homeGoals") if finished else None,
            "away_goals": raw.get("awayGoals") if finished else None,
            "decided": decided if finished else None}


def normalise_event(raw: dict, game: dict) -> dict:
    # TODO: map real field names
    return {"game_id": game["id"], "seq": raw.get("seq") or raw.get("id"),
            "type": raw.get("type", "goal"), "period": raw.get("period"),
            "clock": raw.get("clock") or raw.get("gameTime", ""), "team": str(raw.get("teamId", "")),
            "player": raw.get("player") or raw.get("scorer"), "assists": raw.get("assists", []),
            "detail": raw.get("detail", ""), "home_score": raw.get("homeScore"),
            "away_score": raw.get("awayScore")}


def get_provider(kind: str = "mock"):
    return LiigaApiProvider() if kind == "liiga" else MockProvider()
