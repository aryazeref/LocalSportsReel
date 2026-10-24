"""Prepare reproducible forecasts lazily and reconcile league scenario inputs."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile
import threading

from threadpoolctl import threadpool_limits

from ..liiga_api import current_season
from . import data
from .domain import HELSINKI, Match, OUTCOMES, OUTCOME_POINTS, Standing, canonical_team_id
from .engine import ModelBundle, train_model
from .schemas import ForecastFixture, ForecastModel, ImpactResponse, PredictionsResponse
from .simulation import simulate_scenarios
from .settings import PredictionConfigurationError, PredictionSettings, resolve_settings

logger = logging.getLogger(__name__)
PIPELINE_VERSION = 2
_prepare_lock = asyncio.Lock()
_simulation_lock = asyncio.Semaphore(2)
_cached_context = None
_forecast_cache: dict = {}
_forecast_cache_lock = threading.Lock()


class PredictionUnavailable(Exception):
    def __init__(self, detail: str, status_code: int = 503):
        super().__init__(detail)
        self.status_code = status_code


@dataclass
class PredictionContext:
    season: int
    bundle: ModelBundle
    history: list[Match]
    current: data.SeasonData
    now: datetime


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _result_hash(matches: list[Match]) -> str:
    values = [(m.season, m.game_id, m.start.isoformat(), m.home_id, m.away_id,
               m.home_goals, m.away_goals, m.home_regulation_goals,
               m.away_regulation_goals, m.finish_type) for m in matches]
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def _train(history: list[Match], test_season: int, test_seasons: int = 1) -> ModelBundle:
    with threadpool_limits(limits=2):
        return train_model(history, test_season=test_season, test_seasons=test_seasons)


def _write_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=f'.{path.stem}-', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


async def context(*, refresh: bool = False, settings: PredictionSettings | None = None) -> PredictionContext:
    """The first visit prepares historical data/model; later visits reuse JSON."""
    global _cached_context
    now, season = utc_now(), current_season()
    try:
        settings = (settings or resolve_settings(season)).validate(season)
    except PredictionConfigurationError as error:
        raise PredictionUnavailable(str(error)) from error
    try:
        current = await data.load_season(season, refresh=refresh)
    except data.PredictionDataError as error:
        raise PredictionUnavailable(str(error), 502) from error
    today = now.astimezone(HELSINKI).date()
    known = [m for m in current.matches if m.outcome is not None and m.day < today]
    signature = (season, today.isoformat(), _result_hash(known), settings.history_seasons, settings.test_seasons)
    async with _prepare_lock:
        if not refresh and _cached_context is not None and _cached_context[0] == signature:
            stored = _cached_context[1]
            return PredictionContext(season, stored.bundle, stored.history, current, utc_now())
        semaphore = asyncio.Semaphore(3)

        async def get_year(year):
            async with semaphore:
                return await data.load_season(year, refresh=refresh)

        try:
            seasons = list(range(season - settings.history_seasons + 1, season))
            historical = await asyncio.gather(*(get_year(year) for year in seasons))
        except data.PredictionDataError as error:
            raise PredictionUnavailable(str(error), 502) from error
        snapshots = [*historical, current]
        # Results from the current Helsinki date are excluded even when marked ended.
        # This avoids unreliable end timestamps and overlapping same-day games.
        history = sorted(
            [m for snapshot in snapshots for m in snapshot.matches
             if m.outcome is not None and m.day < today],
            key=lambda match: (match.start, match.season, match.game_id),
        )
        fingerprint = hashlib.sha256(json.dumps({
            'results': _result_hash(history), 'settings': settings.as_dict(),
            'pipeline_version': PIPELINE_VERSION,
        }, sort_keys=True).encode()).hexdigest()
        artifact = data.CACHE_DIR / 'model-v1.json'
        bundle = None
        if not refresh and artifact.exists():
            try:
                value = json.loads(artifact.read_text(encoding='utf-8'))
                candidate = ModelBundle.from_dict(value)
                if (candidate.metadata.get('service_fingerprint') == fingerprint
                    and candidate.metadata.get('pipeline_version') == PIPELINE_VERSION
                    and candidate.metadata.get('preparation_settings') == settings.as_dict()):
                    bundle = candidate
            except (ValueError, KeyError, TypeError, OSError):
                logger.warning('Prediction artifact could not be restored; preparing a fresh model')
        if bundle is None:
            logger.info('Preparing chronological prediction evaluation on %d known results', len(history))
            try:
                bundle = await asyncio.to_thread(_train, history, season - 1, settings.test_seasons)
            except ValueError as error:
                raise PredictionUnavailable(f'Forecast preparation needs more usable history: {error}') from error
            bundle.metadata['service_fingerprint'] = fingerprint
            bundle.metadata['pipeline_version'] = PIPELINE_VERSION
            bundle.metadata['preparation_settings'] = settings.as_dict()
            bundle.metadata['history_seasons'] = settings.history_seasons
            bundle.metadata['evaluation_test_season_count'] = settings.test_seasons
            bundle.metadata['dataset_manifest'] = [
                {'season': season - settings.history_seasons + 1 + index,
                 'sha256': snapshot.source_hash,
                 'fetched_at': snapshot.fetched_at.isoformat(),
                 'matches': len(snapshot.matches), 'diagnostics': snapshot.diagnostics}
                for index, snapshot in enumerate(snapshots)
            ]
            try:
                await asyncio.to_thread(_write_json, artifact, bundle.to_dict())
                await asyncio.to_thread(_write_json, data.CACHE_DIR / 'evaluation.json', bundle.report)
            except OSError as error:
                raise PredictionUnavailable('Unable to save the prediction cache. Check that the backend cache folder is writable.') from error
        result = PredictionContext(season, bundle, history, current, utc_now())
        _cached_context = signature, result
        with _forecast_cache_lock:
            _forecast_cache.clear()
        return result


def _remaining(ctx: PredictionContext) -> list[Match]:
    return sorted(
        [m for m in ctx.current.matches if m.status == 'upcoming' and m.start > ctx.now
         and m.home_id and m.away_id and m.home_id != m.away_id],
        key=lambda match: (match.start, match.game_id),
    )


def _forecast_rows(ctx: PredictionContext, fixtures: list[Match]) -> list[dict]:
    key = (ctx.bundle.metadata['model_version'], ctx.current.source_hash,
           ctx.now.astimezone(HELSINKI).date().isoformat(), tuple(m.key for m in fixtures))
    with _forecast_cache_lock:
        cached = _forecast_cache.get(key)
    if cached is not None:
        return cached
    try:
        rows = ctx.bundle.predict_many(ctx.history, fixtures, cutoff=ctx.now)
    except ValueError as error:
        raise PredictionUnavailable(f'Forecast cannot be made with this historical cutoff: {error}') from error
    with _forecast_cache_lock:
        _forecast_cache.clear()
        _forecast_cache[key] = rows
    return rows


def _model_metadata(bundle: ModelBundle) -> ForecastModel:
    meta = bundle.metadata
    title = {'knn': 'Paper-inspired nearest neighbors', 'logistic': 'Regularized statistical model',
             'elo': 'Elo baseline', 'prior': 'Historical league baseline'}
    return ForecastModel(
        name=meta['selected_model'], display_name=title[meta['algorithm']],
        model_version=meta['model_version'], feature_set=meta['feature_set'], window=meta['window'],
        training_cutoff=meta['training_cutoff'], training_matches=meta['usable_matches'],
        trained_at=meta['created_at'],
        training_seasons=meta.get('training_seasons', []),
        history_seasons=meta.get('history_seasons', len(meta.get('training_seasons', []))),
        evaluation_test_seasons=meta.get('evaluation_test_seasons', []),
    )


def _serialize_fixture(match: Match, row: dict) -> ForecastFixture:
    probabilities = dict(zip(OUTCOMES, row['probabilities']))
    probabilities.update(home_win=row['home_win'], away_win=row['away_win'])
    return ForecastFixture(
        game_id=match.game_id, season=match.season, start=match.start,
        home_team={'team_id': match.home_id, 'name': match.home_name},
        away_team={'team_id': match.away_id, 'name': match.away_name},
        probabilities=probabilities,
        features={'names': row['feature_names'], 'values': row['features'],
                  'home_history': row['home_history'], 'away_history': row['away_history'],
                  'cold_start': row['cold_start'], 'history_cutoff': row['history_cutoff']},
        warnings=['Limited team history: using the historical league-prior probabilities.'] if row['cold_start'] else [],
    )


async def get_predictions(*, limit: int = 12, team_id: str | None = None) -> PredictionsResponse:
    ctx = await context()
    fixtures = _remaining(ctx)
    if team_id:
        canonical = canonical_team_id(team_id)
        fixtures = [m for m in fixtures if canonical in (m.home_id, m.away_id)]
    fixtures = fixtures[:limit]
    rows = await asyncio.to_thread(_forecast_rows, ctx, fixtures)
    return PredictionsResponse(
        season=ctx.season, source='Liiga Stats API v1', generated_at=ctx.now,
        data_updated_at=ctx.current.fetched_at, model=_model_metadata(ctx.bundle),
        evaluation=ctx.bundle.report,
        fixtures=[_serialize_fixture(match, row) for match, row in zip(fixtures, rows)],
        warnings=[
            'Experimental pre-match forecasts, not guarantees. Historical evaluation is shown below.',
            'Only results from earlier Helsinki calendar dates are inputs; same-day results, injuries and starting lineups are not included.',
            'Forecasts cover the regular-season fixtures returned by the provider, whose independent total is not supplied.',
        ],
    )


def reconcile_standings(matches: list[Match], standings: list[Standing]) -> None:
    """Require the provider's current table to agree with finished game outcomes."""
    totals = defaultdict(lambda: {'points': 0, 'played': 0, 'regulation_wins': 0,
                                  'overtime_wins': 0, 'overtime_losses': 0,
                                  'regulation_losses': 0, 'goals_for': 0, 'goals_against': 0})
    identifiers = {row.team_id for row in standings}
    for match in matches:
        if match.status != 'finished':
            continue
        label = match.outcome
        if label is None or match.home_id not in identifiers or match.away_id not in identifiers:
            raise PredictionUnavailable('Some finished matches have incomplete result data; points scenarios are unavailable.', 409)
        for side, opponent, points, field, goals, against in (
            (match.home_id, match.away_id, OUTCOME_POINTS[label][0], ('regulation_wins','overtime_wins','overtime_losses','regulation_losses')[label], match.home_goals, match.away_goals),
            (match.away_id, match.home_id, OUTCOME_POINTS[label][1], ('regulation_losses','overtime_losses','overtime_wins','regulation_wins')[label], match.away_goals, match.home_goals),
        ):
            row = totals[side]
            row['played'] += 1
            row['points'] += points
            row[field] += 1
            row['goals_for'] += goals
            row['goals_against'] += against
    for team in standings:
        if any(getattr(team, field) != value for field, value in totals[team.team_id].items()):
            raise PredictionUnavailable('Official standings and finished match results do not yet agree. Refresh after the provider updates both datasets.', 409)


def _completed_results_snapshot(ctx: PredictionContext) -> tuple[PredictionContext, list[Standing], list[Match], int]:
    """Reconstruct a pre-day table and replay every known fixture from that day.

    Today's final/live scores are deliberately ignored. Every noncancelled game
    from the cutoff onward is simulated once, so no points are lost or counted
    twice. This is a retrospective pre-match view, not a live-state forecast.
    """
    cutoff = ctx.now.astimezone(HELSINKI).replace(hour=0, minute=0, second=0, microsecond=0, fold=0).astimezone(timezone.utc)
    names: dict[str, str] = {}
    completed, replay, seen = [], [], set()
    started = 0
    for match in ctx.current.matches:
        if match.status == 'cancelled':
            continue
        if (match.key in seen or match.season != ctx.season or not match.home_id
            or not match.away_id or match.home_id == match.away_id):
            raise PredictionUnavailable('A completed-results snapshot cannot be calculated: the schedule has duplicate matches or unresolved teams.', 409)
        if match.status in ('live', 'finished') and match.start > ctx.now:
            raise PredictionUnavailable('A completed-results snapshot cannot be calculated: a future fixture is marked as started or finished.', 409)
        seen.add(match.key)
        names.update({match.home_id: match.home_name, match.away_id: match.away_name})
        if match.start < cutoff:
            if match.status != 'finished' or match.outcome is None:
                raise PredictionUnavailable('A completed-results snapshot cannot be calculated: earlier matches have unfinished or incomplete results.', 409)
            completed.append(match)
        else:
            if match.status not in ('upcoming', 'live', 'finished') or match.start <= cutoff:
                raise PredictionUnavailable('A completed-results snapshot cannot be calculated: a fixture has an unresolved status or cutoff time.', 409)
            started += int(match.status in ('live', 'finished') or match.start <= ctx.now)
            replay.append(replace(match, status='upcoming', home_goals=None, away_goals=None,
                                  home_regulation_goals=None, away_regulation_goals=None,
                                  finish_type=None, home_expected_goals=None, away_expected_goals=None))
    totals = {team: {'points': 0, 'played': 0, 'regulation_wins': 0, 'overtime_wins': 0,
                     'overtime_losses': 0, 'regulation_losses': 0, 'goals_for': 0, 'goals_against': 0}
              for team in names}
    home_fields = ('regulation_wins', 'overtime_wins', 'overtime_losses', 'regulation_losses')
    away_fields = tuple(reversed(home_fields))
    for match in completed:
        outcome = match.outcome
        assert outcome is not None
        for team, points, field, goals, against in (
            (match.home_id, OUTCOME_POINTS[outcome][0], home_fields[outcome], match.home_goals, match.away_goals),
            (match.away_id, OUTCOME_POINTS[outcome][1], away_fields[outcome], match.away_goals, match.home_goals),
        ):
            row = totals[team]
            row['points'] += points
            row['played'] += 1
            row[field] += 1
            row['goals_for'] += goals
            row['goals_against'] += against
    standings = [Standing(team, names[team], **totals[team]) for team in sorted(names)]
    historical = [match for match in ctx.history if match.start < cutoff]
    snapshot_ctx = replace(ctx, history=historical, now=cutoff)
    return snapshot_ctx, standings, sorted(replay, key=lambda match: (match.start, match.game_id)), started


async def get_impact(game_id: int, *, top_n: int = 4, simulations: int = 4000, expected_model_version: str | None = None) -> ImpactResponse:
    ctx = await context()
    if expected_model_version is not None and expected_model_version != ctx.bundle.metadata['model_version']:
        raise PredictionUnavailable('The forecast model has updated. Refresh forecasts before comparing league scenarios.', 409)
    fixtures = _remaining(ctx)
    selected = next((game for game in fixtures if game.game_id == game_id), None)
    if selected is None:
        raise PredictionUnavailable('The selected match is not an upcoming regular-season fixture.', 404)
    unresolved = [m for m in ctx.current.matches if m.status == 'live' or
                  (m.status == 'upcoming' and (m.start <= ctx.now or not m.home_id or not m.away_id or m.home_id == m.away_id))]
    today = ctx.now.astimezone(HELSINKI).date()
    snapshot_mode = any(match.day == today and (match.status == 'live' or
                        (match.status == 'upcoming' and match.start <= ctx.now)) for match in unresolved)
    started = 0
    if snapshot_mode:
        calculation_ctx, standings, fixtures, started = _completed_results_snapshot(ctx)
        standings_updated_at = ctx.current.fetched_at
        warnings = [
            'The table is reconstructed from completed results before the stated Helsinki-day cutoff; it is not the official live standings.',
            "All of today's noncancelled matches, including live and already-finished matches, are simulated again from their pre-match probabilities. Today's scores and outcomes are ignored.",
            'Exact tie-breakers, playoff rules, and any points adjustments outside match results are not encoded.',
        ]
    else:
        if unresolved:
            raise PredictionUnavailable('League scenarios are paused because the schedule has unresolved dates or teams. A completed-results snapshot is unavailable for these fixtures.', 409)
        try:
            official = await data.load_standings(ctx.season)
        except data.PredictionDataError as error:
            raise PredictionUnavailable(str(error), 502) from error
        standings = list(official.standings)
        standings_updated_at = official.fetched_at
        calculation_ctx = ctx
        warnings = ['Official points were reconciled with completed results. Exact tie-breakers and playoff rules are not encoded.']
    if not 1 <= top_n <= len(standings):
        raise PredictionUnavailable('Top-N must be between one and the number of teams.', 422)
    if not snapshot_mode:
        reconcile_standings(list(ctx.current.matches), standings)
    rows = await asyncio.to_thread(_forecast_rows, calculation_ctx, fixtures)
    async with _simulation_lock:
        try:
            result = await asyncio.to_thread(
                simulate_scenarios, standings, fixtures,
                [row['probabilities'] for row in rows], selected_match_key=selected.key,
                simulations=simulations, top_n=top_n, seed=2026,
            )
        except ValueError as error:
            raise PredictionUnavailable(f'League scenario inputs are incomplete: {error}', 409) from error
    return ImpactResponse(
        **result, season=ctx.season, game_id=game_id, generated_at=ctx.now,
        standings_updated_at=standings_updated_at, model_name=ctx.bundle.metadata['selected_model'],
        model_version=ctx.bundle.metadata['model_version'], forecast_cutoff=ctx.now.astimezone(HELSINKI).date().isoformat(),
        standings_basis='completed_results_snapshot' if snapshot_mode else 'official',
        standings_as_of=calculation_ctx.now if snapshot_mode else None,
        simulated_started_games=started, warnings=warnings,
    )
