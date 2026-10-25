import copy
import hashlib
from pathlib import Path
import sys
import uuid
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_session
from board_model import BoardModel, BoardConflictError, BoardValidationError, new_object, new_page
from board_store import BoardStore
from board_session import (BoardSession, BoardAuthorityError, BoardSessionSaveError,
                           BoardSessionError, BoardMediaError)


def apply(session, commands):
    view = session.teacher_view()
    return session.teacher_apply(commands, expected_revision=view['revision'], expected_token=view['token'])


def add(session, obj):
    page = session.teacher_view()['page_id']
    return apply(session, [{'op': 'add_object', 'page_id': page, 'object': obj}])


def travel(session, direction):
    view = session.teacher_view()
    return getattr(session, 'teacher_' + direction)(expected_revision=view['revision'], expected_token=view['token'])


def test_freeze_pins_complete_pupil_view_through_private_teacher_edits_and_navigation():
    session = BoardSession()
    second = new_page('Condensation')
    text = new_object('text', text='Before')
    add(session, text)
    apply(session, [{'op': 'add_page', 'page': second}])
    frozen = session.freeze(expected_token=session.teacher_view()['token'])
    frozen_copy = copy.deepcopy(frozen)
    page = session.teacher_view()['page_id']
    apply(session, [{'op': 'rename_lesson', 'title': 'Private title'},
                    {'op': 'update_object', 'page_id': page, 'object_id': text['id'],
                     'changes': {'text': 'Private text', 'x': 300}},
                    {'op': 'add_object', 'page_id': page, 'object': new_object('ink')}])
    session.teacher_navigate(second['id'], expected_token=session.teacher_view()['token'])
    assert session.pupil_view() == frozen_copy
    travel(session, 'undo')
    assert session.pupil_view() == frozen_copy
    travel(session, 'redo')
    assert session.pupil_view() == frozen_copy
    resumed = session.resume(expected_token=session.teacher_view()['token'])
    assert resumed['document'] == session.teacher_view()['document']
    assert resumed['page_id'] == second['id']
    assert resumed['frozen'] is False and resumed['read_only'] is False
    assert resumed['token'] != frozen['token']


@pytest.mark.parametrize('action', ['navigate', 'add', 'erase'])
def test_all_pupil_mutations_rejected_while_frozen(action):
    session = BoardSession()
    ink = new_object('ink')
    add(session, ink)
    frozen = session.freeze(expected_token=session.teacher_view()['token'])
    before = session.teacher_view()
    with pytest.raises(BoardAuthorityError, match='frozen'):
        if action == 'navigate':
            session.pupil_navigate(frozen['page_id'], expected_token=frozen['token'])
        elif action == 'add':
            session.pupil_add_ink(new_object('ink'), expected_revision=frozen['revision'], expected_token=frozen['token'])
        else:
            session.pupil_erase_ink(ink['id'], expected_revision=frozen['revision'], expected_token=frozen['token'])
    assert session.teacher_view() == before and session.pupil_view() == frozen


def test_pupil_authority_only_adds_and_erases_unlocked_active_page_ink():
    session = BoardSession()
    text = new_object('text', text='Keep this label')
    locked = new_object('ink', locked=True)
    add(session, text); add(session, locked)
    before = session.teacher_view()
    for illegal in [new_object('shape'), new_object('text'), new_object('ink', locked=True)]:
        with pytest.raises(BoardAuthorityError):
            session.pupil_add_ink(illegal, expected_revision=before['revision'], expected_token=before['token'])
    for object_id in [text['id'], locked['id']]:
        with pytest.raises(BoardAuthorityError):
            session.pupil_erase_ink(object_id, expected_revision=before['revision'], expected_token=before['token'])
    ink = new_object('ink', points=[[1, 1], [10, 10]])
    result = session.pupil_add_ink(ink, expected_revision=before['revision'], expected_token=before['token'])
    assert result['document'] == session.teacher_view()['document']
    result = session.pupil_erase_ink(ink['id'], expected_revision=result['revision'], expected_token=result['token'])
    assert [obj['id'] for obj in result['document']['pages'][0]['objects']] == [text['id'], locked['id']]
    assert not result['can_edit_layout'] and result['can_annotate']


def test_navigation_uses_stable_pages_and_invalidates_old_callbacks_without_dirtying_lesson(tmp_path):
    session = BoardSession(store=BoardStore(tmp_path))
    second = new_page('Second')
    apply(session, [{'op': 'add_page', 'page': second}])
    session.save(expected_token=session.teacher_view()['token'])
    old = session.pupil_view()
    navigated = session.pupil_navigate(second['id'], expected_token=old['token'])
    assert navigated['page_id'] == session.teacher_view()['page_id'] == second['id']
    assert navigated['revision'] == old['revision']
    assert not session.teacher_view()['dirty']
    with pytest.raises(BoardConflictError):
        session.pupil_add_ink(new_object('ink'), expected_revision=old['revision'], expected_token=old['token'])
    with patch.object(session._store, 'save') as save:
        with pytest.raises(BoardConflictError):
            session.save(expected_token=old['token'])
        save.assert_not_called()


def test_freeze_resume_invalidates_stale_actions_and_prior_session_tokens(tmp_path):
    store = BoardStore(tmp_path)
    session = BoardSession(store=store)
    old = session.teacher_view()
    session.freeze(expected_token=old['token'])
    with pytest.raises(BoardConflictError):
        session.resume(expected_token=old['token'])
    session.resume(expected_token=session.teacher_view()['token'])
    session.save(expected_token=session.teacher_view()['token'])
    reopened = BoardSession.open(BoardStore(tmp_path))
    with pytest.raises(BoardConflictError):
        reopened.teacher_apply([{'op': 'rename_lesson', 'title': 'Delayed old session'}],
                               expected_revision=old['revision'], expected_token=old['token'])
    assert reopened.teacher_view()['revision'] == old['revision']


def test_teacher_batch_failure_preserves_both_views_and_undo_is_atomic():
    session = BoardSession()
    before_t, before_p = session.teacher_view(), session.pupil_view()
    with pytest.raises(BoardValidationError):
        apply(session, [{'op': 'rename_lesson', 'title': 'Must not appear'}, {'op': 'arbitrary_shell'}])
    assert session.teacher_view() == before_t and session.pupil_view() == before_p
    apply(session, [{'op': 'rename_lesson', 'title': 'New title'},
                    {'op': 'add_object', 'page_id': before_t['page_id'], 'object': new_object('text')}])
    assert session.pupil_view()['document']['title'] == 'New title'
    travel(session, 'undo')
    assert session.pupil_view()['document']['title'] == 'Untitled lesson'
    assert session.pupil_view()['revision'] == 2


def test_deleting_frozen_audience_page_keeps_snapshot_until_atomic_resume():
    session = BoardSession()
    original = session.teacher_view()['page_id']
    replacement = new_page('Replacement')
    apply(session, [{'op': 'add_page', 'page': replacement}])
    frozen = session.freeze(expected_token=session.teacher_view()['token'])
    apply(session, [{'op': 'remove_page', 'page_id': original}])
    assert session.teacher_view()['page_id'] == replacement['id']
    assert session.pupil_view() == frozen
    session.resume(expected_token=session.teacher_view()['token'])
    assert session.pupil_view()['page_id'] == replacement['id']
    assert len(session.pupil_view()['document']['pages']) == 1


def test_save_failure_stays_dirty_and_reports_error_without_losing_ink_or_freeze(tmp_path):
    store = BoardStore(tmp_path)
    session = BoardSession(store=store)
    assert session.teacher_view()['dirty']
    assert session.save(expected_token=session.teacher_view()['token']) == 0
    add(session, new_object('ink'))
    frozen = session.freeze(expected_token=session.teacher_view()['token'])
    before = session.teacher_view()['document']
    with patch.object(store, 'save', side_effect=OSError('Private storage path must not leak')):
        with pytest.raises(BoardSessionSaveError):
            session.save(expected_token=session.teacher_view()['token'])
    state = session.teacher_view()
    assert state['dirty'] and state['saved_revision'] == 0 and state['save_error']
    assert 'Private storage path' not in state['save_error']
    assert state['document'] == before and session.pupil_view() == frozen
    assert session.save(expected_token=state['token']) == 1
    assert not session.teacher_view()['dirty'] and session.teacher_view()['save_error'] is None


def test_reopen_preserves_lesson_ink_undo_and_reports_previous_recovery(tmp_path):
    store = BoardStore(tmp_path)
    session = BoardSession(store=store)
    ink = new_object('ink', points=[[1, 2], [30, 40]])
    add(session, ink)
    session.save(expected_token=session.teacher_view()['token'])
    apply(session, [{'op': 'rename_lesson', 'title': 'Later checkpoint'}])
    session.save(expected_token=session.teacher_view()['token'])
    store.current_path.write_bytes(b'Synthetic damaged current')
    recovered = BoardSession.open(BoardStore(tmp_path))
    view = recovered.teacher_view()
    assert view['recovery_status'] == 'recovered_previous'
    assert view['saved_revision'] == view['revision'] == 1 and not view['dirty']
    assert view['document']['pages'][0]['objects'][0]['id'] == ink['id']
    assert not view['frozen']
    travel(recovered, 'undo')
    assert recovered.teacher_view()['dirty']
    assert recovered.teacher_view()['document']['pages'][0]['objects'] == []


def test_external_model_and_view_mutation_cannot_bypass_role_or_token_boundary():
    model = BoardModel()
    session = BoardSession(model)
    model.apply([{'op': 'rename_lesson', 'title': 'External model edit'}], expected_revision=0)
    view = session.pupil_view()
    view['document']['title'] = 'External view edit'
    assert session.teacher_view()['document']['title'] == 'Untitled lesson'


def test_no_store_and_closed_sessions_fail_honestly():
    session = BoardSession()
    old = session.teacher_view()
    with pytest.raises(BoardSessionSaveError, match='No local'):
        session.save(expected_token=old['token'])
    assert session.teacher_view()['dirty']
    session.close()
    with pytest.raises(BoardSessionError, match='closed'):
        session.save(expected_token=old['token'])
    with pytest.raises(BoardSessionError):
        session.pupil_navigate(old['page_id'], expected_token=old['token'])


def test_readonly_image_resolver_checks_pin_and_bytes_without_mutating_or_fallback(monkeypatch):
    data = b'Synthetic pinned bytes; renderer validates supported image decoding separately.'
    ref = {'asset_id': str(uuid.uuid4()), 'version_id': str(uuid.uuid4()),
           'sha256': hashlib.sha256(data).hexdigest()}
    resolver = Mock(return_value=data)
    session = BoardSession(image_resolver=resolver)
    before = session.teacher_view()
    assert session.resolve_image(ref) == data
    resolver.assert_called_once_with(ref)
    for invalid in [None, b'corrupt', Path('arbitrary.png'), 'https://arbitrary.invalid/image']:
        resolver.return_value = invalid
        with pytest.raises(BoardMediaError):
            session.resolve_image(ref)
    monkeypatch.setattr(board_session, 'MAX_IMAGE_BYTES', 4)
    resolver.return_value = data
    with pytest.raises(BoardMediaError):
        session.resolve_image(ref)
    assert session.teacher_view() == before
    with pytest.raises(BoardValidationError):
        session.resolve_image({**ref, 'path': 'private.png'})
    with pytest.raises(BoardMediaError):
        BoardSession().resolve_image(ref)
