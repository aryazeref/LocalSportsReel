"""Prepare forecasts: python -m app.prediction.prepare --history-seasons 10 --test-seasons 3."""

import argparse
import asyncio
import json
import logging
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='Refresh provider snapshots and retrain even if an artifact exists')
    parser.add_argument('--history-seasons', type=int, help='Ending-seasons of input history, including the current season (default 10)')
    parser.add_argument('--test-seasons', type=int, help='Prior seasons for rolling chronological tests (default 3)')
    parser.add_argument('--env-file', type=Path, default=Path(__file__).resolve().parents[2] / '.env', help='Optional backend environment file; flags override its settings')
    args = parser.parse_args(argv)
    # CACHE_DIR is resolved on import, so load local settings first.
    from dotenv import load_dotenv
    load_dotenv(args.env_file)
    from ..liiga_api import current_season
    from .settings import PredictionConfigurationError, resolve_settings
    from .service import PredictionUnavailable, context

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    try:
        settings = resolve_settings(current_season(), history_seasons=args.history_seasons, test_seasons=args.test_seasons)
        result = asyncio.run(context(refresh=args.refresh, settings=settings))
    except (PredictionUnavailable, PredictionConfigurationError) as error:
        print(f'Forecast preparation failed: {error}')
        return 1
    print(json.dumps({'model': result.bundle.metadata, 'evaluation': result.bundle.report}, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
