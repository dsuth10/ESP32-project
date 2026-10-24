"""Offline routing, migration and frozen-request safety checks. No provider calls."""
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import companion_settings as settings
from config_loader import load_env_config
from image_provider_config import (image_snapshot, image_readiness, create_image_provider,
                                   validate_options, GOOGLE_MODEL)
from media_service import MediaService
from media_store import MediaStore
from test_media_service import png, service


def test_legacy_settings_keep_openai_and_exact_model():
    snapshot = image_snapshot({'IMAGE_MODEL': 'existing-model'})
    assert snapshot['provider'] == 'openai'
    assert snapshot['model'] == 'existing-model'
    assert snapshot['options'] == {'size': '1024x1024', 'aspect_ratio': '1:1', 'quality': 'high'}


def test_factory_routes_openai_without_changing_payload():
    config = {'OPENAI_API_KEY': 'offline-secret', 'IMAGE_MODEL': 'existing-model'}
    session = Mock()
    adapter = create_image_provider(image_snapshot(config), config, session=session)
    assert adapter.model == 'existing-model'
    assert adapter.key == 'offline-secret'
    session.post.assert_not_called()


def test_google_is_explicit_and_never_borrows_openai_allocation_or_falls_back(tmp_path):
    app = MediaService(MediaStore(tmp_path), {'IMAGE_PROVIDER': 'gemini', 'IMAGE_GENERATION_ENABLED': '1',
        'GOOGLE_IMAGE_API_KEY': 'offline-secret', 'IMAGE_ESTIMATE_AUD_CENTS': '100'}, Mock())
    job = app.prepare_generation('Offline synthetic brief')
    assert job['image_provider']['model'] == GOOGLE_MODEL
    with patch('media_providers.OpenAIImageProvider') as openai:
        with pytest.raises(ValueError, match='allocation'):
            app.generate(job['job_id'])
    openai.assert_not_called()
    app.sync.reserve_budget.assert_not_called()
    assert app.store.get_job(job['job_id'])['provider_dispatched'] is False


@pytest.mark.parametrize('provider,options', [
    ('openai', {'size': '1K'}), ('openai', {'aspect_ratio': '3:4'}),
    ('openai', {'quality': 'low'}), ('gemini', {'thinking': 'unknown'}),
    ('gemini', {'search': True}), ('gemini', {'size': '8K'}),
])
def test_unsupported_output_options_are_refused(provider, options):
    with pytest.raises(ValueError):
        validate_options(provider, options)


def test_unsupported_provider_is_not_an_implicit_openai_request():
    with pytest.raises(ValueError):
        image_snapshot({'IMAGE_PROVIDER': 'unknown'})


@pytest.mark.parametrize('changed', [
    {'IMAGE_PROVIDER': 'gemini'}, {'IMAGE_MODEL': 'another-model'}, {'IMAGE_ESTIMATE_AUD_CENTS': '200'},
])
def test_changed_settings_never_redirect_a_prepared_job(tmp_path, changed):
    app = service(tmp_path)
    job = app.prepare_generation('Offline synthetic brief')
    before = json.loads(json.dumps(job['image_provider']))
    app.config.update(changed)
    with pytest.raises(ValueError):
        app.generate(job['job_id'])
    assert app.store.get_job(job['job_id'])['image_provider'] == before
    app.provider.generate.assert_not_called()
    app.sync.reserve_budget.assert_not_called()


def test_legacy_undispatched_job_requires_repreparation(tmp_path):
    app = service(tmp_path)
    job = app.store.create_job('generate', 'Legacy brief')
    app.store.update_job(job['job_id'], 'awaiting_user')
    with pytest.raises(ValueError, match='legacy.*Prepare it again'):
        app.generate(job['job_id'])
    app.provider.generate.assert_not_called()
    app.sync.reserve_budget.assert_not_called()


def test_restart_keeps_frozen_choice_allocation_and_single_dispatch(tmp_path):
    app = service(tmp_path)
    job = app.prepare_generation('Offline brief')
    reopened = MediaService(MediaStore(tmp_path), app.config, app.sync, provider=app.provider)
    reopened.generate(job['job_id'])
    with pytest.raises(ValueError):
        reopened.generate(job['job_id'])
    assert app.provider.generate.call_count == 1
    assert app.provider.generate.call_args.kwargs['options'] == job['image_provider']['options']
    app.sync.reserve_budget.assert_called_once_with(job['job_id'], 100)


def test_cross_provider_refinement_requires_deliberate_transfer(tmp_path):
    app = service(tmp_path, IMAGE_PROVIDER='gemini')
    parent = app.store.import_bytes(png(), 'Synthetic parent', source={'provider': 'openai'})
    with pytest.raises(ValueError, match='Confirm sending'):
        app.prepare_generation('Change arrows', parent_version_id=parent['version_id'])
    assert app.store.list_jobs() == []
    job = app.prepare_generation('Change arrows', parent_version_id=parent['version_id'], allow_cross_provider=True)
    assert job['parent_version_id'] == parent['version_id']
    assert app.store.blob_path(parent['sha256']).read_bytes() == png()


def test_missing_prepared_reference_never_becomes_unreferenced_generation(tmp_path):
    app = service(tmp_path)
    parent = app.store.import_bytes(png(), 'Synthetic parent')
    job = app.prepare_generation('Change arrows', parent_version_id=parent['version_id'])
    with patch.object(app.store, 'get_version', return_value=None):
        with pytest.raises(ValueError, match='reference image is unavailable'):
            app.generate(job['job_id'])
    app.provider.generate.assert_not_called()
    app.sync.reserve_budget.assert_not_called()


def test_google_key_uses_protected_storage_and_does_not_replace_openai(tmp_path):
    def crypt(data, decrypt=False):
        return data[7:] if decrypt else b'SEALED:' + data
    with patch.object(settings, '_crypt', side_effect=crypt):
        settings.save_settings({'OPENAI_API_KEY': 'old-secret', 'IMAGE_MODEL': 'existing-model'}, tmp_path)
        settings.save_settings({'IMAGE_PROVIDER': 'gemini', 'GOOGLE_IMAGE_MODEL': GOOGLE_MODEL,
                                'GOOGLE_IMAGE_API_KEY': 'google-secret', 'GOOGLE_IMAGE_SIZE': '2K',
                                'GOOGLE_IMAGE_ASPECT_RATIO': '3:4', 'GOOGLE_IMAGE_THINKING': 'minimal',
                                'GOOGLE_IMAGE_ESTIMATE_2K_AUD_CENTS': '200'}, tmp_path)
        loaded = settings.load_settings(tmp_path)
        settings.save_settings({'IMAGE_PROVIDER': 'openai'}, tmp_path)
        assert settings.load_settings(tmp_path)['GOOGLE_IMAGE_API_KEY'] == 'google-secret'
    assert loaded['OPENAI_API_KEY'] == 'old-secret'
    assert loaded['IMAGE_MODEL'] == 'existing-model'
    assert loaded['GOOGLE_IMAGE_API_KEY'] == 'google-secret'
    assert image_snapshot(loaded)['options'] == {'size': '2K', 'aspect_ratio': '3:4', 'thinking': 'minimal'}
    assert image_snapshot(loaded)['allocation_cents'] == 200
    assert 'secret' not in (tmp_path / 'settings.json').read_text()


def test_google_key_is_never_loaded_from_environment_or_plain_file(tmp_path):
    (tmp_path / 'compose.env').write_text('GOOGLE_IMAGE_API_KEY=plaintext-secret\n')
    with patch('config_loader.fallback_env_paths', return_value=[tmp_path / 'compose.env']), \
         patch.dict('os.environ', {'GOOGLE_IMAGE_API_KEY': 'process-secret'}):
        assert 'GOOGLE_IMAGE_API_KEY' not in load_env_config(tmp_path, settings_loader=lambda: {})
        loaded = load_env_config(tmp_path, settings_loader=lambda: {'GOOGLE_IMAGE_API_KEY': 'sealed-secret'})
    assert loaded['GOOGLE_IMAGE_API_KEY'] == 'sealed-secret'


def test_snapshot_and_sync_payload_never_contain_keys(tmp_path):
    app = service(tmp_path, GOOGLE_IMAGE_API_KEY='private-google-key', OPENAI_API_KEY='private-openai-key')
    job = app.prepare_generation('Synthetic private brief')
    app.generate(job['job_id'])
    durable = json.dumps(app.store.get_job(job['job_id']))
    outgoing = json.dumps(app.store.pending_events())
    for secret in ('private-google-key', 'private-openai-key'):
        assert secret not in durable + outgoing
    assert 'Synthetic private brief' not in outgoing
    assert 'image_provider' not in outgoing


def test_readiness_separates_configuration_adapter_policy_and_budget():
    state = image_readiness({'IMAGE_PROVIDER': 'gemini', 'GOOGLE_IMAGE_API_KEY': 'private-key', 'LOCAL_ONLY': '1'})
    assert 'model access unchecked' in state
    assert 'Adapter: ready' in state
    assert 'blocked by local-only mode' in state
    assert 'Budget: not checked' in state
    assert 'private-key' not in state


def test_g1_openai_preparation_keeps_its_snapshot_compatibility(tmp_path):
    app = service(tmp_path)
    job = app.store.create_job('generate', 'Synthetic legacy OpenAI brief')
    app.store.update_job(job['job_id'], 'awaiting_user', image_provider=image_snapshot(app.config))
    app.generate(job['job_id'])
    assert app.store.get_job(job['job_id'])['phase'] == 'preview_ready'
    app.provider.generate.assert_called_once()
