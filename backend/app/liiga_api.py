"""HTTP routes for real Liiga matches and backend-calculated team analysis."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query

from .models import LiigaAnalysisResponse, LiigaGamesResponse, LiigaTeamAnalysisResponse, LiigaDiscoveryResponse
from .services.liiga_analysis import calculate_team_stats
from .services.liiga_client import LiigaAPIError, SeasonGames, fetch_season_games

router = APIRouter(prefix="/api/liiga", tags=["Liiga (real data)"])
HELSINKI = ZoneInfo("Europe/Helsinki")


def current_season() -> int:
    """Liiga identifies a season by its ending year; July starts a new season."""
    today = datetime.now(HELSINKI).date()
    return today.year + (today.month >= 7)


async def _dataset(season: int) -> SeasonGames:
    try:
        return await fetch_season_games(season)
    except LiigaAPIError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/games", response_model=LiigaGamesResponse)
async def get_liiga_games(
    season: int | None = Query(default=None, ge=2000, le=2100),
    limit: int = Query(default=12, ge=1, le=30),
    from_date: date | None = Query(default=None),
    team_id: str | None = Query(default=None, min_length=1, max_length=100),
) -> LiigaGamesResponse:
    selected_season = season if season is not None else current_season()
    snapshot = await _dataset(selected_season)
    if from_date is None:
        from_date = (
            datetime.now(HELSINKI).date() - timedelta(days=7)
            if selected_season == current_season()
            else date(selected_season - 1, 7, 1)
        )
    # Filter the season dataset before limiting the UI's match cards.
    games = [
        game for game in snapshot.games
        if game.start.astimezone(HELSINKI).date() >= from_date
        and (team_id is None or team_id in (game.home_team.team_id, game.away_team.team_id))
    ][:limit]
    return LiigaGamesResponse(
        season=selected_season, updated_at=snapshot.updated_at,
        games_in_dataset=len(snapshot.games), count=len(games), games=games,
    )


@router.get("/discover", response_model=LiigaDiscoveryResponse)
async def get_liiga_discovery(
    season: int | None = Query(default=None, ge=2000, le=2100),
    city: str | None = Query(default=None, min_length=1, max_length=100),
) -> LiigaDiscoveryResponse:
    """A balanced real-data discovery feed, independent of upstream list order.

    The original fictional /api/feed model has athletes, radius and invented
    stories. Those fields don't exist in Liiga, so don't manufacture them.
    An optional city refers to the MATCH VENUE, not the viewer's distance or
    the location of the away team.
    """
    chosen_season = season or current_season()
    dataset = await _dataset(chosen_season)
    cities = sorted({
        game.city.strip() for game in dataset.games
        if game.city and game.city.strip() and game.status != "cancelled"
    }, key=str.casefold)
    selected_city = next(
        (value for value in cities if city and value.casefold() == city.strip().casefold()),
        None,
    )
    if city and selected_city is None:
        raise HTTPException(status_code=422, detail="This venue city is not in the selected Liiga season.")

    games = [
        game for game in dataset.games
        if game.status != "cancelled" and (
            selected_city is None or (game.city or "").strip().casefold() == selected_city.casefold()
        )
    ]
    live = sorted((game for game in games if game.status == "live"), key=lambda game: (game.start, game.id))[:3]
    # Reverse the past results: newest finished matches first, not the
    # earliest games in the season. No fictional scores are inserted.
    recent = sorted((game for game in games if game.status == "finished"),
                    key=lambda game: (game.start, game.id), reverse=True)[:6]
    upcoming = sorted((game for game in games if game.status == "upcoming"),
                      key=lambda game: (game.start, game.id))[:9]

    return LiigaDiscoveryResponse(
        season=chosen_season, updated_at=dataset.updated_at,
        games_in_dataset=len(dataset.games), selected_city=selected_city,
        cities=cities, live=live, recent=recent, upcoming=upcoming,
    )


@router.get("/analysis", response_model=LiigaAnalysisResponse)
async def get_liiga_analysis(
    season: int | None = Query(default=None, ge=2000, le=2100),
) -> LiigaAnalysisResponse:
    """Descriptive team statistics over all returned regular-season games."""
    selected_season = season if season is not None else current_season()
    snapshot = await _dataset(selected_season)
    teams, completed, excluded = calculate_team_stats(snapshot.games)
    return LiigaAnalysisResponse(
        season=selected_season, updated_at=snapshot.updated_at,
        games_in_dataset=len(snapshot.games), completed_games=completed,
        excluded_games=excluded, teams=teams,
    )


@router.get("/teams/{team_id}/analysis", response_model=LiigaTeamAnalysisResponse)
async def get_liiga_team_analysis(
    team_id: str,
    season: int | None = Query(default=None, ge=2000, le=2100),
) -> LiigaTeamAnalysisResponse:
    """The same season calculation for one provider team ID (including ':')."""
    analysis = await get_liiga_analysis(season)
    team = next((team for team in analysis.teams if team.team_id == team_id), None)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found in this season's Liiga games.")
    return LiigaTeamAnalysisResponse(
        **team.model_dump(), season=analysis.season, updated_at=analysis.updated_at,
        games_in_dataset=analysis.games_in_dataset,
    )
