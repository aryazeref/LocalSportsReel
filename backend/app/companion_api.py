"""HTTP API for the teammate's reusable Fan Companion (not its Streamlit UI)."""
from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .liiga_api import _dataset, current_season
from .prediction.service import PredictionUnavailable, get_predictions, get_impact
from .services.companion_bridge import build_companion_snapshot, companion_response, team_options, local_action_reply
from companion.agent import route, follow_ups
from companion.facts import build_team_facts, find_teams, add_team_facts
from companion.config import FORMATS, use_league
from companion.stats import next_game
from .services.companion_ai import companion_ai_status

router = APIRouter(prefix="/api/companion", tags=["Fan companion"])


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1200)


class CompanionRequest(BaseModel):
    team_id: str = Field(min_length=1, max_length=100)
    season: int | None = Field(default=None, ge=2000, le=2100)
    kind: Literal["chat", "brief", "podcast"] = "chat"
    message: str = Field(default="", max_length=1200)
    persona: Literal["buddy", "analyst", "stats"] = "buddy"
    language: Literal["English", "Finnish"] = "English"
    user_name: str = Field(default="", max_length=40)
    answer_length: Literal["short", "normal", "long"] = "normal"
    fan_since: str = Field(default="", max_length=4)
    favourite_player: str = Field(default="", max_length=80)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)
    use_ai: bool = False
    # Explicit opt-in prevents preparing the prediction model for every chat.
    include_forecast: bool = False
    include_impact: bool = False


class Receipt(BaseModel):
    id: str
    label: str
    value: str
    source: str


class CompanionForecast(BaseModel):
    game_id: int
    season: int
    home_team: str
    away_team: str
    home_win: float
    away_win: float
    model: str
    warnings: list[str]


class CompanionImpactOutcome(BaseModel):
    outcome: str
    expected_points: float
    delta_points: float
    expected_rank: float


class CompanionImpact(BaseModel):
    game_id: int
    model: str
    scope: str
    top_n: int
    outcomes: list[CompanionImpactOutcome]
    limitations: list[str]
    warnings: list[str]


class Suggestion(BaseModel):
    label: str
    question: str


class LocalAction(BaseModel):
    tool: Literal["set_alert", "save_prediction"]
    team_id: str
    season: int
    game_id: str | None = None
    home_team: str | None = None
    away_team: str | None = None
    home_goals: int | None = None
    away_goals: int | None = None
    threshold: int | None = None


class CompanionResponse(BaseModel):
    kind: Literal["chat", "brief", "podcast"]
    text: str
    engine: str
    generation_mode: Literal["ai", "offline", "fallback"]
    mode_message: str
    verification_status: Literal["verified", "corrected", "redacted"]
    numbers_checked: int
    receipts: list[Receipt]
    team_id: str
    team_name: str
    data_source: str
    data_as_of: str
    is_mock: bool
    forecast: CompanionForecast | None = None
    forecast_warning: str | None = None
    impact: CompanionImpact | None = None
    impact_warning: str | None = None
    model_note: str
    suggestions: list[Suggestion] = Field(default_factory=list)
    action: LocalAction | None = None


@router.get("/status")
async def companion_status():
    """Reveal AI readiness without returning private API keys."""
    return companion_ai_status()


@router.get("/teams")
async def get_companion_teams(
    season: int | None = Query(default=None, ge=2000, le=2100),
):
    """Team choices come from the same backend Liiga snapshot as /liiga."""
    chosen = season or current_season()
    data = await _dataset(chosen)
    snapshot = build_companion_snapshot(data)
    initial = follow_ups(None, top_label="Top-four race")
    return {
        "season": chosen, "source": snapshot.source, "as_of": snapshot.as_of,
        "data_mode": "real", "teams": team_options(snapshot),
        "suggestions": [{"label": key, "question": value} for key, value in initial.items()],
    }


@router.post("/respond", response_model=CompanionResponse)
async def respond(payload: CompanionRequest):
    if payload.kind == "chat" and not payload.message.strip():
        raise HTTPException(status_code=422, detail="Enter a question to send.")
    chosen = payload.season or current_season()
    data = await _dataset(chosen)
    snapshot = build_companion_snapshot(data)
    if not snapshot.teams:
        raise HTTPException(status_code=503, detail="No usable Liiga teams are available.")
    if payload.team_id not in snapshot.teams:
        raise HTTPException(status_code=404, detail="Selected team is not available.")

    # The teammate's routing is deterministic: no extra model request or
    # Gemini quota used to classify an action.
    use_league(FORMATS["liiga"])
    named = find_teams(snapshot, payload.message, exclude=payload.team_id) if payload.kind == "chat" else []
    opponent_name = snapshot.name(named[0]) if named else ""
    options = follow_ups(payload.message if payload.kind == "chat" else None,
                         opponent_name, "Top-four race")
    suggestions = [{"label": label, "question": question} for label, question in options.items()]
    choice = (route(payload.message, None, team=snapshot.name(payload.team_id),
                    opponent=opponent_name) if payload.kind == "chat" else {"tool": "answer"})
    if choice["tool"] in ("save_prediction", "set_alert"):
        action = None
        explanation = ("You can save an alert preference in this browser. "
                       "It will not send notifications or run in the background.")
        if choice["tool"] == "set_alert":
            threshold = choice.get("threshold")
            if threshold is not None and (not isinstance(threshold, int) or not 0 <= threshold <= 100):
                raise HTTPException(status_code=422, detail="An alert threshold must be a percentage.")
            action = {
                "tool": "set_alert", "team_id": payload.team_id,
                "season": chosen, "threshold": threshold,
            }
        else:
            goals = (choice.get("home"), choice.get("away"))
            if any(not isinstance(score, int) or not 0 <= score <= 20 for score in goals):
                raise HTTPException(status_code=422, detail="Predicted scores must be valid goal counts.")
            next_fixture = next_game(snapshot, payload.team_id)
            if next_fixture:
                action = {
                    "tool": "save_prediction", "team_id": payload.team_id,
                    "season": chosen, "game_id": str(next_fixture["id"]),
                    "home_team": snapshot.name(next_fixture["home"]),
                    "away_team": snapshot.name(next_fixture["away"]),
                    "home_goals": goals[0], "away_goals": goals[1],
                }
                explanation = ("Your score prediction is ready to save privately in this browser. "
                               "It will not be published or checked automatically.")
            else:
                explanation = "There is no upcoming fixture available for saving a score prediction."
        response = local_action_reply(
            snapshot, team_id=payload.team_id, tool=choice["tool"],
            action=action, explanation=explanation,
        )
        response["suggestions"] = suggestions
        return response

    # The teammate's comparison facts are added BEFORE generation and
    # verification, so claims about named rival teams require valid receipts.
    facts = build_team_facts(snapshot, payload.team_id, None, profile={
        "fan_since": payload.fan_since, "fav_player": payload.favourite_player,
    })
    for other in named:
        add_team_facts(facts, snapshot, payload.team_id, other, None)

    if choice["tool"] == "podcast":
        # A direct "make a podcast" chat request uses the existing verified
        # podcast generator rather than an ordinary text-chat answer.
        routed_kind = "podcast"
    else:
        routed_kind = payload.kind

    # Use the authoritative feature/API_integration predictor only.
    # No companion-side probability or playoff simulation runs here.
    fixture = None
    model_name = None
    forecast_warning = None
    impact_result = None
    impact_warning = None
    prediction = None
    if payload.include_forecast or payload.include_impact:
        if chosen != current_season():
            forecast_warning = "Forecasts are available for the current season only."
        else:
            try:
                prediction = await get_predictions(limit=1, team_id=payload.team_id)
                fixture = prediction.fixtures[0] if prediction.fixtures else None
                model_name = prediction.model.display_name
                if fixture is None:
                    forecast_warning = "No upcoming match forecast is available for this team."
            except PredictionUnavailable:
                forecast_warning = "Prediction service is currently unavailable; no forecast was invented."
    if payload.include_impact:
        if fixture is None or prediction is None:
            impact_warning = "A matching upcoming forecast is required for scenario analysis."
        else:
            try:
                impact_result = await get_impact(
                    fixture.game_id, top_n=4, simulations=4000,
                    expected_model_version=prediction.model.model_version,
                )
            except PredictionUnavailable:
                impact_warning = "League-impact simulation is currently unavailable; no scenario was invented."
    try:
        # LLM clients and fact checking are synchronous: run off the event loop.
        answer = await asyncio.to_thread(
            companion_response, snapshot, team_id=payload.team_id,
            message=payload.message.strip(),
            history=[item.model_dump() for item in payload.history],
            kind=routed_kind, persona=payload.persona,
            language=payload.language, use_ai=payload.use_ai,
            user_name=payload.user_name.strip(), length=payload.answer_length,
            prepared_facts=facts,
            forecast=fixture, forecast_model=model_name,
            forecast_warning=forecast_warning,
            impact=impact_result, impact_warning=impact_warning,
        )
        answer["suggestions"] = suggestions
        return answer
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Selected team is not available.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Companion could not verify its response.") from exc
