"""Public current-season forecasts with bounded, validated scenario controls."""

from fastapi import APIRouter, HTTPException, Query

from .schemas import ImpactResponse, PredictionsResponse
from .service import PredictionUnavailable, get_impact, get_predictions

router = APIRouter(prefix="/api/liiga/predictions", tags=["Liiga predictions"])


@router.get("", response_model=PredictionsResponse)
async def predictions(
    limit: int = Query(default=12, ge=1, le=30),
    team_id: str | None = Query(default=None, min_length=1, max_length=100),
):
    """Prepare/evaluate a model on first use, then forecast upcoming fixtures.

    Historical data and the JSON model are cached locally. No LLM key is used.
    The held-out evaluation and production refit are separately identified.
    """
    try:
        return await get_predictions(limit=limit, team_id=team_id)
    except PredictionUnavailable as error:
        raise HTTPException(error.status_code, str(error)) from error


@router.get("/{game_id}/impact", response_model=ImpactResponse)
async def impact(
    game_id: int,
    top_n: int = Query(default=4, ge=1, le=30),
    simulations: int = Query(default=4000, ge=1000, le=10000),
    model_version: str | None = Query(default=None, min_length=1, max_length=100),
):
    """Compare all four outcomes using reconciled current regular-season points.

    Top-N points finish ranges leave official tied-points ordering unresolved.
    These are not official qualification or championship probabilities.
    """
    try:
        return await get_impact(game_id, top_n=top_n, simulations=simulations, expected_model_version=model_version)
    except PredictionUnavailable as error:
        raise HTTPException(error.status_code, str(error)) from error
