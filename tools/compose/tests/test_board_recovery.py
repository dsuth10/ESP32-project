"""Offline recovery storage/transport contracts; no remote services are used."""
import copy
import hashlib
import json
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_agent import BoardAgentController, result_envelope
from board_model import canonical_json
from board_recovery import BoardRecoveryStore, BoardRecoveryError, MAX_RECORD_BYTES
from board_session import BoardSession


@pytest.fixture
def saved(tmp_path):
    session = BoardSession()
    composer = lambda *_: None
    composer.remote = False
    controller = BoardAgentController(session, composer=composer)
    prepared = controller.prepare('Explain evaporation in Australian English.')
    view = session.teacher_view()
    baseline = {key: copy.deepcopy(view[key]) for key in ('document', 'page_id', 'revision')}
    store = BoardRecoveryStore(tmp_path / 'private-recovery')
    record = store.create(prepared, baseline)
    yield store, prepared, baseline, record
    controller.close()


class Service:
    config = {'LOCAL_ONLY': False}

    def __init__(self, prepared, *, status='running', receipt=True):
        self.identity = str(uuid.uuid4())
        self.selection = dict(request_id=self.identity, task=prepared['task'], context=prepared['context'],
                              status=status, receipt_exists=receipt, run_id='run-1' if receipt else None)
        self.calls = []
        self.next_state = None

    def preview(self, request_id):
        assert request_id == self.identity
        self.calls.append('preview')
        return copy.deepcopy(self.selection)

    def poll(self, request_id):
        assert request_id == self.identity
        self.calls.append('poll')
        if self.next_state:
            self.selection.update(self.next_state)
        return copy.deepcopy(self.selection)

    def stop(self, request_id):
        assert request_id == self.identity
        self.calls.append('stop')
        self.selection.update(status='stopping')
        return copy.deepcopy(self.selection)

    def prepare(self, *_):
        pytest.fail('Recovery must never prepare a task.')

    def submit(self, *_):
        pytest.fail('Recovery must never dispatch a task.')


def bind(store, prepared, **options):
    service = Service(prepared, **options)
    store.bind(prepared['request_id'], service.identity)
    return service


def output(prepared):
    return canonical_json(result_envelope(prepared)).decode('utf-8')


def test_saved_request_reopens_with_exact_private_context_and_baseline(saved):
    store, prepared, baseline, record = saved
    reopened = BoardRecoveryStore(store.root)
    assert reopened.get(prepared['request_id']) == record
    assert record['prepared'] == prepared and record['baseline'] == baseline
    prepared['effective_context']['instructions'] = 'changed local copy'
    assert reopened.get(record['request_id']) == record
    assert reopened.list_requests() == [record]


def test_create_idempotent_but_different_baseline_or_context_rejected(saved):
    store, prepared, baseline, record = saved
    assert store.create(prepared, baseline) == record
    changed = copy.deepcopy(baseline)
    changed['document']['title'] = 'Another title'
    with pytest.raises(BoardRecoveryError, match='another immutable'):
        store.create(prepared, changed)
    changed = copy.deepcopy(prepared)
    changed['task'] += 'changed'
    with pytest.raises(BoardRecoveryError):
        store.create(changed, baseline)


def test_binding_and_run_and_result_identities_cannot_be_replaced(saved):
    store, prepared, _, _ = saved
    identity = prepared['request_id']
    store.bind(identity, 'hermes-original')
    store.bind(identity, 'hermes-original')
    with pytest.raises(BoardRecoveryError, match='another Hermes'):
        store.bind(identity, 'hermes-replacement')
    store.update(identity, result=output(prepared), run_id='run-1')
    for fields in ({'result': None}, {'result': '{}'}, {'run_id': 'run-2'}, {'prepared': {}}):
        with pytest.raises(BoardRecoveryError):
            store.update(identity, **fields)


@pytest.mark.parametrize('bad_result', ['[]', 'not JSON', '{"x":NaN}', '{"x":1,"x":2}', '{"text":"'+'x'*20001+'"}'])
def test_results_are_bounded_finite_duplicate_free_objects(saved, bad_result):
    store, prepared, _, _ = saved
    with pytest.raises(BoardRecoveryError):
        store.update(prepared['request_id'], result=bad_result)
    assert store.get(prepared['request_id'])['result'] is None


def test_complete_existing_task_recovers_result_without_dispatch(saved):
    store, prepared, _, _ = saved
    service = bind(store, prepared)
    service.next_state = dict(status='completed', text=output(prepared))
    record = BoardRecoveryStore(store.root).refresh(prepared['request_id'], service)
    assert service.calls == ['preview', 'poll', 'preview']
    assert record['result'] == output(prepared)
    assert record['run_id'] == 'run-1' and record['status'] == 'completed'
    assert record['publication_status'] == 'pending'
    assert store.get(prepared['request_id']) == record


@pytest.mark.parametrize('status', ['prepared', 'dispatching', 'uncertain', 'http_error'])
def test_no_receipt_never_polled_or_replayed(saved, status):
    store, prepared, _, _ = saved
    service = bind(store, prepared, status=status, receipt=False)
    record = store.refresh(prepared['request_id'], service)
    assert service.calls == ['preview']
    assert record['status'] == 'needs_attention' and record['result'] is None
    assert store.get(prepared['request_id'])['hermes_request_id'] == service.identity


def test_uncertain_task_with_receipt_polled_using_original_identity(saved):
    store, prepared, _, _ = saved
    service = bind(store, prepared, status='uncertain')
    service.next_state = {'status': 'running'}
    assert store.refresh(prepared['request_id'], service)['status'] == 'running'
    assert service.calls == ['preview', 'poll', 'preview']


def test_selection_mismatch_stops_before_network(saved):
    store, prepared, _, _ = saved
    service = bind(store, prepared)
    service.selection['context'] = '{}'
    assert store.refresh(prepared['request_id'], service)['status'] == 'needs_attention'
    assert service.calls == ['preview']


def test_local_only_makes_no_service_calls_and_keeps_saved_result(saved):
    store, prepared, _, _ = saved
    service = bind(store, prepared)
    store.update(prepared['request_id'], result=output(prepared), status='completed')
    for operation in (store.refresh, store.stop):
        assert operation(prepared['request_id'], service, local_only=True)['result'] == output(prepared)
    service.config = {'LOCAL_ONLY': 'true'}
    assert store.refresh(prepared['request_id'], service)['status'] == 'local_only'
    assert service.calls == []


def test_cancel_remote_reports_unconfirmed_until_terminal_receipt(saved):
    store, prepared, _, _ = saved
    service = bind(store, prepared)
    record = store.stop(prepared['request_id'], service)
    assert 'stop' in service.calls and record['status'] == 'stopping'
    assert record['publication_status'] == 'pending'


def test_cancel_without_run_receipt_does_not_attempt_remote_stop(saved):
    store, prepared, _, _ = saved
    service = bind(store, prepared, receipt=False)
    assert store.stop(prepared['request_id'], service)['status'] == 'needs_attention'
    assert service.calls == ['preview']


def test_publication_barrier_survives_refresh_restart_and_late_worker(saved):
    store, prepared, _, _ = saved
    identity = prepared['request_id']
    service = bind(store, prepared)
    store.update(identity, publication_status='applying')
    store = BoardRecoveryStore(store.root)
    assert store.update(identity, publication_status='failed')['publication_status'] == 'applying'
    service.next_state = {'status': 'completed', 'text': output(prepared)}
    assert store.refresh(identity, service)['publication_status'] == 'applying'
    store.update(identity, publication_status='applied')
    for status in ('cancelled', 'pending', 'review', 'failed'):
        assert store.update(identity, publication_status=status)['publication_status'] == 'applied'


def test_publication_claim_exclusive_across_store_instances(saved):
    store, prepared, _, _ = saved
    identity = prepared['request_id']
    other = BoardRecoveryStore(store.root)
    store.update(identity, publication_status='review')
    assert store.claim_publication(identity)['publication_status'] == 'applying'
    with pytest.raises(BoardRecoveryError, match='already claimed'):
        other.claim_publication(identity)
    other.update(identity, publication_status='applied')
    with pytest.raises(BoardRecoveryError, match='already claimed'):
        store.claim_publication(identity)


@pytest.mark.parametrize('publication', ['cancelled', 'stale', 'failed'])
def test_publication_claim_rejects_terminal_local_outcome(saved, publication):
    store, prepared, _, _ = saved
    identity = prepared['request_id']
    store.update(identity, publication_status=publication)
    assert store.update(identity, publication_status='review')['publication_status'] == publication
    assert store.update(identity, publication_status='pending')['publication_status'] == publication
    with pytest.raises(BoardRecoveryError):
        store.claim_publication(identity)


def test_corrupt_record_visible_but_unusable_and_never_repaired_implicitly(saved):
    store, prepared, _, _ = saved
    path = store.root / (prepared['request_id']+'.json')
    data = json.loads(path.read_text(encoding='utf-8'))
    data['record']['prepared']['task'] = 'tampered'
    raw = json.dumps(data)
    path.write_text(raw, encoding='utf-8')
    with pytest.raises(BoardRecoveryError, match='checksum'):
        store.get(prepared['request_id'])
    listed = store.list_requests()
    assert len(listed) == 1 and listed[0]['invalid'] is True
    assert path.read_text(encoding='utf-8') == raw


def test_oversized_and_duplicate_json_entries_refused(saved):
    store, prepared, _, _ = saved
    path = store.root / (prepared['request_id']+'.json')
    path.write_bytes(b'x'*(MAX_RECORD_BYTES+1))
    with pytest.raises(BoardRecoveryError, match='size limit'):
        store.get(prepared['request_id'])
    path.write_text('{"record":{},"record":{}}', encoding='utf-8')
    with pytest.raises(BoardRecoveryError):
        store.get(prepared['request_id'])


def test_interrupted_atomic_write_keeps_previous_record(saved, monkeypatch):
    store, prepared, _, record = saved
    def fail(*_):
        raise OSError('simulated interrupted replace')
    monkeypatch.setattr('board_recovery.os.replace', fail)
    with pytest.raises(OSError):
        store.update(prepared['request_id'], status='running')
    assert store.get(prepared['request_id']) == record
    assert not list(store.root.glob('.writing-*'))


def test_threaded_updates_do_not_lose_immutable_binding_or_result(saved):
    store, prepared, _, _ = saved
    identity = prepared['request_id']
    store.bind(identity, 'hermes-original')
    with ThreadPoolExecutor(max_workers=2) as executor:
        result = executor.submit(store.update, identity, result=output(prepared))
        publication = executor.submit(store.update, identity, publication_status='cancelled')
        result.result(); publication.result()
    record = store.get(identity)
    assert record['hermes_request_id'] == 'hermes-original'
    assert record['result'] == output(prepared) and record['publication_status'] == 'cancelled'


def test_reopened_stores_share_normalised_process_lock(saved):
    store, prepared, _, _ = saved
    alias = store.root / '..' / store.root.name
    other = BoardRecoveryStore(alias)
    assert store._lock is other._lock
    stores = [store, other]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(stores[index % 2].update, prepared['request_id'], status='running')
                   for index in range(40)]
        for future in futures:
            assert future.result()['status'] == 'running'
    assert other.get(prepared['request_id'])['prepared'] == prepared


@pytest.mark.parametrize('identity', ['../outside', '', 'a/b', 'a\\b', 'a'*161])
def test_unsafe_request_paths_refused(saved, identity):
    store, _, _, _ = saved
    with pytest.raises(BoardRecoveryError):
        store.get(identity)


def test_missing_request_distinct_from_corruption(saved):
    store, _, _, _ = saved
    with pytest.raises(FileNotFoundError):
        store.get(str(uuid.uuid4()))
