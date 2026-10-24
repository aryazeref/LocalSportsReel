"""League points and tied-rank scenario regressions, without external data."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.prediction.domain import Match, OUTCOME_POINTS, OUTCOMES, Standing
from app.prediction.simulation import simulate_scenarios


def fixture(game_id=1, home="a", away="b", *, season=2027, status="upcoming"):
    return Match(
        season=season, game_id=game_id, start=datetime(2026, 11, 1, 16, tzinfo=timezone.utc),
        home_id=home, away_id=away, home_name=home.upper(), away_name=away.upper(), status=status,
    )


def teams(*points):
    return [Standing(chr(97 + index), chr(65 + index), value, 10) for index, value in enumerate(points)]


def by_id(rows):
    return {row["team_id"]: row for row in rows}


def simulate(standings=None, fixtures=None, probabilities=None, **kwargs):
    return simulate_scenarios(
        standings if standings is not None else teams(0, 0),
        fixtures if fixtures is not None else [fixture()],
        probabilities if probabilities is not None else [[0.4, 0.1, 0.15, 0.35]],
        selected_match_key=kwargs.pop("selected_match_key", (2027, 1)),
        simulations=kwargs.pop("simulations", 100), top_n=kwargs.pop("top_n", 1),
        **kwargs,
    )


def test_all_forced_outcomes_replace_selected_points_exactly_once():
    result = simulate(teams(10, 12), probabilities=[[1, 0, 0, 0]])
    assert by_id(result["baseline"])["a"]["expected_points"] == 13
    assert by_id(result["baseline"])["b"]["expected_points"] == 12
    assert [scenario["outcome"] for scenario in result["scenarios"]] == list(OUTCOMES)
    for scenario, (home, away) in zip(result["scenarios"], OUTCOME_POINTS):
        rows = by_id(scenario["teams"])
        assert rows["a"]["expected_points"] == 10 + home
        assert rows["b"]["expected_points"] == 12 + away
        assert rows["a"]["delta_points"] == home - 3
        assert rows["b"]["delta_points"] == away
        assert sum(row["expected_points"] for row in rows.values()) == 25


def test_official_base_points_and_other_remaining_fixtures_are_preserved():
    result = simulate(
        teams(10, 12, 9), [fixture(), fixture(2, "a", "c")],
        [[1, 0, 0, 0], [0, 0, 0, 1]],
    )
    baseline = by_id(result["baseline"])
    assert [baseline[team]["expected_points"] for team in ["a", "b", "c"]] == [13, 12, 12]
    for scenario in result["scenarios"]:
        rows = by_id(scenario["teams"])
        assert rows["c"]["expected_points"] == 12
        assert rows["c"]["delta_points"] == 0
        assert sum(row["expected_points"] for row in rows.values()) == 37
    assert result["remaining_fixtures"] == 2


def test_tied_points_produce_midrank_and_probability_bounds():
    result = simulate(teams(0, 0, 3), probabilities=[[1, 0, 0, 0]])
    baseline = by_id(result["baseline"])
    for team in ["a", "c"]:
        assert baseline[team]["expected_rank"] == 1.5
        assert baseline[team]["top_n_lower"] == 0
        assert baseline[team]["top_n_upper"] == 1
    assert baseline["b"]["expected_rank"] == 3
    assert baseline["b"]["top_n_lower"] == baseline["b"]["top_n_upper"] == 0
    top_two = simulate(teams(0, 0, 3), probabilities=[[1, 0, 0, 0]], top_n=2)
    assert all(row["top_n_lower"] == 1 for row in top_two["baseline"] if row["team_id"] in {"a", "c"})


def test_more_points_cannot_worsen_selected_teams_points_rank_bounds():
    result = simulate(
        teams(12, 12, 13, 14),
        [fixture(), fixture(2, "c", "d"), fixture(3, "a", "d")],
        [[0.25] * 4] * 3,
        simulations=300,
    )
    cases = [by_id(scenario["teams"]) for scenario in result["scenarios"]]
    for left, right in zip(cases, cases[1:]):
        assert left["a"]["expected_points"] >= right["a"]["expected_points"]
        assert left["a"]["expected_rank"] <= right["a"]["expected_rank"]
        assert left["a"]["top_n_lower"] >= right["a"]["top_n_lower"]
        assert left["a"]["top_n_upper"] >= right["a"]["top_n_upper"]
        assert left["b"]["expected_rank"] >= right["b"]["expected_rank"]
    for case in cases:
        for row in case.values():
            assert 0 <= row["top_n_lower"] <= row["top_n_upper"] <= 1
            assert 1 <= row["expected_rank"] <= 4


def test_deltas_use_same_random_other_results_and_rank_negative_means_improvement():
    result = simulate(
        teams(10, 12, 11), [fixture(), fixture(2, "a", "c")],
        [[0.1, 0.2, 0.3, 0.4], [0.25] * 4], simulations=250,
    )
    original = by_id(result["baseline"])
    for scenario in result["scenarios"]:
        for row in scenario["teams"]:
            baseline = original[row["team_id"]]
            assert row["delta_rank"] == row["expected_rank"] - baseline["expected_rank"]
            assert row["delta_top_n_lower"] == row["top_n_lower"] - baseline["top_n_lower"]
            assert row["delta_top_n_upper"] == row["top_n_upper"] - baseline["top_n_upper"]
            if row["team_id"] == "c":
                assert row["delta_points"] == 0


def test_seed_is_reproducible_and_sampling_margin_is_reported():
    a, b = simulate(seed=123, simulations=200), simulate(seed=123, simulations=200)
    assert a == b
    assert a["max_mc_margin_95"] == pytest.approx(1.96 * 0.5 / 200 ** 0.5)
    assert simulate(seed=124, simulations=200)["baseline"] != a["baseline"]
    assert any("fixed" in limitation for limitation in a["limitations"])
    assert any("not official" in limitation for limitation in a["limitations"])


@pytest.mark.parametrize("probabilities", [
    [], [[0.5, 0.5]], [[0.5, 0.5, 0.5, 0.5]], [[-0.1, 0.3, 0.4, 0.4]],
    [[float("nan"), 0, 0, 1]], [[float("inf"), 0, 0, 0]], [[2, 0, 0, -1]],
    [["0.25"] * 4], [[True, False, False, False]], [[0.1, 0.2, 0.3, 0.4], [1, 0, 0, 0]],
    [[0.25 + 0.1j, 0.25, 0.25, 0.25]],
])
def test_invalid_probability_vectors_are_rejected(probabilities):
    with pytest.raises(ValueError):
        simulate(probabilities=probabilities)


@pytest.mark.parametrize("status", ["live", "finished", "cancelled"])
def test_non_upcoming_matches_are_rejected(status):
    with pytest.raises(ValueError, match="upcoming"):
        simulate(fixtures=[fixture(status=status)])


def test_duplicate_unknown_or_same_teams_and_mixed_seasons_are_rejected():
    invalid_cases = [
        (teams(0, 0), [fixture(), fixture()]),
        (teams(0, 0), [fixture(away="unknown")]),
        (teams(0, 0), [fixture(away="a")]),
        (teams(0, 0), [fixture(), fixture(2, season=2026)]),
        ([Standing("a", "A", 0, 0), Standing("a", "Duplicate", 0, 0)], [fixture()]),
    ]
    for standings, fixtures in invalid_cases:
        with pytest.raises(ValueError):
            simulate(standings, fixtures, [[0.25] * 4] * len(fixtures))


@pytest.mark.parametrize("kwargs", [
    {"simulations": 0}, {"simulations": True}, {"simulations": 1.5},
    {"top_n": 0}, {"top_n": 3}, {"top_n": True},
    {"seed": -1}, {"seed": True}, {"seed": 2.3},
    {"selected_match_key": (2027, 999)},
])
def test_invalid_simulation_controls_are_rejected(kwargs):
    with pytest.raises(ValueError):
        simulate(**kwargs)


def test_invalid_baseline_and_naive_fixture_dates_are_rejected():
    for standing in [Standing("a", "A", -1, 0), Standing("a", "A", True, 0), Standing("a", "A", 0, -1)]:
        with pytest.raises(ValueError):
            simulate([standing, Standing("b", "B", 0, 0)])
    with pytest.raises(ValueError, match="timezone"):
        simulate(fixtures=[replace(fixture(), start=datetime(2026, 11, 1))])


@pytest.mark.parametrize("changes", [
    {"season": True}, {"game_id": 1.5}, {"game_id": -1}, {"home_id": ["a"]},
    {"start": "2026-11-01T16:00:00Z"},
])
def test_invalid_fixture_identity_types_are_rejected(changes):
    with pytest.raises(ValueError):
        simulate(fixtures=[replace(fixture(), **changes)])


def test_one_monte_carlo_draw_is_supported_and_inputs_are_not_mutated():
    standings, fixtures, probabilities = teams(1, 2), [fixture()], [[0.25] * 4]
    result = simulate(standings, fixtures, probabilities, simulations=1)
    assert result["simulations"] == 1
    assert [team.points for team in standings] == [1, 2]
    assert fixtures[0].status == "upcoming"
    assert probabilities == [[0.25] * 4]
