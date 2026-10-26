"""Offline adversarial restart checks across Board recovery, controller and stores."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import uuid
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from board_agent import BoardAgentController, BoardAgentError, result_envelope
from board_export import export_lesson
from board_model import BoardModel, BoardConflictError, new_object, new_page
from board_recovery import BoardRecoveryStore
from board_session import BoardSession
from board_store import BoardStore
from media_store import MediaStore


def apply(session, commands):
    view = session.teacher_view()
    return session.teacher_apply(commands, expected_revision=view['revision'], expected_token=view['token'])


def no_composition(*args, **kwargs):
    raise AssertionError('Recovery must never dispatch a fresh composition.')


no_composition.remote = False


def controller(session, recovery):
    return BoardAgentController(session, composer=no_composition, recovery_store=recovery)


@pytest.fixture
def saved_request(tmp_path):
    """A real saved lesson and completed remote output, not yet published locally."""
    root = tmp_path / 'lesson'
    store = BoardStore(root)
    session = BoardSession(store=store)
    page_id = session.teacher_view()['page_id']
    obj = new_object('text', text='Original explanation', x=80, y=80, width=700, height=150)
    other = new_page('Another teaching page')
    apply(session, [{'op': 'add_object', 'page_id': page_id, 'object': obj},
                    {'op': 'add_page', 'page': other}])
    session.save(expected_token=session.teacher_view()['token'])
    recovery = BoardRecoveryStore(root / 'board-requests')
    original = controller(session, recovery)
    prepared = original.prepare('PRIVATE_RECOVERY_PROMPT Explain evaporation')
    view = session.teacher_view()
    baseline = {key: copy.deepcopy(view[key]) for key in ('document', 'page_id', 'revision')}
    recovery.create(prepared, baseline)
    recovery.bind(prepared['request_id'], str(uuid.uuid4()))
    result = result_envelope(prepared, commands=[{'op': 'update_object', 'page_id': page_id,
        'object_id': obj['id'], 'changes': {'text': 'Warmth causes evaporation.'}}])
    recovery.update(prepared['request_id'], status='completed', result=json.dumps(result), run_id='existing-run-1')
    yield {'root': root, 'session': session, 'store': store, 'recovery': recovery,
           'prepared': prepared, 'result': result, 'id': prepared['request_id'],
           'page_id': page_id, 'object_id': obj['id'], 'other_page_id': other['id']}
    original.close()


def reopen(case):
    session = BoardSession.open(BoardStore(case['root']))
    recovery = BoardRecoveryStore(case['root'] / 'board-requests')
    return session, recovery, controller(session, recovery)


def recover(case, session=None):
    session, recovery, current = reopen(case) if session is None else (
        session, case['recovery'], controller(session, case['recovery']))
    request_id = current.recover(recovery.get(case['id']))
    return session, recovery, current, request_id


def test_restart_uses_exact_existing_output_explicit_preview_then_one_undo(saved_request):
    case = saved_request
    session, recovery, current = reopen(case)
    before = session.teacher_view()
    assert before['token'] != case['session'].teacher_view()['token']
    request_id = current.recover(recovery.get(case['id']))
    state = current.snapshot(request_id)
    assert state['status'] == 'awaiting_confirmation'
    assert state['requires_confirmation'] is True
    assert session.teacher_view() == before
    assert current.preview(request_id) is not None
    applied = current.confirm(request_id, state['proposal_digest'])
    assert applied['status'] == 'applied'
    after = session.teacher_view()
    assert after['revision'] == before['revision'] + 1
    assert after['document']['pages'][0]['objects'][0]['text'] == 'Warmth causes evaporation.'
    undone = session.teacher_undo(expected_revision=after['revision'], expected_token=after['token'])
    assert undone['document']['pages'] == before['document']['pages']
    assert current.poll(request_id)['status'] == 'applied'
    assert recovery.get(request_id)['publication_status'] == 'applied'
    with pytest.raises((BoardAgentError, BoardConflictError, ValueError)):
        controller(session, recovery).recover(recovery.get(request_id))
    current.close()


def test_freeze_keeps_pupil_snapshot_during_recovered_preview_and_apply(saved_request):
    case = saved_request
    session, recovery, current = reopen(case)
    pinned = session.freeze(expected_token=session.teacher_view()['token'])
    request_id = current.recover(recovery.get(case['id']))
    state = current.snapshot(request_id)
    assert session.pupil_view() == pinned
    assert current.confirm(request_id, state['proposal_digest'])['status'] == 'applied'
    assert session.pupil_view() == pinned
    session.resume(expected_token=session.teacher_view()['token'])
    assert session.pupil_view()['document'] == session.teacher_view()['document']
    current.close()


@pytest.mark.parametrize('change', ['same_revision_content', 'same_revision_other_page', 'new_lesson_identity', 'navigation'])
def test_restart_rejects_different_work_even_when_revision_matches(saved_request, change):
    case = saved_request
    state = case['session'].export_state()
    if change == 'same_revision_content':
        state['document']['pages'][0]['objects'][0]['text'] = 'Different saved teaching work'
    elif change == 'same_revision_other_page':
        state['document']['pages'][1]['title'] = 'A different private page'
    elif change == 'new_lesson_identity':
        identity = str(uuid.uuid4())
        state['document']['lesson_id'] = identity
        for prior in state['undo'] + state['redo']:
            prior['lesson_id'] = identity
    session = BoardSession(BoardModel.from_state(state))
    if change == 'navigation':
        session.teacher_navigate(case['other_page_id'], expected_token=session.teacher_view()['token'])
    current = controller(session, case['recovery'])
    before = session.teacher_view()
    with pytest.raises((BoardAgentError, BoardConflictError, ValueError)):
        current.recover(case['recovery'].get(case['id']))
    assert session.teacher_view() == before
    current.close()


def test_edit_after_recovered_preview_refuses_older_publication(saved_request):
    session, recovery, current, request_id = recover(saved_request)
    preview = current.snapshot(request_id)
    apply(session, [{'op': 'update_object', 'page_id': saved_request['page_id'],
        'object_id': saved_request['object_id'], 'changes': {'text': 'Newer teacher edit'}}])
    before = session.teacher_view()
    assert current.confirm(request_id, preview['proposal_digest'])['status'] == 'stale'
    assert session.teacher_view() == before
    current.close()


def test_two_windows_cannot_present_the_same_recovered_result_twice(saved_request):
    first_session, recovery, first = reopen(saved_request)
    second_session, _, second = reopen(saved_request)
    request_id = first.recover(recovery.get(saved_request['id']))
    second.recover(recovery.get(request_id))
    first_preview = first.snapshot(request_id)
    second_preview = second.snapshot(request_id)
    assert first.confirm(request_id, first_preview['proposal_digest'])['status'] == 'applied'
    before_second = second_session.teacher_view()
    second_result = second.confirm(request_id, second_preview['proposal_digest'])
    assert second_result['status'] != 'applied'
    assert second_session.teacher_view() == before_second
    assert recovery.get(request_id)['publication_status'] == 'applied'
    first.close()
    second.close()


@pytest.mark.parametrize('publication_status', ['applying', 'applied', 'cancelled'])
def test_restart_does_not_replay_ambiguous_or_consumed_publication(saved_request, publication_status):
    case = saved_request
    case['recovery'].update(case['id'], publication_status=publication_status)
    session, recovery, current = reopen(case)
    before = session.teacher_view()
    with pytest.raises((BoardAgentError, BoardConflictError, ValueError)):
        current.recover(recovery.get(case['id']))
    assert session.teacher_view() == before
    current.close()


def test_cancelled_recovered_preview_stays_cancelled_after_restart(saved_request):
    session, recovery, current, request_id = recover(saved_request)
    before = session.teacher_view()
    current.cancel(request_id)
    assert current.snapshot(request_id)['status'] == 'cancelled'
    assert session.teacher_view() == before
    current.close()
    restarted = controller(session, BoardRecoveryStore(saved_request['root'] / 'board-requests'))
    with pytest.raises((BoardAgentError, BoardConflictError, ValueError)):
        restarted.recover(recovery.get(request_id))
    restarted.close()


@pytest.mark.parametrize('tamper', ['request_id', 'context_sha256', 'session_token'])
def test_recovered_output_must_match_original_envelope_before_rebinding(saved_request, tamper):
    case = saved_request
    changed = copy.deepcopy(case['result'])
    changed[tamper] = str(uuid.uuid4())
    # A malformed response is the first saved result, rather than a later rewrite
    # of the immutable output retained by the journal.
    original = case['recovery'].get(case['id'])
    recovery = BoardRecoveryStore(case['root'] / ('bad-output-' + tamper))
    recovery.create(case['prepared'], original['baseline'])
    recovery.bind(case['id'], original['hermes_request_id'])
    recovery.update(case['id'], status='completed', result=json.dumps(changed))
    session = BoardSession.open(BoardStore(case['root']))
    current = controller(session, recovery)
    before = session.teacher_view()
    with pytest.raises((BoardAgentError, BoardConflictError, ValueError)):
        current.recover(recovery.get(case['id']))
    assert session.teacher_view() == before
    current.close()


def test_portable_export_excludes_private_request_and_receipt_files(saved_request, tmp_path):
    case = saved_request
    private_marker = b'PRIVATE_REMOTE_RECEIPT_NOT_LESSON_CONTENT'
    private = case['root'] / 'agent-runtime'
    private.mkdir()
    (private / 'run-response.json').write_bytes(private_marker)
    package = export_lesson(case['session'].export_state(), tmp_path / 'lesson.tboard',
        media_store=MediaStore(case['root'] / 'media'))
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        contents = b''.join(archive.read(name) for name in names)
    assert all('board-requests' not in name and 'agent-runtime' not in name for name in names)
    assert private_marker not in contents
    assert b'PRIVATE_RECOVERY_PROMPT' not in contents
    assert case['id'].encode() not in contents


def test_independent_copy_excludes_requests_and_cannot_own_original_task(saved_request, monkeypatch):
    import board_lessons
    from board_lessons import copy_saved_lesson
    case = saved_request
    monkeypatch.setattr(board_lessons, 'CANDIDATE_ROOT', case['root'].parent)
    destination = case['root'].parent / 'independent-copy'
    copied, copied_store, _ = copy_saved_lesson(case['session'], case['root'], destination, 'Independent lesson')
    assert copied.teacher_view()['document']['lesson_id'] != case['session'].teacher_view()['document']['lesson_id']
    assert not (copied_store.root / 'board-requests').exists()
    copy_recovery = BoardRecoveryStore(copied_store.root / 'board-requests')
    assert copy_recovery.list_requests() == []
    other_controller = controller(copied, copy_recovery)
    before = copied.teacher_view()
    with pytest.raises((BoardAgentError, BoardConflictError, ValueError, FileNotFoundError)):
        other_controller.recover(case['recovery'].get(case['id']))
    assert copied.teacher_view() == before
    other_controller.close()
    copied.close()
