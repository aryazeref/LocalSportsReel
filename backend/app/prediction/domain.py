"""Shared prediction data, independent of provider JSON and HTTP routes."""

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

HELSINKI = ZoneInfo("Europe/Helsinki")
OUTCOMES = ("home_regulation", "home_overtime", "away_overtime", "away_regulation")
OUTCOME_POINTS = ((3, 0), (2, 1), (1, 2), (0, 3))
REGULATION = "ENDED_DURING_REGULAR_GAME_TIME"
EXTRA_TIME = {"ENDED_DURING_EXTENDED_GAME_TIME", "ENDED_DURING_WINNING_SHOT_COMPETITION"}


def canonical_team_id(value: str) -> str:
    """Numeric provider identity; preserve identity across display-slug changes."""
    return value.split(":", 1)[0]


@dataclass(frozen=True)
class Match:
    season: int
    game_id: int
    start: datetime
    home_id: str
    away_id: str
    home_name: str
    away_name: str
    status: str
    home_goals: int | None = None
    away_goals: int | None = None
    home_regulation_goals: int | None = None
    away_regulation_goals: int | None = None
    finish_type: str | None = None
    home_expected_goals: float | None = None
    away_expected_goals: float | None = None

    @property
    def key(self) -> tuple[int, int]:
        return self.season, self.game_id

    @property
    def day(self):
        return self.start.astimezone(HELSINKI).date()

    @property
    def outcome(self) -> int | None:
        """Four points-relevant labels; unknown/inconsistent results are unusable."""
        values = (self.home_goals, self.away_goals, self.home_regulation_goals, self.away_regulation_goals)
        if (
            self.status != "finished" or not self.home_id or not self.away_id
            or self.home_id == self.away_id
            or any(type(value) is not int or value < 0 for value in values)
            or self.home_goals == self.away_goals
        ):
            return None
        if self.finish_type == REGULATION:
            if (self.home_goals, self.away_goals) != (self.home_regulation_goals, self.away_regulation_goals):
                return None
            return 0 if self.home_goals > self.away_goals else 3
        if self.finish_type in EXTRA_TIME:
            if self.home_regulation_goals != self.away_regulation_goals:
                return None
            tied = self.home_regulation_goals
            if (self.home_goals, self.away_goals) not in ((tied + 1, tied), (tied, tied + 1)):
                return None
            return 1 if self.home_goals > self.away_goals else 2
        return None


@dataclass(frozen=True)
class Standing:
    team_id: str
    name: str
    points: int
    played: int
    regulation_wins: int = 0
    overtime_wins: int = 0
    overtime_losses: int = 0
    regulation_losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
