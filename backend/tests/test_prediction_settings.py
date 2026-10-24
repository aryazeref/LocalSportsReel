"""Scope settings are explicit, bounded by available eras, and non-mutating."""

import os
from types import SimpleNamespace

import pytest

from app.prediction import prepare, service
from app.prediction.settings import PredictionConfigurationError, PredictionSettings, resolve_settings


@pytest.fixture(autouse=True)
def clean_settings(monkeypatch):
    for key in ('PREDICTION_HISTORY_SEASONS', 'PREDICTION_TEST_SEASONS'):
        monkeypatch.delenv(key, raising=False)


def test_defaults_expand_history_and_rolling_tests():
    assert resolve_settings(2027) == PredictionSettings(10, 3)


def test_explicit_overrides_win_without_mutating_environment(monkeypatch):
    monkeypatch.setenv('PREDICTION_HISTORY_SEASONS', '12')
    monkeypatch.setenv('PREDICTION_TEST_SEASONS', '4')
    assert resolve_settings(2027) == PredictionSettings(12, 4)
    assert resolve_settings(2027, history_seasons=8, test_seasons=2) == PredictionSettings(8, 2)
    assert os.environ['PREDICTION_HISTORY_SEASONS'] == '12'
    assert os.environ['PREDICTION_TEST_SEASONS'] == '4'


@pytest.mark.parametrize('history,tests', [
    (0, 1), (-1, 1), (3, 1), (4, 0), (4, 2), (10, 8), (29, 1),
    (True, 1), (10, False), (10, 1.5), (1.5, 1),
])
def test_invalid_or_unsupported_scope_is_rejected(history, tests):
    with pytest.raises(PredictionConfigurationError):
        resolve_settings(2027, history_seasons=history, test_seasons=tests)


@pytest.mark.parametrize('value', ['', 'abc', '3.5', 'True'])
def test_invalid_environment_integer_has_configuration_error(monkeypatch, value):
    monkeypatch.setenv('PREDICTION_HISTORY_SEASONS', value)
    with pytest.raises(PredictionConfigurationError, match='integer'):
        resolve_settings(2027)


def test_api_minimum_ending_season_is_inclusive():
    assert resolve_settings(2027, history_seasons=28, test_seasons=3).history_seasons == 28


def test_cli_overrides_resolve_before_preparation(monkeypatch, tmp_path, capsys):
    env = tmp_path / '.env'
    env.write_text('PREDICTION_HISTORY_SEASONS=8\nPREDICTION_TEST_SEASONS=2\n')
    calls = []
    async def fake_context(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(bundle=SimpleNamespace(metadata={'ready': True}, report={'test': {'count': 2}}))
    monkeypatch.setattr(service, 'context', fake_context)
    assert prepare.main(['--history-seasons', '10', '--test-seasons', '3', '--env-file', str(env)]) == 0
    assert calls[0]['settings'] == PredictionSettings(10, 3)
    assert os.environ['PREDICTION_HISTORY_SEASONS'] == '8'
    assert os.environ['PREDICTION_TEST_SEASONS'] == '2'
    assert '"ready": true' in capsys.readouterr().out


def test_invalid_cli_scope_never_calls_data_provider(monkeypatch, tmp_path, capsys):
    async def reject_context(**kwargs):
        pytest.fail('Invalid CLI settings must not start data preparation')
    monkeypatch.setattr(service, 'context', reject_context)
    assert prepare.main(['--test-seasons', '0', '--env-file', str(tmp_path / 'missing.env')]) == 1
    assert 'Forecast preparation failed' in capsys.readouterr().out
