"""Historical team statistics from provider results, not standings or predictions.

Wins and losses include overtime and shootout results in the final score.
"""

from collections.abc import Iterable

from ..models import LiigaGame, LiigaTeamStats


def calculate_team_stats(games: Iterable[LiigaGame]) -> tuple[list[LiigaTeamStats], int, int]:
    """Return team summaries, usable completed games, and excluded results.

    A completed result is excluded when either side lacks an ID or score, or
    both sides have the same ID. Form is newest first, regardless of input order.
    """
    teams: dict[str, LiigaTeamStats] = {}
    completed = excluded = 0
    for game in sorted(games, key=lambda item: (item.start, item.id), reverse=True):
        home, away = game.home_team, game.away_team
        for team in (home, away):
            if team.team_id and team.team_id not in teams:
                teams[team.team_id] = LiigaTeamStats(team_id=team.team_id, name=team.name)
        if game.status != "finished":
            continue
        if (
            not home.team_id or not away.team_id or home.team_id == away.team_id
            or home.goals is None or away.goals is None
        ):
            excluded += 1
            continue
        completed += 1
        for team, opponent in ((home, away), (away, home)):
            stats = teams[team.team_id]
            stats.matches_played += 1
            stats.goals_for += team.goals
            stats.goals_against += opponent.goals
            if team.goals > opponent.goals:
                result = "W"
                stats.wins += 1
            elif team.goals < opponent.goals:
                result = "L"
                stats.losses += 1
            else:
                result = "D"
                stats.draws += 1
            if len(stats.form) < 5:
                stats.form.append(result)
    for stats in teams.values():
        stats.goal_difference = stats.goals_for - stats.goals_against
        if stats.matches_played:
            stats.win_percentage = round(100 * stats.wins / stats.matches_played, 1)
    return sorted(teams.values(), key=lambda team: (team.name.casefold(), team.team_id)), completed, excluded
