"""HTTP API for the teammate's reusable Fan Companion (not its Streamlit UI)."""
from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .liiga_api import _dataset, current_season
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


class Receipt(BaseModel):
    id: str
    label: str
    value: str
    source: str


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
    try:
        # LLM clients and fact checking are synchronous: run off the event loop.
        return await asyncio.to_thread(
            companion_response, snapshot, team_id=payload.team_id,
            message=payload.message.strip(),
            history=[item.model_dump() for item in payload.history],
            kind=payload.kind, persona=payload.persona,
            language=payload.language, use_ai=payload.use_ai,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Selected team is not available.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Companion could not verify its response.") from exc
