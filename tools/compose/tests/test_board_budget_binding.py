"""Paid-attempt recovery identity is durable in its original atomic claim."""
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_resource_policy
from board_resource_policy import BoardRequestAcquisition
from image_provider_config import image_snapshot


def service(config, job):
    return SimpleNamespace(config=dict(config), store=SimpleNamespace(get_job=lambda _: dict(job)), generate=Mock())


def fixtures():
    config = {'IMAGE_PROVIDER': 'gemini', 'IMAGE_GENERATION_ENABLED': '1', 'LOCAL_ONLY': '0',
              'GOOGLE_IMAGE_ESTIMATE_1K_AUD_CENTS': '24',
              'MEDIA_SERVER_URL': 'https://original-budget.invalid', 'MEDIA_SERVER_TOKEN': 'synthetic-original-token'}
    snapshot = image_snapshot(config)
    job = {'job_id': 'original-job', 'phase': 'awaiting_user', 'kind': 'generate',
           'image_provider': snapshot, 'image_settings': snapshot}
    return config, job


def test_claim_pins_accounting_identity_before_dispatch_and_retains_it_for_uncertainty(tmp_path):
    config, job = fixtures(); media = service(config, job)
    path = tmp_path / 'request-A.json'
    expected = hashlib.sha256((config['MEDIA_SERVER_URL'] + '\0' + config['MEDIA_SERVER_TOKEN']).encode()).hexdigest()
    def dispatch(*args, **kwargs):
        saved = json.loads(path.read_text())
        assert saved['status'] == 'claimed'
        assert saved['budget_fingerprint'] == expected
        assert saved['job_id'] == 'original-job'
        raise TimeoutError('synthetic uncertain response')
    media.generate.side_effect = dispatch
    with pytest.raises(TimeoutError):
        BoardRequestAcquisition(path, 'request-A').generate_once(media, 'original-job', estimate_cents=24)
    value = json.loads(path.read_text())
    assert value['status'] == 'uncertain' and value['budget_fingerprint'] == expected
    assert config['MEDIA_SERVER_URL'] not in path.read_text()
    assert config['MEDIA_SERVER_TOKEN'] not in path.read_text()
    assert BoardRequestAcquisition.unresolved(tmp_path)[0]['budget_fingerprint'] == expected


def test_reconciliation_cannot_use_another_budget_account(tmp_path):
    config, job = fixtures(); media = service(config, job)
    path = tmp_path / 'request-A.json'; guard = BoardRequestAcquisition(path, 'request-A')
    media.generate.side_effect = TimeoutError('synthetic')
    with pytest.raises(TimeoutError):
        guard.generate_once(media, 'original-job', estimate_cents=24)
    original = path.read_bytes()
    job['phase'] = 'needs_recovery'
    changed = service({**config, 'MEDIA_SERVER_TOKEN': 'synthetic-different-account'}, job)
    with pytest.raises(ValueError, match='original shared budget'):
        guard.reconcile(changed, 'original-job', outcome='provider_account_reviewed')
    assert path.read_bytes() == original
    restored = service(config, job)
    result = guard.reconcile(restored, 'original-job', outcome='provider_account_reviewed')
    assert result['status'] == 'reconciled'
    assert result['budget_fingerprint'] == json.loads(original)['budget_fingerprint']


def test_failure_to_durably_create_claim_never_dispatches(tmp_path, monkeypatch):
    config, job = fixtures(); media = service(config, job)
    def denied(*args):
        raise OSError('synthetic local write denial')
    monkeypatch.setattr(board_resource_policy, '_create_claim', denied)
    with pytest.raises(OSError):
        BoardRequestAcquisition(tmp_path / 'request-A.json', 'request-A').generate_once(media, 'original-job', estimate_cents=24)
    media.generate.assert_not_called()


def test_invalid_accounting_fingerprint_blocks_recovery_scan(tmp_path):
    path = tmp_path / 'request-A.json'
    path.write_text(json.dumps({'schema': 1, 'request_id': 'request-A', 'job_id': 'original-job',
                                'status': 'uncertain', 'budget_fingerprint': 'invalid'}))
    with pytest.raises(ValueError, match='accounting identity'):
        BoardRequestAcquisition.unresolved(tmp_path)


def test_local_legacy_review_requires_exact_original_generate_job_and_explicit_confirmation(tmp_path):
    config, job = fixtures(); job['phase'] = 'needs_recovery'
    store = service(config, job).store
    path = tmp_path / 'request-A.json'
    original = {'schema': 1, 'request_id': 'request-A', 'job_id': 'original-job', 'status': 'uncertain'}
    path.write_text(json.dumps(original)); guard = BoardRequestAcquisition(path, 'request-A')
    with pytest.raises(ValueError, match='Confirm review'):
        guard.reconcile_legacy_local(store, 'original-job', outcome='provider_account_reviewed')
    with pytest.raises(ValueError, match='Select the unresolved job'):
        guard.reconcile_legacy_local(store, 'another-job', outcome='provider_account_reviewed', original_outcome_reviewed=True)
    job['kind'] = 'refine'
    with pytest.raises(ValueError, match='existing media job'):
        guard.reconcile_legacy_local(store, 'original-job', outcome='provider_account_reviewed', original_outcome_reviewed=True)
    assert json.loads(path.read_text()) == original


def test_modern_bound_receipt_cannot_use_legacy_local_review(tmp_path):
    config, job = fixtures(); job['phase'] = 'needs_recovery'
    path = tmp_path / 'request-A.json'
    path.write_text(json.dumps({'schema': 1, 'request_id': 'request-A', 'job_id': 'original-job',
        'status': 'uncertain', 'budget_fingerprint': BoardRequestAcquisition._budget_fingerprint(config)}))
    with pytest.raises(ValueError, match='known service identity'):
        BoardRequestAcquisition(path, 'request-A').reconcile_legacy_local(service(config, job).store,
            'original-job', outcome='provider_account_reviewed', original_outcome_reviewed=True)
