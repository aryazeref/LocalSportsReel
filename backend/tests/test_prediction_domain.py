"""Reject impossible result progressions before producing training labels."""

from datetime import datetime, timezone

import pytest

from app.prediction.domain import Match


@pytest.mark.parametrize("finish", [
    "ENDED_DURING_EXTENDED_GAME_TIME", "ENDED_DURING_WINNING_SHOT_COMPETITION",
])
@pytest.mark.parametrize("final,label", [
    ((4, 3), 1), ((3, 4), 2), ((6, 0), None), ((4, 4), None),
    ((5, 3), None), ((2, 3), None),
])
def test_extra_time_keeps_regulation_goals_and_adds_only_winning_goal(finish, final, label):
    game = Match(
        season=2027, game_id=1, start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        home_id="1", away_id="2", home_name="Home", away_name="Away",
        status="finished", home_goals=final[0], away_goals=final[1],
        home_regulation_goals=3, away_regulation_goals=3, finish_type=finish,
    )
    assert game.outcome == label
