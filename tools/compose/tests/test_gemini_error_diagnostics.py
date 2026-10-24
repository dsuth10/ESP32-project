"""HTTP rejection diagnostics must be useful without copying private response text."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemini_images import GeminiImageProvider
from media_providers import ProviderFailure
from test_gemini_images import Response, session, KEY


def test_rejected_request_keeps_safe_rpc_status_and_field_names():
    prompt = 'Private synthetic image brief'
    payload = {'error': {'code': 400, 'status': 'INVALID_ARGUMENT',
        'message': f'Invalid request with {KEY} and {prompt}',
        'details': [
            {'@type': 'type.googleapis.com/google.rpc.BadRequest', 'fieldViolations': [
                {'field': 'response_format.delivery', 'description': f'private detail {KEY}'},
                {'field': KEY, 'description': 'must not retain arbitrary values'}]},
            {'@type': 'type.googleapis.com/google.rpc.ErrorInfo', 'reason': 'UNSUPPORTED_PARAMETER',
             'domain': 'private.invalid', 'metadata': {'key': KEY, 'prompt': prompt}}]}}
    transport = session(Response(payload, status=400))
    with pytest.raises(ProviderFailure) as caught:
        GeminiImageProvider(KEY, session=transport).generate(prompt)
    receipt = caught.value.receipt
    assert receipt['provider_error_status'] == 'INVALID_ARGUMENT'
    assert receipt['provider_error_code'] == 400
    assert receipt['provider_error_fields'] == ['response_format.delivery']
    assert receipt['provider_error_reason'] == 'UNSUPPORTED_PARAMETER'
    assert KEY not in str(receipt)
    assert prompt not in str(receipt)
    assert 'private detail' not in str(receipt)
    assert receipt['provider_error_summary'] == 'Invalid request with <REDACTED> and <REDACTED>'
    transport.post.assert_called_once()


def test_unknown_name_diagnostic_keeps_only_recognised_request_fields():
    payload = {'error': {'code': 400, 'status': 'INVALID_ARGUMENT',
                         'message': 'Invalid JSON payload. Unknown name "delivery" at response_format.'}}
    with pytest.raises(ProviderFailure) as caught:
        GeminiImageProvider(KEY, session=session(Response(payload, status=400))).generate('Synthetic brief')
    assert caught.value.receipt['provider_error_fields'] == ['delivery']
    assert 'message' not in caught.value.receipt


def test_unreadable_or_oversized_error_body_still_remains_one_held_attempt():
    transport = session(Response(status=400, raw=b'not JSON' * 20_000))
    with pytest.raises(ProviderFailure) as caught:
        GeminiImageProvider(KEY, session=transport).generate('Synthetic brief')
    assert caught.value.receipt['http_status'] == 400
    assert caught.value.receipt['outcome'] == 'http_error'
    transport.post.assert_called_once()


def test_error_metadata_survives_service_recovery_without_retry_or_release(tmp_path):
    from test_gemini_images import make_service
    payload = {'error': {'code': 400, 'status': 'INVALID_ARGUMENT',
                         'message': 'Invalid JSON payload. Unknown name "delivery" at response_format.'}}
    transport = session(Response(payload, status=400))
    app = make_service(tmp_path, transport)
    job = app.prepare_generation('Private synthetic brief')
    with pytest.raises(ProviderFailure):app.generate(job['job_id'])
    stored = app.store.get_job(job['job_id'])
    assert stored['phase'] == 'needs_recovery'
    assert stored['provider_receipt']['provider_error_status'] == 'INVALID_ARGUMENT'
    assert stored['provider_receipt']['provider_error_fields'] == ['delivery']
    assert KEY not in str(stored)
    app.sync.release_budget.assert_not_called()
    transport.post.assert_called_once()


def test_error_summary_redacts_keys_paths_urls_and_is_bounded():
    prompt = 'Private synthetic image brief'
    message = (f'Invalid {KEY}; {prompt}; C:\\private\\reference.png; /private/reference.png; '
               f'https://private.invalid/?key={KEY}; ' + 'x' * 2000)
    with pytest.raises(ProviderFailure) as caught:
        GeminiImageProvider(KEY, session=session(Response({'error': {'message': message}}, status=400))).generate(prompt)
    summary = caught.value.receipt['provider_error_summary']
    assert len(summary) <= 500
    assert KEY not in summary and prompt not in summary
    assert 'reference.png' not in summary and 'private.invalid' not in summary
    assert '<REDACTED>' in summary
