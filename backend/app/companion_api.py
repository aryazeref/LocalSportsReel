"""HTTP API for the teammate's reusable Fan Companion (not its Streamlit UI)."""
from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .liiga_api import _dataset, current_season
from .prediction.service import PredictionUnavailable, get_predictions, get_impact
from .services.companion_bridge import build_companion_snapshot, companion_response, team_options

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


class CompanionResponse(BaseModel):
    kind: Literal["chat", "brief", "podcast"]
    text: str
    engine: str
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


@router.get("/teams")
async def get_companion_teams(
    season: int | None = Query(default=None, ge=2000, le=2100),
):
    """Team choices come from the same backend Liiga snapshot as /liiga."""
    chosen = season or current_season()
    data = await _dataset(chosen)
    snapshot = build_companion_snapshot(data)
    return {
        "season": chosen, "source": snapshot.source, "as_of": snapshot.as_of,
        "data_mode": "real", "teams": team_options(snapshot),
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
        return await asyncio.to_thread(
            companion_response, snapshot, team_id=payload.team_id,
            message=payload.message.strip(),
            history=[item.model_dump() for item in payload.history],
            kind=payload.kind, persona=payload.persona,
            language=payload.language, use_ai=payload.use_ai,
            forecast=fixture, forecast_model=model_name,
            forecast_warning=forecast_warning,
            impact=impact_result, impact_warning=impact_warning,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Selected team is not available.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Companion could not verify its response.") from exc
