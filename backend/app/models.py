"""Typed schemas shared by our API, data adapter, and bounded AI workflow.

Pydantic rejects malformed data at clear boundaries. Type annotations also
make it easier for beginner developers to see which fields travel where.
"""
from datetime import datetime
from typing import Literal
from pydantic import AwareDatetime, BaseModel, Field


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


class LiigaTeam(BaseModel):
    name: str
    team_id: str | None = None
    goals: int | None = Field(default=None, ge=0)
    logo_url: str | None = None


class LiigaGoalEvent(BaseModel):
    team_side: Literal["home", "away"]
    scorer: str
    period: int | None = None
    game_time_seconds: int | None = None
    has_video: bool = False


class LiigaGame(BaseModel):
    id: int
    season: int
    start: AwareDatetime
    status: Literal["upcoming", "live", "finished", "cancelled"]
    home_team: LiigaTeam
    away_team: LiigaTeam
    venue: str | None = None
    city: str | None = None
    goal_events: list[LiigaGoalEvent] = Field(default_factory=list)


class LiigaDatasetMetadata(BaseModel):
    source: Literal["Liiga Stats API v1"] = "Liiga Stats API v1"
    data_mode: Literal["real"] = "real"
    season: int
    updated_at: datetime
    games_in_dataset: int


class LiigaGamesResponse(LiigaDatasetMetadata):
    count: int
    games: list[LiigaGame]


class LiigaTeamStats(BaseModel):
    team_id: str
    name: str
    matches_played: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    goals_for: int = 0
    goals_against: int = 0
    goal_difference: int = 0
    win_percentage: float | None = None
    form: list[Literal["W", "L", "D"]] = Field(default_factory=list)


class LiigaAnalysisResponse(LiigaDatasetMetadata):
    scope: Literal["regular_season_games_returned_by_provider"] = (
        "regular_season_games_returned_by_provider"
    )
    completed_games: int
    excluded_games: int
    teams: list[LiigaTeamStats]


class LiigaTeamAnalysisResponse(LiigaDatasetMetadata, LiigaTeamStats):
    scope: Literal["regular_season_games_returned_by_provider"] = (
        "regular_season_games_returned_by_provider"
    )
