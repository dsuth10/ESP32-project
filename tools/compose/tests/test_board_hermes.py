import copy
import hashlib
import json
from pathlib import Path
import sys
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_hermes
from board_hermes import (prepare_request, review_result, apply_result,
                          BoardProposalError, BoardConfirmationRequired)
from board_model import BoardConflictError, new_object, new_page
from board_session import BoardSession
from hermes_service import HermesService, _message


def teacher_apply(session, commands):
    view = session.teacher_view()
    return session.teacher_apply(commands, expected_revision=view['revision'], expected_token=view['token'])


@pytest.fixture
def board():
    session = BoardSession()
    page = session.teacher_view()['page_id']
    a, b = new_object('text', text='ACTIVE_TEXT'), new_object('shape')
    other = new_page('Other page')
    other['objects'] = [new_object('text', text='SECRET_OTHER_PAGE')]
    teacher_apply(session, [{'op': 'add_object', 'page_id': page, 'object': a},
                            {'op': 'add_object', 'page_id': page, 'object': b},
                            {'op': 'add_page', 'page': other}])
    return session, page, a, b, other


def selected_image():
    return {'image_ref': {'asset_id': str(uuid.uuid4()), 'version_id': str(uuid.uuid4()), 'sha256': 'a' * 64},
            'title': 'Water cycle image', 'width': 1024, 'height': 768}


def proposal_for(selection, commands, operation='edit'):
    context = json.loads(selection['context'])
    return {'schema': 1, 'request_id': context['request_id'],
            'context_sha256': hashlib.sha256(selection['context'].encode('utf-8')).hexdigest(),
            'lesson_id': context['lesson_id'], 'expected_revision': context['revision'],
            'session_token': context['session_token'], 'operation': operation, 'commands': commands}


def saved_fixture(tmp_path, session, commands, *, operation='edit', **prepare_options):
    selection = prepare_request(session, 'Make this requested lesson change', **prepare_options)
    service = HermesService({'LOCAL_ONLY': '1'}, tmp_path / uuid.uuid4().hex)
    prepared = service.prepare(selection['task'], selection['context'])
    proposal = proposal_for(selection, commands, operation)
    service._save_state(prepared['request_id'], 'completed', 'Synthetic fixture result',
                        text=_message({'output': json.dumps(proposal)}))
    saved = service.preview(prepared['request_id'])
    service.close()
    return saved


def test_default_context_only_active_page_and_explicit_selected_media(board):
    session, page, _, _, _ = board
    hidden, selected = selected_image(), selected_image()
    teacher_apply(session, [{'op': 'add_object', 'page_id': page,
                            'object': new_object('image', image_ref=hidden['image_ref'])}])
    selection = prepare_request(session, 'Explain ACTIVE_TEXT', selected_images=[selected])
    context = json.loads(selection['context'])
    assert context['page_ids'] == [page] and context['scope'] == 'active_page'
    assert 'ACTIVE_TEXT' in selection['context'] and 'SECRET_OTHER_PAGE' not in selection['context']
    assert hidden['image_ref']['version_id'] not in selection['context']
    assert context['selected_images'] == [selected]
    assert 'image_ref' not in context['pages'][0]['objects'][-1]
    assert set(selection) == {'task', 'context'}
    assert session.teacher_view()['revision'] == 2
    whole = prepare_request(session, 'Review all pages', whole_lesson=True)
    assert 'SECRET_OTHER_PAGE' in whole['context']


def test_real_durable_preview_scoped_batch_applies_as_one_undo_and_cannot_replay(tmp_path, board):
    session, page, a, b, _ = board
    before = session.teacher_view()
    saved = saved_fixture(tmp_path, session, [
        {'op': 'update_object', 'page_id': page, 'object_id': a['id'], 'changes': {'text': 'Evaporation'}},
        {'op': 'update_object', 'page_id': page, 'object_id': b['id'], 'changes': {'x': 250}},
    ])
    assert review_result(session, saved)['supported']
    assert session.teacher_view() == before
    result = apply_result(session, saved)
    assert result['revision'] == before['revision'] + 1
    with pytest.raises(BoardConflictError):
        apply_result(session, saved)
    undone = session.teacher_undo(expected_revision=result['revision'], expected_token=result['token'])
    assert undone['document']['pages'] == before['document']['pages']
    assert undone['revision'] > result['revision']


def test_stale_result_after_manual_edit_navigation_or_freeze_cannot_apply(tmp_path, board):
    session, page, a, _, other = board
    commands = [{'op': 'update_object', 'page_id': page, 'object_id': a['id'], 'changes': {'text': 'Old AI'}}]
    saved = saved_fixture(tmp_path, session, commands)
    session.teacher_navigate(other['id'], expected_token=session.teacher_view()['token'])
    with pytest.raises(BoardConflictError):
        apply_result(session, saved)
    session.teacher_navigate(page, expected_token=session.teacher_view()['token'])
    saved = saved_fixture(tmp_path, session, commands)
    session.freeze(expected_token=session.teacher_view()['token'])
    with pytest.raises(BoardConflictError):
        apply_result(session, saved)
    saved = saved_fixture(tmp_path, session, commands)
    teacher_apply(session, [{'op': 'update_object', 'page_id': page,
                            'object_id': a['id'], 'changes': {'text': 'New manual text'}}])
    with pytest.raises(BoardConflictError):
        apply_result(session, saved)


@pytest.mark.parametrize('field,value', [
    ('request_id', str(uuid.uuid4())), ('context_sha256', 'b' * 64),
    ('lesson_id', str(uuid.uuid4())), ('expected_revision', 999),
    ('expected_revision', True), ('session_token', 'different-session:1'),
])
def test_proposal_must_echo_exact_request_context_identity_revision_and_token(tmp_path, board, field, value):
    session, page, a, _, _ = board
    saved = saved_fixture(tmp_path, session, [{'op': 'update_object', 'page_id': page,
        'object_id': a['id'], 'changes': {'text': 'Requested'}}])
    proposal = json.loads(saved['text']); proposal[field] = value
    saved['text'] = json.dumps(proposal)
    before = session.teacher_view()
    with pytest.raises(BoardConflictError):
        apply_result(session, saved)
    assert session.teacher_view() == before


@pytest.mark.parametrize('command_kind', ['other_page', 'add_page', 'rename_lesson'])
def test_default_scope_cannot_edit_other_pages_or_expand_to_lesson(tmp_path, board, command_kind):
    session, _, _, _, other = board
    commands = {
        'other_page': {'op': 'update_page', 'page_id': other['id'], 'changes': {'title': 'No'}},
        'add_page': {'op': 'add_page', 'page': new_page('No')},
        'rename_lesson': {'op': 'rename_lesson', 'title': 'No'},
    }
    saved = saved_fixture(tmp_path, session, [commands[command_kind]])
    with pytest.raises(BoardProposalError):
        apply_result(session, saved)


def test_explicit_whole_lesson_scope_can_add_page_and_edit_selected_other_page(tmp_path, board):
    session, _, _, _, other = board
    page = new_page('New page')
    saved = saved_fixture(tmp_path, session, [{'op': 'add_page', 'page': page},
        {'op': 'update_page', 'page_id': other['id'], 'changes': {'title': 'Condensation'}}], whole_lesson=True)
    result = apply_result(session, saved)
    assert [p['title'] for p in result['document']['pages']][-2:] == ['Condensation', 'New page']


@pytest.mark.parametrize('mutate', ['unselected', 'asset_id', 'version_id', 'sha256', 'path'])
def test_added_images_require_exact_explicit_immutable_manifest(tmp_path, board, mutate):
    session, page, _, _, _ = board
    selected = selected_image()
    ref = copy.deepcopy(selected['image_ref'])
    if mutate in {'asset_id', 'version_id'}:
        ref[mutate] = str(uuid.uuid4())
    elif mutate == 'sha256':
        ref['sha256'] = 'b' * 64
    image = new_object('image', image_ref=ref)
    if mutate == 'path':
        image['path'] = 'private.png'
    saved = saved_fixture(tmp_path, session, [{'op': 'add_object', 'page_id': page, 'object': image}],
                          selected_images=[] if mutate == 'unselected' else [selected])
    with pytest.raises(BoardProposalError):
        apply_result(session, saved)


def test_exact_selected_image_ref_is_supported_and_never_resolved_or_generated(tmp_path, board):
    session, page, _, _, _ = board
    selected = selected_image()
    saved = saved_fixture(tmp_path, session, [{'op': 'add_object', 'page_id': page,
        'object': new_object('image', image_ref=selected['image_ref'])}], selected_images=[selected])
    result = apply_result(session, saved)
    assert result['document']['pages'][0]['objects'][-1]['image_ref'] == selected['image_ref']


@pytest.mark.parametrize('field', ['confirmed_destructive', 'confirmation_digest', 'shell', 'url', 'private_notes'])
def test_model_cannot_supply_controller_authority_or_action_fields(tmp_path, board, field):
    session, page, a, _, _ = board
    saved = saved_fixture(tmp_path, session, [{'op': 'update_object', 'page_id': page,
        'object_id': a['id'], 'changes': {'text': 'Requested'}}])
    proposal = json.loads(saved['text']); proposal[field] = 'untrusted'
    saved['text'] = json.dumps(proposal)
    with pytest.raises(BoardProposalError):
        apply_result(session, saved)


def test_failed_mixed_batch_never_partially_publishes_or_adds_undo(tmp_path, board):
    session, page, a, _, _ = board
    before = session.teacher_view(), session.pupil_view()
    saved = saved_fixture(tmp_path, session, [
        {'op': 'update_object', 'page_id': page, 'object_id': a['id'], 'changes': {'text': 'Must not publish'}},
        {'op': 'update_object', 'page_id': page, 'object_id': str(uuid.uuid4()), 'changes': {'x': 1}},
    ])
    with pytest.raises(BoardProposalError):
        apply_result(session, saved)
    assert (session.teacher_view(), session.pupil_view()) == before


def test_invalid_object_identity_type_fails_without_leaking_type_error(tmp_path, board):
    session, page, _, _, _ = board
    saved = saved_fixture(tmp_path, session, [{'op': 'remove_object', 'page_id': page, 'object_id': []}])
    with pytest.raises(BoardProposalError):
        apply_result(session, saved)


def test_result_byte_limit_fits_real_hermes_text_extraction_boundary(board):
    session, page, a, _, _ = board
    selection = prepare_request(session, 'Change the selected text')
    commands = [{'op': 'update_object', 'page_id': page,
                 'object_id': a['id'], 'changes': {'text': ''}}]
    proposal = proposal_for(selection, commands)
    base = json.dumps(proposal)
    remaining = board_hermes.MAX_RESULT_BYTES - len(base.encode('utf-8'))
    proposal['commands'][0]['changes']['text'] = 'x' * remaining
    encoded = json.dumps(proposal)
    assert len(encoded.encode('utf-8')) == 20000
    extracted = _message({'output': {'content': [{'text': encoded}]}})
    assert extracted == encoded
    preview = {'status': 'completed', 'context': selection['context'], 'text': extracted}
    assert review_result(session, preview)['supported']
    proposal['commands'][0]['changes']['text'] += 'x'
    oversized = json.dumps(proposal)
    assert len(oversized) == 20001
    truncated = _message({'output': oversized})
    assert len(truncated) == 20000 and truncated != oversized
    with pytest.raises(BoardProposalError):
        review_result(session, {**preview, 'text': oversized})
    with pytest.raises(BoardProposalError):
        review_result(session, {**preview, 'text': truncated})


def test_page_removal_requires_external_confirmation_bound_to_exact_proposal(tmp_path, board):
    session, _, _, _, other = board
    saved = saved_fixture(tmp_path, session, [{'op': 'remove_page', 'page_id': other['id']}], whole_lesson=True)
    review = review_result(session, saved)
    assert review['requires_confirmation'] and review['supported']
    for options in [{}, {'confirmed_destructive': True},
                    {'confirmed_destructive': True, 'confirmation_digest': 'wrong'}]:
        with pytest.raises(BoardConfirmationRequired):
            apply_result(session, saved, **options)
    result = apply_result(session, saved, confirmed_destructive=True, confirmation_digest=review['proposal_digest'])
    assert len(result['document']['pages']) == 1


def test_changed_destructive_result_cannot_consume_prior_confirmation(tmp_path):
    session = BoardSession()
    page = session.teacher_view()['page_id']
    original = new_object('text', text='Original board')
    teacher_apply(session, [{'op': 'add_object', 'page_id': page, 'object': original}])
    saved = saved_fixture(tmp_path, session, [{'op': 'remove_object', 'page_id': page, 'object_id': original['id']}])
    confirmation = review_result(session, saved)
    assert confirmation['requires_confirmation']
    proposal = json.loads(saved['text'])
    proposal['commands'].append({'op': 'add_object', 'page_id': page, 'object': new_object('text', text='Replacement')})
    saved['text'] = json.dumps(proposal)
    assert review_result(session, saved)['requires_confirmation']
    with pytest.raises(BoardConfirmationRequired):
        apply_result(session, saved, confirmed_destructive=True, confirmation_digest=confirmation['proposal_digest'])
    assert session.teacher_view()['document']['pages'][0]['objects'][0]['text'] == 'Original board'


def test_remove_and_replace_all_original_objects_with_reused_ids_still_requires_confirmation(tmp_path):
    session = BoardSession()
    page = session.teacher_view()['page_id']
    original = new_object('text', text='Original board')
    teacher_apply(session, [{'op': 'add_object', 'page_id': page, 'object': original}])
    replacement = {**original, 'text': 'Replacement reusing original identity'}
    saved = saved_fixture(tmp_path, session, [
        {'op': 'remove_object', 'page_id': page, 'object_id': original['id']},
        {'op': 'add_object', 'page_id': page, 'object': replacement},
    ])
    review = review_result(session, saved)
    assert review['requires_confirmation']
    with pytest.raises(BoardConfirmationRequired):
        apply_result(session, saved)
    result = apply_result(session, saved, confirmed_destructive=True, confirmation_digest=review['proposal_digest'])
    assert result['document']['pages'][0]['objects'][0]['text'] == replacement['text']


def test_remove_readd_cannot_change_type_or_immutable_pin_under_existing_id(tmp_path):
    session = BoardSession()
    page = session.teacher_view()['page_id']
    selected, replacement = selected_image(), selected_image()
    image = new_object('image', image_ref=selected['image_ref'])
    teacher_apply(session, [{'op': 'add_object', 'page_id': page, 'object': image}])
    for other in [new_object('text', id=image['id'], text='Changed type'),
                  new_object('image', id=image['id'], image_ref=replacement['image_ref'])]:
        saved = saved_fixture(tmp_path, session, [
            {'op': 'remove_object', 'page_id': page, 'object_id': image['id']},
            {'op': 'add_object', 'page_id': page, 'object': other},
        ], selected_images=[replacement])
        with pytest.raises(BoardProposalError, match='cannot be reused'):
            apply_result(session, saved, confirmed_destructive=True)


@pytest.mark.parametrize('operation', ['replace_board', 'delete_lesson'])
def test_unsupported_whole_board_operations_never_execute_even_if_confirmed(tmp_path, board, operation):
    session, _, _, _, _ = board
    saved = saved_fixture(tmp_path, session, [], operation=operation, whole_lesson=True)
    review = review_result(session, saved)
    assert review['requires_confirmation'] and not review['supported']
    before = session.teacher_view()
    with pytest.raises(BoardProposalError, match='cannot execute'):
        apply_result(session, saved, confirmed_destructive=True, confirmation_digest=review['proposal_digest'])
    assert session.teacher_view() == before


def test_frozen_ai_edit_remains_private_until_resume_and_undo_is_one_step(tmp_path, board):
    session, page, a, _, _ = board
    frozen = session.freeze(expected_token=session.teacher_view()['token'])
    saved = saved_fixture(tmp_path, session, [{'op': 'update_object', 'page_id': page,
        'object_id': a['id'], 'changes': {'text': 'Private requested change'}}])
    result = apply_result(session, saved)
    assert session.pupil_view() == frozen
    result = session.teacher_undo(expected_revision=result['revision'], expected_token=result['token'])
    assert result['document']['pages'][0]['objects'][0]['text'] == 'ACTIVE_TEXT'


def test_context_and_result_bounds_types_duplicate_keys_and_no_private_fields(tmp_path, board, monkeypatch):
    session, page, a, _, _ = board
    image = selected_image()
    with pytest.raises(BoardProposalError):
        prepare_request(session, 'Test', selected_images=[{**image, 'prompt': 'PRIVATE_PROMPT'}])
    with pytest.raises(BoardProposalError):
        prepare_request(session, 'Test', whole_lesson='yes')
    with pytest.raises(BoardProposalError):
        prepare_request(session, 'Test', selected_images=[selected_image() for _ in range(17)])
    saved = saved_fixture(tmp_path, session, [{'op': 'update_object', 'page_id': page,
        'object_id': a['id'], 'changes': {'text': 'Requested'}}])
    for text in ['{"schema":1,"schema":1}', '{"x":NaN}', '[]', 'not JSON']:
        with pytest.raises(BoardProposalError):
            apply_result(session, {**saved, 'text': text})
    with pytest.raises(BoardProposalError):
        apply_result(session, {**saved, 'status': []})
    monkeypatch.setattr(board_hermes, 'MAX_RESULT_BYTES', 16)
    with pytest.raises(BoardProposalError):
        apply_result(session, saved)


def test_tampered_context_snapshot_fails_even_with_matching_output_hash(tmp_path, board):
    session, page, a, _, _ = board
    saved = saved_fixture(tmp_path, session, [{'op': 'update_object', 'page_id': page,
        'object_id': a['id'], 'changes': {'text': 'Requested'}}])
    context = json.loads(saved['context'])
    context['pages'][0]['objects'][0]['text'] = 'Altered selected snapshot'
    saved['context'] = json.dumps(context)
    proposal = json.loads(saved['text'])
    proposal['context_sha256'] = hashlib.sha256(saved['context'].encode('utf-8')).hexdigest()
    saved['text'] = json.dumps(proposal)
    with pytest.raises(BoardConflictError, match='exact selected snapshot'):
        apply_result(session, saved)
