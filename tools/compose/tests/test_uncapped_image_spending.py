"""Explicit uncapped billing preserves durable claims, previews and recovery."""
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_resource_policy import BoardRequestAcquisition, board_image_issues, board_image_readiness
from image_provider_config import image_snapshot, image_readiness
from media_service import MediaService
from media_store import MediaStore
from media_providers import ProviderFailure
from test_media_service import png


def config():
    return {'IMAGE_PROVIDER': 'gemini', 'GOOGLE_IMAGE_API_KEY': 'synthetic-google-key',
            'IMAGE_GENERATION_ENABLED': '1', 'IMAGE_SPENDING_UNCAPPED': '1',
            'LOCAL_ONLY': '0', 'MEDIA_SYNC_ENABLED': '0'}


def service(root, *, sync=None):
    provider = Mock()
    provider.generate.return_value = {'data': png(), 'source': {'provider': 'gemini', 'model': 'fixture'}}
    return MediaService(MediaStore(root), config(), sync, provider=provider)


@pytest.mark.parametrize('sync', [None, Mock()])
def test_uncapped_generation_needs_no_ledger_and_keeps_preview_and_no_replay(tmp_path, sync):
    app = service(tmp_path, sync=sync)
    job = app.prepare_generation('Synthetic diagram')
    assert job['image_provider']['spending_mode'] == 'uncapped'
    app.provider.generate.assert_not_called()
    version = app.generate(job['job_id'])
    assert app.store.get_job(job['job_id'])['accounting'] == 'uncapped_provider_billing'
    assert app.store.get_asset(version['asset_id'])['canonical_version_id'] is None
    reopened = service(tmp_path, sync=sync)
    with pytest.raises(ValueError):
        reopened.generate(job['job_id'])
    reopened.provider.generate.assert_not_called()
    if sync is not None:
        assert sync.mock_calls == []


def test_uncapped_timeout_retains_receipt_barrier_and_account_binding(tmp_path):
    app = service(tmp_path / 'media')
    app.provider.generate.side_effect = TimeoutError('private transport detail')
    job = app.prepare_generation('Synthetic diagram')
    state = tmp_path / 'attempts' / 'request-1.json'
    guard = BoardRequestAcquisition(state, 'request-1')
    with pytest.raises(ProviderFailure):
        guard.generate_once(app, job['job_id'], estimate_cents=0)
    assert app.store.get_job(job['job_id'])['phase'] == 'needs_recovery'
    assert BoardRequestAcquisition.unresolved(state.parent)[0]['budget_fingerprint']
    app.config['GOOGLE_IMAGE_API_KEY'] = 'different-account-key'
    with pytest.raises(ValueError, match='original'):
        guard.reconcile(app, job['job_id'], outcome='provider_account_reviewed')
    app.config = config()
    guard.reconcile(app, job['job_id'], outcome='provider_account_reviewed')
    assert BoardRequestAcquisition.unresolved(state.parent) == []
    assert app.provider.generate.call_count == 1


def test_spending_policy_change_invalidates_prepared_job(tmp_path):
    app = service(tmp_path)
    job = app.prepare_generation('Synthetic diagram')
    app.config.update(IMAGE_SPENDING_UNCAPPED='0', GOOGLE_IMAGE_ESTIMATE_1K_AUD_CENTS='24')
    with pytest.raises(ValueError, match='changed'):
        app.generate(job['job_id'])
    app.provider.generate.assert_not_called()


def test_uncapped_board_readiness_and_success_without_estimates_or_server(tmp_path):
    app = service(tmp_path / 'media')
    assert board_image_issues(app.config, budget_available=False) == []
    assert 'no application spending cap' in board_image_readiness(app.config)
    assert 'no application spending cap' in image_readiness(app.config)
    app.config['GOOGLE_IMAGE_ESTIMATE_1K_AUD_CENTS'] = 'unused'
    assert image_snapshot(app.config)['allocation_cents'] == 0
    job = app.prepare_generation('Synthetic diagram')
    guard = BoardRequestAcquisition(tmp_path / 'request-1.json', 'request-1')
    result = guard.generate_once(app, job['job_id'], estimate_cents=0)
    assert result['origin'] == 'generated'
    assert BoardRequestAcquisition.unresolved(tmp_path) == []


@pytest.mark.parametrize('override', [{'LOCAL_ONLY': '1'}, {'IMAGE_GENERATION_ENABLED': '0'}])
def test_uncapped_never_overrides_local_only_or_disabled_generation(tmp_path, override):
    app = service(tmp_path)
    app.config.update(override)
    job = app.prepare_generation('Synthetic diagram')
    with pytest.raises(ValueError):
        app.generate(job['job_id'])
    app.provider.generate.assert_not_called()


def test_opt_in_required_and_uncapped_flag_survives_settings_round_trip(tmp_path, monkeypatch):
    import companion_settings
    monkeypatch.setattr(companion_settings, '_crypt', lambda data, decrypt=False: data)
    companion_settings.save_settings({'IMAGE_SPENDING_UNCAPPED': '1'}, tmp_path)
    assert companion_settings.load_settings(tmp_path)['IMAGE_SPENDING_UNCAPPED'] == '1'
    app = service(tmp_path / 'media')
    del app.config['IMAGE_SPENDING_UNCAPPED']
    job = app.prepare_generation('Synthetic diagram')
    with pytest.raises(ValueError, match='budget'):
        app.generate(job['job_id'])
    app.provider.generate.assert_not_called()
