"""HTTP response contracts for forecasts and bounded points scenarios."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ForecastTeam(BaseModel):
    team_id: str
    name: str


class OutcomeProbabilities(BaseModel):
    home_regulation: float = Field(ge=0, le=1)
    home_overtime: float = Field(ge=0, le=1)
    away_overtime: float = Field(ge=0, le=1)
    away_regulation: float = Field(ge=0, le=1)
    home_win: float = Field(ge=0, le=1)
    away_win: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def consistent(self):
        outcomes = self.home_regulation + self.home_overtime + self.away_overtime + self.away_regulation
        if abs(outcomes - 1) > 1e-7 or abs(self.home_win - self.home_regulation - self.home_overtime) > 1e-7 or abs(self.away_win - self.away_regulation - self.away_overtime) > 1e-7:
            raise ValueError("Forecast probabilities must sum to one and agree with final winners")
        return self


class FeatureEvidence(BaseModel):
    names: list[str]
    values: list[float]
    home_history: int = Field(ge=0)
    away_history: int = Field(ge=0)
    cold_start: bool
    history_cutoff: str | None


class ForecastFixture(BaseModel):
    game_id: int
    season: int
    start: datetime
    home_team: ForecastTeam
    away_team: ForecastTeam
    probabilities: OutcomeProbabilities
    features: FeatureEvidence
    warnings: list[str]


class ForecastModel(BaseModel):
    name: str
    display_name: str
    model_version: str
    feature_set: str
    window: int
    training_cutoff: str
    training_matches: int
    trained_at: str
    status: str = "experimental"
    training_seasons: list[int] = Field(default_factory=list)
    history_seasons: int = 0
    evaluation_test_seasons: list[int] = Field(default_factory=list)


class PredictionsResponse(BaseModel):
    season: int
    source: str
    generated_at: datetime
    data_updated_at: datetime
    model: ForecastModel
    evaluation: dict[str, Any]
    warnings: list[str]
    fixtures: list[ForecastFixture]


class PointsProjection(BaseModel):
    team_id: str
    name: str
    current_points: int
    expected_points: float
    expected_rank: float
    top_n_lower: float = Field(ge=0, le=1)
    top_n_upper: float = Field(ge=0, le=1)


class ScenarioProjection(PointsProjection):
    delta_points: float
    delta_rank: float
    delta_top_n_lower: float
    delta_top_n_upper: float


class ForcedScenario(BaseModel):
    outcome: str
    home_points: int
    away_points: int
    teams: list[ScenarioProjection]


class ImpactResponse(BaseModel):
    season: int
    game_id: int
    generated_at: datetime
    standings_updated_at: datetime
    standings_basis: Literal['official', 'completed_results_snapshot'] = 'official'
    standings_as_of: datetime | None = None
    simulated_started_games: int = Field(default=0, ge=0)
    model_name: str
    model_version: str
    forecast_cutoff: str
    scope: str = "regular_season_points"
    warnings: list[str]
    simulations: int
    seed: int
    top_n: int
    remaining_fixtures: int
    max_mc_margin_95: float
    baseline: list[PointsProjection]
    scenarios: list[ForcedScenario]
    limitations: list[str]
