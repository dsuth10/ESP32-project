"""Local readiness must explain the Board route without exposing configuration."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_resource_policy import board_image_issues, board_image_readiness


def configured():
    return {'LOCAL_ONLY': '0', 'IMAGE_PROVIDER': 'gemini', 'IMAGE_GENERATION_ENABLED': '1',
        'GOOGLE_IMAGE_API_KEY': 'synthetic-private-key', 'GOOGLE_IMAGE_SIZE': '1K',
        'GOOGLE_IMAGE_ESTIMATE_1K_AUD_CENTS': '24', 'MEDIA_SYNC_ENABLED': '1',
        'MEDIA_SERVER_URL': 'https://private.invalid', 'MEDIA_SERVER_TOKEN': 'synthetic-private-token'}


def test_configured_readiness_never_claims_remote_verification_or_exposes_secrets():
    config = configured()
    result = board_image_readiness(config)
    assert board_image_issues(config) == []
    assert '24 AUD cents' in result and '1K' in result
    assert 'have not been checked' in result
    assert 'teacher preview' in result
    for value in ('synthetic-private-key', 'synthetic-private-token', 'private.invalid'):
        assert value not in result


@pytest.mark.parametrize(('override', 'message'), [
    ({'LOCAL_ONLY': '1'}, 'local-only'),
    ({'IMAGE_PROVIDER': 'openai'}, 'Select Google Gemini'),
    ({'GOOGLE_IMAGE_API_KEY': ''}, 'Google image API key'),
    ({'GOOGLE_IMAGE_MODEL': 'unexpected-private-model'}, 'supported Google model'),
    ({'IMAGE_GENERATION_ENABLED': '0'}, 'Enable paid image requests'),
    ({'GOOGLE_IMAGE_SIZE': '2K'}, 'Choose 1K'),
    ({'GOOGLE_IMAGE_ESTIMATE_1K_AUD_CENTS': '0'}, '1–50 AUD cents'),
    ({'GOOGLE_IMAGE_ESTIMATE_1K_AUD_CENTS': '51'}, '1–50 AUD cents'),
    ({'GOOGLE_IMAGE_ESTIMATE_1K_AUD_CENTS': 'invalid-private-amount'}, '1–50 AUD cents'),
    ({'MEDIA_SYNC_ENABLED': '0'}, 'shared budget service'),
    ({'MEDIA_SERVER_TOKEN': ''}, 'bearer token'),
    ({'MEDIA_SERVER_URL': 'http://private.invalid'}, 'HTTPS'),
    ({'MEDIA_SERVER_URL': 'https://user:private-secret@host.invalid'}, 'HTTPS'),
    ({'MEDIA_SERVER_URL': 'https://['}, 'HTTPS'),
])
def test_missing_or_invalid_configuration_is_actionable_and_secret_free(override, message):
    config = {**configured(), **override}
    text = board_image_readiness(config)
    assert message in text
    assert 'Board settings' in text
    assert 'private-' not in text and 'host.invalid' not in text


def test_loopback_ledger_is_allowed_without_remote_access():
    config = {**configured(), 'MEDIA_SERVER_URL': 'http://127.0.0.1:8643'}
    assert board_image_issues(config) == []


def test_runtime_can_use_explicitly_injected_provider_and_ledger():
    config = {**configured(), 'GOOGLE_IMAGE_API_KEY': '', 'MEDIA_SYNC_ENABLED': '0',
              'MEDIA_SERVER_URL': '', 'MEDIA_SERVER_TOKEN': ''}
    assert board_image_issues(config, provider_available=True, budget_available=True) == []
    assert 'shared budget service' in ' '.join(board_image_issues(config,
        provider_available=True, budget_available=False))


def test_local_mode_explains_local_choice_without_instructing_chart_data():
    text = board_image_readiness({'LOCAL_ONLY': True})
    assert 'Choose a saved image' in text
    assert 'chart' not in text


def test_composition_status_explains_routes_without_claiming_access():
    config = {**configured(), 'GROQ_API_KEY': 'private-groq', 'HERMES_ENABLED': '1',
        'HERMES_URL': 'https://private-hermes.invalid', 'HERMES_TOKEN': 'private-hermes-token'}
    text = board_image_readiness(config)
    assert 'resource planning: Groq key configured' in text
    assert 'Page composition: Hermes configured' in text
    assert 'access is unverified' in text
    assert 'private-' not in text
    local = board_image_readiness({**config, 'LOCAL_ONLY': '1'})
    assert 'local model fallback' in local and 'Hermes configured' not in local
