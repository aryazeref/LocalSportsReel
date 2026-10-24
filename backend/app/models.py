"""Typed schemas shared by our API, data adapter, and bounded AI workflow.

Pydantic rejects malformed data at clear boundaries. Type annotations also
make it easier for beginner developers to see which fields travel where.
"""
from typing import Literal
from pydantic import BaseModel, Field


class Fact(BaseModel):
    id: str
    text: str
    source_id: str


class Moment(BaseModel):
    id: str
    city: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    happened_at: str
    sport: str
    league: str
    team: str
    athlete: str
    title: str
    moment_type: str
    excitement: float = Field(ge=0, le=1)
    score: str
    facts: list[Fact]
    source_id: str
    source_label: str
    demo: bool = True
    video_url: str | None = None
    video_authorized: bool = False


class FeedMoment(Moment):
    distance_km: float
    relevance_score: float


class FeedResponse(BaseModel):
    selected_city: str
    radius_km: int
    total: int
    demo_data: bool
    moments: list[FeedMoment]


class Story(BaseModel):
    moment_id: str
    headline: str
    narration: str
    evidence: list[Fact]
    mode: Literal["template", "llm_draft"]
    publication_status: Literal["demo_only", "review_required"]
    disclaimer: str


class DraftText(BaseModel):
    """Strict structure requested from the optional language model."""
    headline: str
    narration: str
    used_fact_ids: list[str]
