"""Offline transport, final-output parsing and complete durable Gemini workflows."""
import base64
import json
import io
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemini_images import GeminiImageProvider, check_google_model, ENDPOINT
from image_provider_config import GOOGLE_MODEL, image_snapshot, create_image_provider
from media_providers import ProviderFailure
from media_service import MediaService
from media_store import MediaStore
from gemini_fixtures import fixture, PNG_BASE64

KEY = 'synthetic-google-secret'
CONFIG = {'IMAGE_PROVIDER': 'gemini', 'GOOGLE_IMAGE_API_KEY': KEY,
          'IMAGE_GENERATION_ENABLED': '1', 'GOOGLE_IMAGE_ESTIMATE_1K_AUD_CENTS': '100'}


class Response:
    def __init__(self, payload=None, status=200, raw=None):
        self.status_code = status
        self.headers = {'x-request-id': 'synthetic-http-id'}
        self.body = raw if raw is not None else json.dumps(payload if payload is not None else fixture()).encode()
        self.closed = False

    def iter_content(self, size):
        for offset in range(0, len(self.body), size):yield self.body[offset:offset+size]

    def __enter__(self):return self
    def __exit__(self, *_):self.closed = True


def session(response=None, error=None):
    transport = Mock()
    transport.post = Mock(return_value=response or Response(), side_effect=error)
    transport.get = Mock(return_value=response or Response({'name': 'models/' + GOOGLE_MODEL}))
    return transport


def test_single_stateless_dispatch_header_key_and_actual_provenance():
    transport = session()
    stages = []
    result = GeminiImageProvider(KEY, session=transport).generate('Synthetic image brief', on_stage=stages.append)
    assert result['data'] == base64.b64decode(PNG_BASE64)
    assert result['source'] == {'provider': 'gemini', 'model': GOOGLE_MODEL}
    assert result['mime'] == 'image/png'
    assert result['receipt']['interaction_id'] == 'synthetic-interaction-1'
    assert result['receipt']['usage']['total_tokens'] == 46
    assert result['receipt']['round_trip_seconds'] >= 0
    assert stages == ['Requesting image', 'Receiving image']
    transport.post.assert_called_once()
    args, request = transport.post.call_args
    assert args == (ENDPOINT,)
    assert request['headers']['x-goog-api-key'] == KEY
    assert KEY not in args[0] + json.dumps(request['json'])
    assert request['json'] == {'model': GOOGLE_MODEL, 'input': [{'type': 'text', 'text': 'Synthetic image brief'}],
        'store': False, 'stream': False, 'background': False,
        'generation_config': {'thinking_level': 'medium', 'thinking_summaries': 'none'},
        'response_format': {'type': 'image', 'mime_type': 'image/jpeg',
                            'image_size': '1K', 'aspect_ratio': '1:1'}}
    assert request['allow_redirects'] is False and request['timeout'] == (10, 240) and request['stream'] is True
    assert transport.trust_env is False


def test_reference_is_one_deliberate_image_without_conversation_chaining(tmp_path):
    parent = tmp_path / 'managed-blob'
    parent.write_bytes(base64.b64decode(PNG_BASE64))
    transport = session()
    GeminiImageProvider(KEY, session=transport).generate('Change arrows only', parent=parent,
        options={'size': '2K', 'aspect_ratio': '3:4', 'thinking': 'minimal'})
    payload = transport.post.call_args.kwargs['json']
    assert payload['input'] == [{'type': 'text', 'text': 'Change arrows only'},
                               {'type': 'image', 'mime_type': 'image/png', 'data': PNG_BASE64}]
    assert 'previous_interaction_id' not in payload and 'tools' not in payload
    assert str(parent) not in json.dumps(payload)
    assert payload['response_format']['image_size'] == '2K'
    assert parent.read_bytes() == base64.b64decode(PNG_BASE64)


def test_actual_delivery_mode_rejection_is_avoided_for_generation_and_refinement(tmp_path):
    """The live endpoint rejects explicit delivery despite its OpenAPI enum."""
    transport = session()
    def endpoint(*args, **kwargs):
        if 'delivery' in kwargs['json']['response_format']:
            return Response({'error': {'message': 'Image delivery mode is not supported.'}}, status=400)
        return Response()
    transport.post.side_effect = endpoint
    app = make_service(tmp_path, transport)
    first = app.prepare_generation('Synthetic wildlife photograph')
    parent = app.generate(first['job_id'])
    edit = app.prepare_generation('Change the background only', parent_version_id=parent['version_id'])
    child = app.generate(edit['job_id'])
    assert child['parent_version_id'] == parent['version_id']
    assert transport.post.call_count == 2
    assert all('delivery' not in call.kwargs['json']['response_format'] for call in transport.post.call_args_list)
    assert app.store.get_job(first['job_id'])['phase'] == 'preview_ready'
    assert app.store.get_job(edit['job_id'])['phase'] == 'preview_ready'


@pytest.mark.parametrize('change', ['thought_only', 'last_text', 'two_images', 'mime', 'base64', 'not_image',
                                    'uri_only', 'no_model', 'steps_shape', 'incomplete', 'text_only', 'two_final_steps'])
def test_bad_or_nonfinal_outputs_never_become_saved_images(change):
    payload = fixture()
    image = payload['steps'][-1]['content'][0]
    if change == 'thought_only':payload['steps'] = payload['steps'][:1]
    elif change == 'last_text':payload['steps'].append({'type': 'model_output', 'content': [{'type': 'text', 'text': 'No final image'}]})
    elif change == 'two_images':payload['steps'][-1]['content'].append(dict(image))
    elif change == 'two_final_steps':payload['steps'].append({'type': 'model_output', 'content': [dict(image)]})
    elif change == 'mime':image['mime_type'] = 'image/jpeg'
    elif change == 'base64':image['data'] = 'not-base64!'
    elif change == 'not_image':image['data'] = base64.b64encode(b'not an image').decode()
    elif change == 'uri_only':image.pop('data');image['uri'] = 'https://untrusted.invalid/image'
    elif change == 'no_model':payload.pop('model')
    elif change == 'steps_shape':payload['steps'] = {'type': 'model_output'}
    else:payload = fixture(change)
    transport = session(Response(payload))
    with pytest.raises(ProviderFailure) as caught:
        GeminiImageProvider(KEY, session=transport).generate('Private brief')
    assert transport.post.call_count == 1
    transport.get.assert_not_called()
    assert KEY not in str(caught.value) + json.dumps(caught.value.receipt)
    assert 'Private brief' not in str(caught.value)
    assert caught.value.receipt['round_trip_seconds'] >= 0


@pytest.mark.parametrize('status,outcome', [(302, 'http_error'), (401, 'authentication'),
                                           (403, 'access_denied'), (429, 'quota'), (503, 'http_error')])
def test_http_failures_retain_safe_receipt_and_never_retry(status, outcome):
    response = Response({'error': KEY}, status)
    transport = session(response)
    with pytest.raises(ProviderFailure) as caught:
        GeminiImageProvider(KEY, session=transport).generate('Private brief')
    assert caught.value.receipt['outcome'] == outcome
    assert caught.value.receipt['http_status'] == status
    assert response.closed
    assert KEY not in json.dumps(caught.value.receipt) + str(caught.value)
    assert transport.post.call_count == 1


@pytest.mark.parametrize('response', [Response(raw=b'{broken JSON'), Response(raw=b'[]')])
def test_malformed_response_is_uncertain(response):
    transport = session(response)
    with pytest.raises(ProviderFailure):GeminiImageProvider(KEY, session=transport).generate('Synthetic brief')
    assert transport.post.call_count == 1


def test_response_is_bounded_while_reading_and_closes_transport():
    response = Response()
    with patch('gemini_images.MAX_RESPONSE_BYTES', 20):
        with pytest.raises(ProviderFailure) as caught:
            GeminiImageProvider(KEY, session=session(response)).generate('Synthetic brief')
    assert caught.value.receipt['outcome'] == 'oversized_response'
    assert response.closed


def test_numeric_usage_allowlist_excludes_arbitrary_provider_metadata():
    payload = fixture()
    payload['usage'].update(prompt='Private prompt', secret=KEY, total_thought_tokens=True)
    result = GeminiImageProvider(KEY, session=session(Response(payload))).generate('Synthetic brief')
    assert result['usage'] == {'total_input_tokens': 12, 'total_output_tokens': 34, 'total_tokens': 46}


def test_image_pixel_limit_is_checked_before_saving():
    image = io.BytesIO()
    Image.new('1', (6000, 5000)).save(image, 'PNG')
    payload = fixture()
    payload['steps'][-1]['content'][0]['data'] = base64.b64encode(image.getvalue()).decode()
    with pytest.raises(ProviderFailure) as caught:
        GeminiImageProvider(KEY, session=session(Response(payload))).generate('Synthetic brief')
    assert caught.value.receipt['outcome'] == 'invalid_image_response'


def make_service(tmp_path, transport, **config):
    config = {**CONFIG, **config}
    provider = GeminiImageProvider(KEY, session=transport)
    return MediaService(MediaStore(tmp_path), config, Mock(), provider=provider)


def test_complete_generation_refinement_restart_and_private_receipts(tmp_path):
    transport = session()
    app = make_service(tmp_path, transport)
    stages = []
    prepared = app.prepare_generation('Synthetic water cycle', 'Water cycle')
    parent = app.generate(prepared['job_id'], on_stage=stages.append)
    app.store.set_canonical(parent['asset_id'], parent['version_id'])
    child_job = app.prepare_generation('Change arrows only', 'Revision', parent['version_id'])
    child = app.generate(child_job['job_id'])
    reopened = MediaStore(tmp_path)
    assert reopened.get_asset(parent['asset_id'])['canonical_version_id'] == parent['version_id']
    assert child['parent_version_id'] == parent['version_id']
    job = reopened.generation_job_for_version(child['version_id'])
    assert job['image_provider']['allocation_cents'] == 100
    assert job['provider_receipt']['interaction_id'] == 'synthetic-interaction-1'
    assert job['workflow_seconds'] >= job['provider_receipt']['round_trip_seconds']
    with pytest.raises(ValueError):app.generate(child_job['job_id'])
    assert transport.post.call_count == 2
    assert app.sync.reserve_budget.call_count == 2
    assert stages == ['Reserving image allocation', 'Requesting image', 'Receiving image', 'Preparing preview']
    events = json.dumps(reopened.pending_events())
    for private in ('provider_receipt', 'synthetic-interaction-1', 'total_tokens', KEY, 'Synthetic water cycle'):
        assert private not in events


@pytest.mark.parametrize('mode', ['timeout', 'refusal', 'quota', 'lost_accounting_ack'])
def test_uncertain_dispatches_hold_allocation_and_never_replay_after_restart(tmp_path, mode):
    transport = session(Response(fixture('text_only')) if mode == 'refusal' else Response(status=429) if mode == 'quota' else None,
                        requests.Timeout(KEY) if mode == 'timeout' else None)
    app = make_service(tmp_path, transport)
    if mode == 'lost_accounting_ack':app.sync.commit_budget.side_effect = TimeoutError()
    job = app.prepare_generation('Synthetic brief')
    if mode == 'lost_accounting_ack':
        version = app.generate(job['job_id'])
        assert app.store.get_version(version['version_id'])
    else:
        with pytest.raises(ProviderFailure):app.generate(job['job_id'])
        assert app.store.get_job(job['job_id'])['provider_receipt']['outcome'] in {'uncertain', 'no_final_image', 'quota'}
    restored = MediaService(MediaStore(tmp_path), app.config, app.sync, provider=app.provider)
    restored.recover_interrupted_jobs()
    with pytest.raises(ValueError):restored.generate(job['job_id'])
    assert transport.post.call_count == 1
    app.sync.release_budget.assert_not_called()
    assert KEY not in json.dumps(restored.store.get_job(job['job_id']))


def test_google_size_allocation_never_uses_openai_or_another_resolution():
    config = {**CONFIG, 'IMAGE_ESTIMATE_AUD_CENTS': '900', 'GOOGLE_IMAGE_SIZE': '2K'}
    assert image_snapshot(config)['allocation_cents'] == 0
    config['GOOGLE_IMAGE_ESTIMATE_2K_AUD_CENTS'] = '200'
    assert image_snapshot(config)['allocation_cents'] == 200


def test_saved_image_accounting_reconciliation_never_renders_or_reserves_again(tmp_path):
    transport = session()
    app = make_service(tmp_path, transport)
    app.sync.commit_budget.side_effect = TimeoutError()
    job = app.prepare_generation('Synthetic brief')
    app.generate(job['job_id'])
    app.sync.commit_budget.side_effect = None
    result = app.reconcile_saved_allocation(job['job_id'])
    assert result['phase'] == 'preview_ready'
    assert result['accounting'] == 'allocation_retained_after_reconciliation'
    app.reconcile_saved_allocation(job['job_id'])
    assert transport.post.call_count == 1
    assert app.sync.reserve_budget.call_count == 1
    assert app.sync.commit_budget.call_count == 2
    app.sync.release_budget.assert_not_called()


def test_local_only_blocks_saved_image_accounting_reconciliation(tmp_path):
    app = make_service(tmp_path, session())
    app.sync.commit_budget.side_effect = TimeoutError()
    job = app.prepare_generation('Synthetic brief')
    app.generate(job['job_id'])
    app.config['LOCAL_ONLY'] = '1'
    with pytest.raises(ValueError, match='local-only'):
        app.reconcile_saved_allocation(job['job_id'])
    assert app.sync.commit_budget.call_count == 1


@pytest.mark.parametrize('change', [{'GOOGLE_IMAGE_SIZE': '2K'}, {'GOOGLE_IMAGE_ASPECT_RATIO': '3:4'},
                                    {'GOOGLE_IMAGE_THINKING': 'minimal'}, {'GOOGLE_IMAGE_ESTIMATE_1K_AUD_CENTS': '200'}])
def test_changed_google_options_require_repreparation_before_reservation(tmp_path, change):
    transport = session()
    app = make_service(tmp_path, transport)
    prepared = app.prepare_generation('Synthetic brief')
    app.config.update(change)
    with pytest.raises(ValueError):app.generate(prepared['job_id'])
    app.sync.reserve_budget.assert_not_called();transport.post.assert_not_called()


def test_local_only_blocks_generation_and_metadata_before_transport(tmp_path):
    transport = session()
    app = make_service(tmp_path, transport, LOCAL_ONLY='1')
    prepared = app.prepare_generation('Synthetic brief')
    with pytest.raises(ValueError):app.generate(prepared['job_id'])
    with pytest.raises(ValueError):check_google_model(app.config, session=transport)
    transport.post.assert_not_called();transport.get.assert_not_called()


def test_google_preparation_from_g1_requires_resolution_allocation_repreparation(tmp_path):
    transport = session()
    app = make_service(tmp_path, transport)
    legacy = app.store.create_job('generate', 'Synthetic legacy brief')
    app.store.update_job(legacy['job_id'], 'awaiting_user', image_provider=image_snapshot(CONFIG))
    with pytest.raises(ValueError, match='predates resolution-specific allocations'):
        app.generate(legacy['job_id'])
    transport.post.assert_not_called();app.sync.reserve_budget.assert_not_called()


def test_successful_connection_check_updates_google_readiness_without_claiming_rendering():
    from settings_panel import SettingsPanel
    panel = SettingsPanel.__new__(SettingsPanel)
    panel._closed = False
    panel._image_revision = 3
    panel.check_button = Mock()
    panel.connection_status = Mock()
    panel.image_status = Mock()
    panel.image_status.cget.return_value = 'Google credentials: configured; model access unchecked. Adapter: ready.'
    producer = Mock();producer.get.return_value = 'gemini'
    panel.values = {'IMAGE_PROVIDER': producer}
    panel._connection_finished(3, 'Google model metadata is accessible. Paid rendering remains unverified.')
    assert 'model metadata accessible; rendering unverified' in panel.image_status.configure.call_args.kwargs['text']
    panel.image_status.configure.reset_mock()
    panel._connection_finished(2, 'Google model metadata is accessible.')
    panel.image_status.configure.assert_not_called()


def test_connection_check_is_only_an_explicit_header_authenticated_metadata_get():
    transport = session()
    message = check_google_model(CONFIG, session=transport)
    assert 'Paid rendering and budget availability remain unverified' in message
    transport.post.assert_not_called()
    args, kwargs = transport.get.call_args
    assert args == ('https://generativelanguage.googleapis.com/v1beta/models/' + GOOGLE_MODEL,)
    assert kwargs['headers'] == {'x-goog-api-key': KEY}
    assert kwargs['allow_redirects'] is False
    assert KEY not in args[0]


def test_factory_constructs_gemini_without_an_openai_fallback():
    transport = session()
    adapter = create_image_provider(image_snapshot(CONFIG), CONFIG, session=transport)
    assert isinstance(adapter, GeminiImageProvider)
    transport.post.assert_not_called()


def test_two_instances_can_only_claim_one_provider_dispatch(tmp_path):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    transport = session()
    first = make_service(tmp_path, transport)
    second = make_service(tmp_path, transport)
    job = first.prepare_generation('Synthetic brief')
    barrier = threading.Barrier(2)
    for app in (first, second):
        original = app.store.claim_job
        def claim(job_id, expected, phase, _original=original, **fields):
            if phase == 'reserving':barrier.wait(timeout=5)
            return _original(job_id, expected, phase, **fields)
        app.store.claim_job = claim
    def generate(app):
        try:return app.generate(job['job_id'])
        except ValueError:return None
    with ThreadPoolExecutor(2) as executor:
        results = list(executor.map(generate, (first, second)))
    assert sum(result is not None for result in results) == 1
    assert transport.post.call_count == 1
    assert first.sync.reserve_budget.call_count + second.sync.reserve_budget.call_count == 1
    assert first.store.get_job(job['job_id'])['phase'] == 'preview_ready'


@pytest.mark.parametrize('response', [Response(status=401), Response(status=302),
                                     Response({'name': 'models/unexpected'}), Response(raw=b'{broken')])
def test_metadata_check_failures_are_sanitised_and_do_not_generate(response):
    transport = session(response)
    with pytest.raises(ValueError) as caught:check_google_model(CONFIG, session=transport)
    assert KEY not in str(caught.value)
    assert transport.get.call_count == 1
    transport.post.assert_not_called()
