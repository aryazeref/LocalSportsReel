"""Use the existing Liiga FastAPI snapshot for the teammate's fact-verified companion.

The teammate's Streamlit app remains untouched in fan-companion/. We import
only its reusable Python modules; Streamlit is never started by this backend.

Important: the companion's independent Poisson playoff probabilities are NOT
used here. The /predictions service remains the authoritative modelled forecast.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ..services.liiga_client import SeasonGames

# A hyphenated directory is not a Python package name. Add its absolute folder
# to the module search path and import the original library without copying it.
_COMPANION_ROOT = Path(__file__).resolve().parents[3] / "fan-companion"
if str(_COMPANION_ROOT) not in sys.path:
    sys.path.insert(0, str(_COMPANION_ROOT))

from companion.companion import Companion  # noqa: E402
from companion.config import FORMATS, use_league  # noqa: E402
from companion.data.providers import Snapshot  # noqa: E402
from companion.facts import build_team_facts  # noqa: E402
from companion.llm import OpenAIBackend  # noqa: E402

HELSINKI = ZoneInfo("Europe/Helsinki")
FINISHED_TYPES = {
    "ENDED_DURING_REGULAR_GAME_TIME": "REG",
    "ENDED_DURING_EXTENDED_GAME_TIME": "OT",
    "ENDED_DURING_WINNING_SHOT_COMPETITION": "SO",
}


def build_companion_snapshot(data: SeasonGames) -> Snapshot:
    """Map the existing normalized Liiga data into the companion's input contract.

    Keep full provider team IDs (not similarly-spelled slugs) to avoid
    accidentally attributing another team's matches to the selected club.
    Live games are treated as scheduled, never as completed results.
    """
    teams: dict[str, dict] = {}
    games: list[dict] = []
    events: dict[str, list[dict]] = {}
    for game in data.games:
        if game.status == "cancelled":
            continue
        home_id, away_id = game.home_team.team_id, game.away_team.team_id
        if not home_id or not away_id or home_id == away_id:
            continue
        local = game.start.astimezone(HELSINKI)
        for team_id, team in ((home_id, game.home_team), (away_id, game.away_team)):
            teams.setdefault(team_id, {
                "id": team_id, "name": team.name, "city": game.city if team_id == home_id else "",
            })
        decided = FINISHED_TYPES.get(game.finished_type or "")
        final = (game.status == "finished" and decided is not None
                 and game.home_team.goals is not None and game.away_team.goals is not None
                 and game.home_team.goals != game.away_team.goals)
        key = str(game.id)
        games.append({
            "id": key, "round": None, "date": local.date().isoformat(),
            "time": local.strftime("%H:%M"), "home": home_id, "away": away_id,
            "status": "final" if final else "scheduled",
            "home_goals": game.home_team.goals if final else None,
            "away_goals": game.away_team.goals if final else None,
            "decided": decided if final else None,
        })
        if final:
            # The shared provider currently normalizes goal scorers but not
            # assists/penalties. Do not invent missing event details.
            evs = []
            for index, goal in enumerate(game.goal_events, start=1):
                player = goal.scorer.strip()
                if not player or player == "Unknown scorer":
                    continue
                evs.append({
                    "game_id": key, "seq": index, "type": "goal",
                    "period": "SO" if goal.period == 5 else "OT" if goal.period == 4 else goal.period,
                    "clock": "", "team": home_id if goal.team_side == "home" else away_id,
                    "player": player, "assists": [], "detail": "",
                    "home_score": None, "away_score": None,
                })
            events[key] = evs
    # This date corresponds to the shared cache timestamp, not the host's
    # current wall clock if the Liiga snapshot was served from cache.
    return Snapshot(
        source="Liiga Stats API v1 (shared FastAPI snapshot)", is_mock=False,
        as_of=data.updated_at.astimezone(HELSINKI).date().isoformat(),
        teams=teams, games=games, events=events,
    )


def team_options(snapshot: Snapshot) -> list[dict]:
    return [
        {"id": team_id, "name": snapshot.name(team_id),
         "city": team.get("city", "")}
        for team_id, team in sorted(snapshot.teams.items(), key=lambda x: x[1]["name"].casefold())
    ]


def companion_response(
    snapshot: Snapshot, *, team_id: str, message: str, history: list[dict],
    kind: str, persona: str, language: str, use_ai: bool,
) -> dict:
    """Runs in a worker thread, so a network LLM never blocks the FastAPI event loop."""
    if team_id not in snapshot.teams:
        raise KeyError("Team not found in the selected Liiga season")
    use_league(FORMATS["liiga"])
    # We intentionally do not call the companion's separate simulation. Its
    # methodology differs from the existing evaluated /predictions model.
    facts = build_team_facts(snapshot, team_id, None)
    allowed = os.getenv("COMPANION_ENABLE_LLM", "false").lower() == "true"
    backend = OpenAIBackend() if use_ai and allowed and os.getenv("OPENAI_API_KEY") else None
    agent = Companion(backend=backend, persona=persona, language=language, length="normal")
    if kind == "brief":
        reply = agent.brief(facts)
    elif kind == "podcast":
        reply = agent.podcast(facts, short=True)
    else:
        reply = agent.chat(facts, history, message)
    if not reply.report.ok:
        # Never expose output that fails the companion's own factual checks.
        raise ValueError("Companion output did not pass fact verification")
    receipts = [
        {"id": fid, "label": reply.facts.facts[fid].label,
         "value": reply.facts.facts[fid].display,
         "source": reply.facts.facts[fid].source}
        for fid in reply.report.cited_ids if fid in reply.facts.facts
    ]
    return {
        "kind": kind, "text": reply.text, "engine": reply.engine,
        "verification_status": reply.status, "numbers_checked": reply.report.numbers_checked,
        "receipts": receipts, "team_id": team_id, "team_name": snapshot.name(team_id),
        "data_source": snapshot.source, "data_as_of": snapshot.as_of,
        "is_mock": snapshot.is_mock,
        "model_note": ("Companion answers use verified descriptive match facts. "
                       "Separate experimental probabilities and points scenarios are available on /predictions; "
                       "this companion does not claim exact playoff probabilities."),
    }
