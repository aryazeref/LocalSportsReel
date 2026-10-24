"""Regular-season points scenarios, without assuming unverified tie-break rules.

The caller supplies the official current points and one fixed four-outcome
probability vector for each remaining fixture. These are pre-match forecasts:
future results do not update team strength inside a simulation.
"""

from __future__ import annotations

import math
from datetime import datetime

import numpy as np

from .domain import Match, OUTCOME_POINTS, OUTCOMES, Standing


def _validate_inputs(
    standings: list[Standing],
    fixtures: list[Match],
    probabilities: list[list[float]],
    selected_match_key: tuple[int, int],
    simulations: int,
    top_n: int,
    seed: int,
) -> tuple[np.ndarray, int, dict[str, int]]:
    if type(simulations) is not int or simulations < 1:
        raise ValueError("simulations must be a positive integer")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if not standings or any(not isinstance(team, Standing) for team in standings):
        raise ValueError("standings must contain Standing records")
    if type(top_n) is not int or not 1 <= top_n <= len(standings):
        raise ValueError("top_n must be between 1 and the number of teams")
    team_indices: dict[str, int] = {}
    for index, team in enumerate(standings):
        if not isinstance(team.team_id, str) or not team.team_id.strip() or team.team_id in team_indices:
            raise ValueError("standings must have unique, nonempty team IDs")
        if type(team.points) is not int or team.points < 0:
            raise ValueError("current points must be nonnegative integers")
        if type(team.played) is not int or team.played < 0:
            raise ValueError("played games must be nonnegative integers")
        team_indices[team.team_id] = index

    if not fixtures or any(not isinstance(game, Match) for game in fixtures):
        raise ValueError("fixtures must contain remaining Match records")
    keys: set[tuple[int, int]] = set()
    seasons: set[int] = set()
    selected_index = None
    for index, game in enumerate(fixtures):
        if type(game.season) is not int or game.season < 1 or type(game.game_id) is not int or game.game_id < 0:
            raise ValueError("fixtures must have integer season/game IDs")
        if game.key in keys:
            raise ValueError("remaining fixtures contain a duplicate season/game ID")
        keys.add(game.key)
        seasons.add(game.season)
        if game.status != "upcoming":
            raise ValueError("only upcoming fixtures can be simulated")
        if not isinstance(game.home_id, str) or not isinstance(game.away_id, str):
            raise ValueError("fixture team IDs must be strings")
        if game.home_id == game.away_id:
            raise ValueError("a fixture must contain two distinct teams")
        if game.home_id not in team_indices or game.away_id not in team_indices:
            raise ValueError("all fixture teams must exist in the standings")
        if not isinstance(game.start, datetime) or game.start.tzinfo is None or game.start.utcoffset() is None:
            raise ValueError("fixture start times must include a timezone")
        if game.key == selected_match_key:
            selected_index = index
    if len(seasons) != 1:
        raise ValueError("a league simulation must use fixtures from one season")
    if selected_index is None:
        raise ValueError("selected match is not among the remaining fixtures")

    try:
        raw_probabilities = np.asarray(probabilities)
        if not (
            np.issubdtype(raw_probabilities.dtype, np.integer)
            or np.issubdtype(raw_probabilities.dtype, np.floating)
        ):
            raise ValueError("probabilities must be numeric")
        values = raw_probabilities.astype(float)
    except (TypeError, ValueError) as error:
        raise ValueError("probabilities must be a rectangular numeric matrix") from error
    if values.shape != (len(fixtures), len(OUTCOMES)):
        raise ValueError("one four-outcome probability vector is required for every fixture")
    if not np.isfinite(values).all() or (values < 0).any() or (values > 1).any():
        raise ValueError("probabilities must be finite values between 0 and 1")
    sums = values.sum(axis=1)
    if not np.allclose(sums, 1.0, rtol=0.0, atol=1e-8):
        raise ValueError("each fixture's probabilities must sum to 1")
    # Only correct harmless floating-point summation drift, not malformed input.
    values /= sums[:, None]
    return values, selected_index, team_indices


def _summarize(points: np.ndarray, standings: list[Standing], top_n: int) -> list[dict]:
    """Bound ranks using points alone, leaving all tied-point ordering unresolved."""
    opponents = points[:, None, :]
    own_points = points[:, :, None]
    best_rank = 1 + (opponents > own_points).sum(axis=2)
    worst_rank = (opponents >= own_points).sum(axis=2)
    mean_points = points.mean(axis=0)
    mean_midrank = ((best_rank + worst_rank) / 2).mean(axis=0)
    lower = (worst_rank <= top_n).mean(axis=0)
    upper = (best_rank <= top_n).mean(axis=0)
    return [
        {
            "team_id": team.team_id,
            "name": team.name,
            "current_points": team.points,
            "expected_points": float(mean_points[index]),
            "expected_rank": float(mean_midrank[index]),
            "top_n_lower": float(lower[index]),
            "top_n_upper": float(upper[index]),
        }
        for index, team in enumerate(standings)
    ]


def simulate_scenarios(
    standings: list[Standing],
    fixtures: list[Match],
    probabilities: list[list[float]],
    *,
    selected_match_key: tuple[int, int],
    simulations: int = 4000,
    top_n: int = 4,
    seed: int = 2026,
) -> dict:
    """Compare a baseline points forecast with all four selected-match outcomes.

    Other match outcomes share the exact same random draws across scenarios.
    The selected fixture's sampled awards are replaced, never added a second
    time. ``delta_rank`` is scenario minus baseline, so a negative value is an
    improvement. Top-N probabilities are bounds over unresolved tied points,
    not playoff qualification probabilities. ``expected_rank`` averages the
    midpoints of each simulation's best/worst points-based ranks.

    ``max_mc_margin_95`` is the worst-case approximate 95% Monte Carlo sampling
    margin for a single marginal probability. It excludes model/data uncertainty
    and must not be interpreted as a margin for a scenario difference.
    """
    values, selected_index, team_indices = _validate_inputs(
        standings, fixtures, probabilities, selected_match_key, simulations, top_n, seed,
    )
    initial = np.array([team.points for team in standings], dtype=np.int64)
    points = np.broadcast_to(initial, (simulations, len(standings))).copy()
    awards = np.array(OUTCOME_POINTS, dtype=np.int64)
    rng = np.random.default_rng(seed)
    selected_awards = None
    for index, game in enumerate(fixtures):
        cumulative = values[index].cumsum()
        cumulative[-1] = 1.0
        outcomes = np.searchsorted(cumulative, rng.random(simulations), side="right")
        sampled_awards = awards[outcomes]
        points[:, team_indices[game.home_id]] += sampled_awards[:, 0]
        points[:, team_indices[game.away_id]] += sampled_awards[:, 1]
        if index == selected_index:
            selected_awards = sampled_awards

    baseline = _summarize(points, standings, top_n)
    selected = fixtures[selected_index]
    home_index, away_index = team_indices[selected.home_id], team_indices[selected.away_id]
    # The fixture is validated as present, so its sampled points were recorded.
    assert selected_awards is not None
    scenarios = []
    for outcome, (home_points, away_points) in zip(OUTCOMES, OUTCOME_POINTS):
        forced_points = points.copy()
        forced_points[:, home_index] += home_points - selected_awards[:, 0]
        forced_points[:, away_index] += away_points - selected_awards[:, 1]
        teams = _summarize(forced_points, standings, top_n)
        for team, original in zip(teams, baseline):
            for field in ("points", "rank"):
                team[f"delta_{field}"] = team[f"expected_{field}"] - original[f"expected_{field}"]
            for bound in ("lower", "upper"):
                key = f"top_n_{bound}"
                team[f"delta_{key}"] = team[key] - original[key]
        scenarios.append({
            "outcome": outcome,
            "home_points": home_points,
            "away_points": away_points,
            "teams": teams,
        })
    return {
        "simulations": simulations,
        "seed": seed,
        "top_n": top_n,
        "remaining_fixtures": len(fixtures),
        "max_mc_margin_95": 1.96 * 0.5 / math.sqrt(simulations),
        "baseline": baseline,
        "scenarios": scenarios,
        "limitations": [
            "Ranks use points only. Tied-point ordering remains unresolved; top-N values are lower/upper bounds.",
            "Top-N points finishes are not official qualification or championship probabilities.",
            "Future fixture probabilities are fixed at the forecast cutoff; simulated results do not update team strength.",
            "Fixture outcomes are sampled independently conditional on those fixed probabilities.",
            "Monte Carlo sampling margins exclude uncertainty in the model, data, and competition rules.",
        ],
    }
