"""Explicit data/evaluation scope, shared by API startup and preparation CLI."""

from dataclasses import asdict, dataclass
import os

DEFAULT_HISTORY_SEASONS = 10
DEFAULT_TEST_SEASONS = 3


class PredictionConfigurationError(ValueError):
    """A requested history/evaluation scope cannot support chronological testing."""


@dataclass(frozen=True)
class PredictionSettings:
    history_seasons: int = DEFAULT_HISTORY_SEASONS
    test_seasons: int = DEFAULT_TEST_SEASONS

    def as_dict(self) -> dict[str, int]:
        return asdict(self)

    def validate(self, season: int) -> "PredictionSettings":
        if type(season) is not int or not 2000 <= season <= 2100:
            raise PredictionConfigurationError("The current ending-season must be between 2000 and 2100.")
        if type(self.history_seasons) is not int or self.history_seasons < 4:
            raise PredictionConfigurationError("PREDICTION_HISTORY_SEASONS must be an integer of at least 4, including the current season.")
        if season - self.history_seasons + 1 < 2000:
            raise PredictionConfigurationError("The requested history starts before the API's supported ending-season 2000.")
        if type(self.test_seasons) is not int or not 1 <= self.test_seasons <= self.history_seasons - 3:
            raise PredictionConfigurationError("PREDICTION_TEST_SEASONS must be at least 1 and leave two earlier seasons for training/validation, plus the current season.")
        return self


def _integer(value: str | int, name: str) -> int:
    if type(value) is int:
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            pass
    raise PredictionConfigurationError(f"{name} must be an integer.")


def resolve_settings(
    season: int, *, history_seasons: int | None = None, test_seasons: int | None = None,
) -> PredictionSettings:
    """Per-call overrides take precedence over environment settings; no mutation."""
    history = os.getenv("PREDICTION_HISTORY_SEASONS", str(DEFAULT_HISTORY_SEASONS)) if history_seasons is None else history_seasons
    tests = os.getenv("PREDICTION_TEST_SEASONS", str(DEFAULT_TEST_SEASONS)) if test_seasons is None else test_seasons
    return PredictionSettings(
        _integer(history, "PREDICTION_HISTORY_SEASONS"),
        _integer(tests, "PREDICTION_TEST_SEASONS"),
    ).validate(season)
