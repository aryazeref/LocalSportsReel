"""Prepare forecast data/model explicitly: python -m app.prediction.prepare."""

import argparse
import asyncio
import json
import logging

from .service import PredictionUnavailable, context


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='Refresh provider snapshots and retrain even if an artifact exists')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    try:
        result = asyncio.run(context(refresh=args.refresh))
    except PredictionUnavailable as error:
        print(f'Forecast preparation failed: {error}')
        return 1
    print(json.dumps({'model': result.bundle.metadata, 'evaluation': result.bundle.report}, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
