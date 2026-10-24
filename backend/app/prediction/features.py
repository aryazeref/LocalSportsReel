"""As-of paper-inspired match profiles, with conservative day-level cutoffs.

Ranks are a defined recent-form context, not historical official standings:
rank known clubs by recent points per game, then regulation goal difference
and goals scored. Ties receive the same midrank. All values use earlier days.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

import numpy as np

from .domain import HELSINKI, Match, OUTCOME_POINTS

MIN_HISTORY = 6
FEATURE_SETS = ("total", "homeaway")


@dataclass(frozen=True)
class Performance:
    goals_for: int
    goals_against: int
    points: int
    venue: str


def feature_names(feature_set: str = "total") -> list[str]:
    if feature_set not in FEATURE_SETS:
        raise ValueError("Unknown feature set")
    contexts = ("total",) if feature_set == "total" else ("total", "home", "away")
    return [
        f"{side}_{context}_{quantity}"
        for context in contexts for side in ("home", "away")
        for quantity in ("goals_for", "goals_against", "form_rank")
    ]


def validated_history(matches: Iterable[Match]) -> list[Match]:
    """Reject duplicated identities; omit results with unusable labels."""
    result, seen = [], set()
    for match in sorted(matches, key=lambda game: (game.start, game.season, game.game_id)):
        if match.start.tzinfo is None:
            raise ValueError("Prediction timestamps must include a timezone")
        if match.key in seen:
            raise ValueError("Duplicate season/game identity in prediction history")
        seen.add(match.key)
        if match.outcome is not None:
            result.append(match)
    return result


class FeatureState:
    def __init__(self):
        self.histories: dict[str, list[Performance]] = defaultdict(list)
        self.season_teams: dict[int, set[str]] = defaultdict(set)
        self.outcome_counts = np.array([3.0, 1.0, 1.0, 3.0])
        self.ratings: dict[str, float] = {}
        self.last_season: int | None = None
        self.goal_sum = 0
        self.games = 0
        self.latest_day: date | None = None

    @property
    def goal_prior(self) -> float:
        return self.goal_sum / (2 * self.games) if self.games else 2.5

    @property
    def prior(self) -> np.ndarray:
        return self.outcome_counts / self.outcome_counts.sum()

    def elo_probability(self, fixture: Match) -> np.ndarray:
        home = self.ratings.get(fixture.home_id, 1500.0)
        away = self.ratings.get(fixture.away_id, 1500.0)
        if self.last_season is not None and fixture.season != self.last_season:
            home, away = 1500 + 0.75 * (home - 1500), 1500 + 0.75 * (away - 1500)
        home_win = 1 / (1 + 10 ** ((away - home - 60) / 400))
        tie_rate = float(self.prior[1] + self.prior[2])
        return np.array([
            (1 - tie_rate) * home_win, tie_rate * home_win,
            tie_rate * (1 - home_win), (1 - tie_rate) * (1 - home_win),
        ])

    def add(self, match: Match) -> None:
        outcome = match.outcome
        if outcome is None:
            return
        if self.latest_day is not None and match.day < self.latest_day:
            raise ValueError("Feature state must be updated chronologically")
        if self.last_season is not None and match.season != self.last_season:
            self.ratings = {team: 1500 + 0.75 * (rating - 1500) for team, rating in self.ratings.items()}
        self.last_season = match.season
        p_home = float(self.elo_probability(match)[:2].sum())
        delta = 20 * ((1 if outcome < 2 else 0) - p_home)
        self.ratings[match.home_id] = self.ratings.get(match.home_id, 1500.0) + delta
        self.ratings[match.away_id] = self.ratings.get(match.away_id, 1500.0) - delta
        home_points, away_points = OUTCOME_POINTS[outcome]
        self.histories[match.home_id].append(Performance(
            match.home_regulation_goals, match.away_regulation_goals, home_points, "home",
        ))
        self.histories[match.away_id].append(Performance(
            match.away_regulation_goals, match.home_regulation_goals, away_points, "away",
        ))
        self.season_teams[match.season].update((match.home_id, match.away_id))
        self.outcome_counts[outcome] += 1
        self.goal_sum += match.home_regulation_goals + match.away_regulation_goals
        self.games += 1
        self.latest_day = match.day

    def _recent(self, team: str, window: int, context: str) -> list[Performance]:
        history = self.histories.get(team, ())
        if context != "total":
            history = [performance for performance in history if performance.venue == context]
        return list(history[-window:])

    def _summary(self, team: str, window: int, context: str) -> tuple[float, float, float]:
        records = self._recent(team, window, context)
        missing = max(0, MIN_HISTORY - len(records))
        denominator = len(records) + missing
        gf = (sum(row.goals_for for row in records) + missing * self.goal_prior) / denominator
        ga = (sum(row.goals_against for row in records) + missing * self.goal_prior) / denominator
        ppg = (sum(row.points for row in records) + missing * 1.5) / denominator
        return gf, ga, ppg

    def profile(self, fixture: Match, window: int = 12, feature_set: str = "total") -> dict:
        if window < MIN_HISTORY:
            raise ValueError("Feature window must be at least six")
        if feature_set not in FEATURE_SETS:
            raise ValueError("Unknown feature set")
        if self.latest_day is not None and self.latest_day >= fixture.day:
            raise ValueError("Features may only use results from earlier days")
        cohort = set(self.season_teams.get(fixture.season, ())) | {fixture.home_id, fixture.away_id}
        contexts = ("total",) if feature_set == "total" else ("total", "home", "away")
        vector = []
        for context in contexts:
            context_window = window if context == "total" else max(1, window // 2)
            summaries = {team: self._summary(team, context_window, context) for team in cohort}
            order = sorted(cohort, key=lambda team: (
                -summaries[team][2], -(summaries[team][0] - summaries[team][1]), -summaries[team][0], team,
            ))
            ranks: dict[str, float] = {}
            # Exact statistical ties receive a midrank; team ID never breaks a tie.
            for team in order:
                own = summaries[team]
                score = (own[2], own[0] - own[1], own[0])
                better = sum((value[2], value[0] - value[1], value[0]) > score for value in summaries.values())
                equal = sum((value[2], value[0] - value[1], value[0]) == score for value in summaries.values())
                rank = 1 + better + (equal - 1) / 2
                ranks[team] = (len(cohort) - rank) / (len(cohort) - 1) if len(cohort) >= 4 else 0.5
            for team in (fixture.home_id, fixture.away_id):
                gf, ga, _ = summaries[team]
                rank = ranks[team] if self.histories.get(team) else 0.5
                vector.extend((gf, ga, rank))
        home_history = len(self.histories.get(fixture.home_id, ()))
        away_history = len(self.histories.get(fixture.away_id, ()))
        return {
            "features": vector, "feature_names": feature_names(feature_set),
            "home_history": home_history, "away_history": away_history,
            "cold_start": min(home_history, away_history) < MIN_HISTORY,
            "history_cutoff": self.latest_day.isoformat() if self.latest_day else None,
        }


def effective_day(fixture: Match, cutoff: datetime | None = None) -> date:
    if cutoff is not None and cutoff.tzinfo is None:
        raise ValueError("Prediction cutoff must include a timezone")
    return min(fixture.day, cutoff.astimezone(HELSINKI).date()) if cutoff is not None else fixture.day


def build_state(history: Iterable[Match], before: date) -> FeatureState:
    state = FeatureState()
    for game in validated_history(history):
        if game.day < before:
            state.add(game)
    return state


def build_feature_rows(matches: Iterable[Match], window: int = 12, feature_set: str = "total") -> list[dict]:
    """Build each calendar day's features before adding any results that day."""
    games = validated_history(matches)
    state = FeatureState()
    result, index = [], 0
    while index < len(games):
        end = index + 1
        while end < len(games) and games[end].day == games[index].day:
            end += 1
        batch = games[index:end]
        for game in batch:
            profile = state.profile(game, window, feature_set)
            result.append({
                **profile, "match": game, "label": game.outcome,
                "prior": state.prior.copy(), "elo": state.elo_probability(game),
            })
        for game in batch:
            state.add(game)
        index = end
    return result
