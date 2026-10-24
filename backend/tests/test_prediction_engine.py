"""Temporal safeguards, historical evaluation and reusable statistical models."""

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import json

import numpy as np
import pytest

from app.prediction.domain import Match, OUTCOMES, REGULATION
from app.prediction.engine import ModelBundle, probability_metrics, train_model
from app.prediction.features import FeatureState, build_feature_rows, build_state, feature_names


def match(game_id, day, *, season=2022, home="1", away="2", outcome=0):
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=15)
    if outcome == 0:
        final, regulation, finish = (4, 2), (4, 2), REGULATION
    elif outcome == 3:
        final, regulation, finish = (1, 3), (1, 3), REGULATION
    elif outcome == 1:
        final, regulation, finish = (4, 3), (3, 3), "ENDED_DURING_WINNING_SHOT_COMPETITION"
    else:
        final, regulation, finish = (2, 3), (2, 2), "ENDED_DURING_EXTENDED_GAME_TIME"
    return Match(
        season, game_id, start, home, away, f"Club {home}", f"Club {away}", "finished",
        *final, *regulation, finish,
    )


@pytest.fixture(scope="module")
def history():
    games = []
    teams = ["1", "2", "3", "4", "5", "6"]
    for season, count in [(2022, 180), (2023, 180), (2024, 120)]:
        for index in range(count):
            day = date(season - 1, 8, 1) + timedelta(days=index // 3)
            rotation = (index // 3) % len(teams)
            home = teams[(2 * (index % 3) + rotation) % len(teams)]
            away = teams[(2 * (index % 3) + rotation + 1) % len(teams)]
            # Nonuniform four-outcome labels and changing team schedules.
            outcome = (0, 0, 3, 1, 3, 0, 2)[index % 7]
            games.append(match(index + 1, day, season=season, home=home, away=away, outcome=outcome))
    return games


@pytest.fixture(scope="module")
def bundle(history):
    return train_model(history, test_season=2024)


def fixture_after(history):
    latest = max(game.start for game in history)
    return Match(2025, 500, latest + timedelta(days=10), "1", "2", "Club 1", "Club 2", "upcoming")


def test_features_exclude_later_and_same_day_results():
    first = match(1, date(2021, 8, 1))
    simultaneous = match(2, first.day, home="3", away="1", outcome=3)
    tomorrow = match(3, first.day + timedelta(days=1), home="1", away="4")
    future = match(4, first.day + timedelta(days=10), home="99", away="1")
    altered_first = replace(first, home_goals=40, home_regulation_goals=40)
    original = build_feature_rows([first, simultaneous, tomorrow, future])
    changed = build_feature_rows([altered_first, simultaneous, tomorrow])
    assert original[1]["features"] == changed[1]["features"]
    assert np.array_equal(original[1]["prior"], changed[1]["prior"])
    assert np.array_equal(original[1]["elo"], changed[1]["elo"])
    assert original[0]["features"] == changed[0]["features"]
    assert original[2]["features"] != changed[2]["features"]
    assert original[1]["home_history"] == 0
    assert original[2]["home_history"] == 2


def test_later_new_club_does_not_change_historical_rank_cohort(history):
    initial = build_feature_rows(history[:90])
    later = match(999, history[89].day + timedelta(days=10), home="future-club")
    extended = build_feature_rows([*history[:90], later])
    assert [row["features"] for row in initial] == [row["features"] for row in extended[:90]]


def test_regulation_goal_features_do_not_include_shootout_winner():
    shootout = match(1, date(2021, 8, 1), outcome=1)
    state = FeatureState()
    state.add(shootout)
    own = state.histories["1"][0]
    assert (own.goals_for, own.goals_against, own.points) == (3, 3, 2)
    assert state.histories["2"][0].points == 1


def test_total_and_homeaway_profiles_are_explicit_and_finite(history):
    fixture = history[100]
    state = build_state(history, fixture.day)
    total = state.profile(fixture, 12, "total")
    extended = state.profile(fixture, 12, "homeaway")
    assert len(total["features"]) == 6
    assert len(extended["features"]) == 18
    assert extended["features"][:6] == total["features"]
    assert "away_home_goals_for" in extended["feature_names"]
    assert "home_away_goals_for" in extended["feature_names"]
    assert np.isfinite(extended["features"]).all()
    for rank in extended["features"][2::3]:
        assert 0 <= rank <= 1


def test_unknown_clubs_use_neutral_finite_features():
    state = FeatureState()
    fixture = Match(2025, 1, datetime(2024, 9, 1, tzinfo=timezone.utc), "new", "other", "New", "Other", "upcoming")
    result = state.profile(fixture)
    assert result["features"] == [2.5, 2.5, 0.5, 2.5, 2.5, 0.5]
    assert result["cold_start"]
    assert result["home_history"] == result["away_history"] == 0


def test_feature_helpers_reject_nonchronological_or_duplicate_data(history):
    with pytest.raises(ValueError, match="Duplicate"):
        build_feature_rows([history[0], history[0]])
    state = FeatureState()
    state.add(history[90])
    with pytest.raises(ValueError, match="earlier days"):
        state.profile(history[90])
    with pytest.raises(ValueError, match="chronologically"):
        state.add(history[0])
    with pytest.raises(ValueError, match="feature set"):
        feature_names("made-up")


def test_report_uses_historical_validation_and_untouched_test_season(bundle):
    report = bundle.report
    assert report["selection_metric"] == "chronological validation four-outcome log loss"
    assert report["validation"]["folds"] == 3
    assert report["validation"]["end"] < report["test"]["start"]
    assert report["test"]["training_end"] < report["test"]["start"]
    assert report["test"]["season"] == 2024
    assert report["test"]["count"] == 120
    assert report["test"]["used_for_selection"] is False
    assert {row["algorithm"] for row in report["test"]["metrics"]} == {"knn", "logistic", "prior", "elo"}
    selected = next(row for row in report["test"]["metrics"] if row["selected"])
    assert selected["name"] == report["selected_model"]
    assert sum(row["count"] for row in selected["calibration_bins"]) == 120
    assert bundle.metadata["production_refit"]


def test_future_test_labels_do_not_choose_model(history, bundle):
    altered = [
        replace(game, home_goals=15, away_goals=0, home_regulation_goals=15,
                away_regulation_goals=0, finish_type=REGULATION)
        if game.season == 2024 else game
        for game in history
    ]
    changed = train_model(altered, test_season=2024)
    assert changed.report["selected_model"] == bundle.report["selected_model"]
    assert changed.report["validation"]["candidates"] == bundle.report["validation"]["candidates"]
    assert changed.metadata["dataset_sha256"] != bundle.metadata["dataset_sha256"]


def test_json_artifact_roundtrip_reproduces_forecast_and_has_no_pickle(history, bundle):
    fixture = fixture_after(history)
    expected = bundle.predict(history, fixture)
    encoded = json.dumps(bundle.to_dict(), allow_nan=False)
    loaded = ModelBundle.from_dict(json.loads(encoded))
    actual = loaded.predict(history, fixture)
    assert actual == expected
    assert tuple(loaded.metadata["outcomes"]) == OUTCOMES
    assert all(0 < value < 1 for value in actual["probabilities"])
    assert sum(actual["probabilities"]) == pytest.approx(1)
    assert actual["home_win"] + actual["away_win"] == pytest.approx(1)
    assert actual["home_win"] == pytest.approx(sum(actual["probabilities"][:2]))
    assert actual["regulation_tie"] == pytest.approx(sum(actual["probabilities"][1:3]))
    # Runtime inference caches never mutate the serialized model.
    assert json.dumps(bundle.to_dict(), allow_nan=False) == encoded


def test_forecast_cutoff_ignores_later_history_and_future_clubs(history, bundle):
    fixture = fixture_after(history)
    cutoff = fixture.start - timedelta(days=2)
    future = match(999, fixture.day + timedelta(days=1), season=2025, home="unknown", outcome=3)
    first = bundle.predict(history, fixture, cutoff=cutoff)
    second = bundle.predict([*history, future], fixture, cutoff=cutoff)
    assert first == second
    assert first["history_cutoff"] < first["cutoff"]


def test_production_artifact_cannot_backtest_on_its_training_history(history, bundle):
    with pytest.raises(ValueError, match="later training outcomes"):
        bundle.predict(history, history[100])
    with pytest.raises(ValueError, match="timezone"):
        bundle.predict(history, fixture_after(history), cutoff=datetime(2025, 1, 1))


def test_cold_start_forecast_uses_explicit_prior(history, bundle):
    fixture = replace(fixture_after(history), home_id="brand-new")
    result = bundle.predict(history, fixture)
    state = build_state(history, fixture.day)
    assert result["cold_start"] is True
    assert result["home_history"] == 0
    assert result["probabilities"] == pytest.approx(state.prior.tolist())


def test_probability_metrics_are_losses_and_preserve_four_outcomes():
    metrics = probability_metrics([0, 1, 2, 3], np.eye(4))
    assert metrics["brier"] == pytest.approx(0, abs=1e-15)
    assert metrics["log_loss"] == pytest.approx(0, abs=1e-10)
    assert metrics["final_winner_accuracy"] == metrics["outcome_accuracy"] == 1
    assert metrics["regulation_rps"] == pytest.approx(0, abs=1e-15)
    with pytest.raises(ValueError, match="distribution"):
        probability_metrics([0], [[-1, 1, 1, 0]])


def test_calibration_boundary_probabilities_belong_to_exactly_one_bin():
    probabilities = [[value * 0.75, value * 0.25, (1 - value) * 0.25, (1 - value) * 0.75]
                     for value in (0.2, 0.4, 0.6, 0.8)]
    result = probability_metrics([0, 1, 2, 3], probabilities)
    assert sum(row["count"] for row in result["calibration_bins"]) == 4


def test_insufficient_history_and_wrong_artifacts_fail_explicitly(history, bundle):
    with pytest.raises(ValueError, match="250"):
        train_model(history[:30])
    with pytest.raises(ValueError, match="held-out season"):
        train_model(history, test_season=2035)
    broken = {**bundle.to_dict(), "artifact_version": -1}
    with pytest.raises(ValueError, match="version"):
        ModelBundle.from_dict(broken)


@pytest.fixture(scope='module')
def rolling_bundle(history):
    return train_model(history, test_season=2024, test_seasons=2)


def test_rolling_report_pools_unequal_season_counts(rolling_bundle):
    test = rolling_bundle.report['test']
    assert test['seasons'] == [2023, 2024]
    assert test['count'] == 300
    assert test['kind'] == 'retrospective_rolling_origin' and test['independent_blind'] is False
    assert test['used_for_selection'] is False
    assert [fold['count'] for fold in test['per_season']] == [180, 120]
    selected = next(row for row in test['metrics'] if row['name'] == 'selected_policy')
    folds = [next(row for row in fold['metrics'] if row['selected']) for fold in test['per_season']]
    weighted = sum(row['log_loss'] * row['count'] for row in folds) / test['count']
    assert selected['log_loss'] == pytest.approx(weighted)
    assert sum(row['count'] for row in selected['calibration_bins']) == test['count']
    assert len(test['metrics']) == 5
    for fold in test['per_season']:
        assert fold['training_end'] < fold['start']
        assert fold['validation']['end'] < fold['start']
    assert rolling_bundle.metadata['selected_model'] == test['per_season'][-1]['selected_model']


def test_later_test_year_cannot_change_earlier_origin_selection(history, rolling_bundle):
    changed = [match(g.game_id, g.day, season=g.season, home=g.home_id, away=g.away_id,
                     outcome=3 - g.outcome) if g.season == 2024 else g for g in history]
    altered = train_model(changed, test_season=2024, test_seasons=2)
    original = rolling_bundle.report['test']['per_season'][0]
    earlier = altered.report['test']['per_season'][0]
    assert earlier['selected_model'] == original['selected_model']
    assert earlier['validation'] == original['validation']
    assert earlier['metrics'] == original['metrics']


@pytest.mark.parametrize('count', [0, -1, True, 1.5, 4])
def test_invalid_or_missing_rolling_test_scope_is_explicit(history, count):
    with pytest.raises(ValueError):
        train_model(history, test_season=2024, test_seasons=count)
