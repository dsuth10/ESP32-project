import copy
from concurrent.futures import Future, ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import sys
import uuid

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_agent import (BoardAgentController, BoardAgentError, TeachingProfile, HermesBoardComposer,
                         load_profile, save_profile, result_envelope)
from board_model import BoardConflictError, new_object, new_page
from board_session import BoardSession


class ManualExecutor:
    def __init__(self):
        self.pending = []

    def submit(self, fn, *args):
        future = Future()
        self.pending.append((future, fn, args))
        return future

    def run(self):
        future, fn, args = self.pending.pop(0)
        if future.set_running_or_notify_cancel():
            try:
                future.set_result(fn(*args))
            except BaseException as exc:
                future.set_exception(exc)


def apply(session, commands):
    view = session.teacher_view()
    return session.teacher_apply(commands, expected_revision=view['revision'], expected_token=view['token'])


@pytest.fixture
def board():
    session = BoardSession()
    page_id = session.teacher_view()['page_id']
    first = new_object('text', text='Original pupil explanation', x=70, y=80, width=650, height=150)
    second = new_object('text', text='Keep this wording', x=70, y=300, width=650, height=150)
    other = new_page('PRIVATE OTHER PAGE')
    other['objects'] = [new_object('text', text='UNRELATED HISTORY OR PRIVATE NOTE')]
    apply(session, [{'op': 'add_object', 'page_id': page_id, 'object': first},
                    {'op': 'add_object', 'page_id': page_id, 'object': second},
                    {'op': 'add_page', 'page': other}])
    return session, page_id, first, second, other


def image_record(*, generated=False, required=False):
    stream = io.BytesIO()
    Image.new('RGB', (80, 40), '#B2DFF7').save(stream, format='PNG')
    data = stream.getvalue()
    return {'image_ref': {'asset_id': str(uuid.uuid4()), 'version_id': str(uuid.uuid4()),
                          'sha256': hashlib.sha256(data).hexdigest()},
            'title': 'Water cycle', 'width': 80, 'height': 40,
            'generated_unreviewed': generated, 'required': required}, data


def edit_result(board, prepared):
    return result_envelope(prepared, commands=[{'op': 'update_object', 'page_id': board[1],
        'object_id': board[2]['id'], 'changes': {'text': 'Warmth causes evaporation.'}}])


def make_controller(board, make_result=None, **kwargs):
    executor = ManualExecutor()
    def composer(prepared, report, cancelled):
        report('composing', 'Composing a complete explanation.')
        return make_result(prepared) if make_result else edit_result(board, prepared)
    composer.remote = False
    controller = BoardAgentController(board[0], composer=composer, executor=executor, **kwargs)
    return controller, executor


def complete(controller, executor, **options):
    prepared = controller.prepare('Explain evaporation', **options)
    request_id = controller.start(prepared)
    executor.run()
    return request_id, controller.poll(request_id)


def test_profile_defaults_save_reopen_revision_and_private_location(tmp_path):
    path = tmp_path / 'private' / 'profile.json'
    assert load_profile(path) == TeachingProfile()
    profile = TeachingProfile(revision=3, year_level=4, instructions='Use Australian examples; measure rainfall in millimetres.')
    save_profile(path, profile)
    assert load_profile(path) == profile
    assert list(path.parent.iterdir()) == [path]
    path.write_text('{"schema":1,"schema":1}', encoding='utf-8')
    with pytest.raises(BoardAgentError):
        load_profile(path)


@pytest.mark.parametrize('fields', [{'revision': True}, {'year_level': 13}, {'year_level': True},
    {'language': 'US English'}, {'instructions': 'x'*4001}, {'allow_illustrative_data': 1}])
def test_profile_rejects_unsupported_values(fields):
    with pytest.raises(BoardAgentError):
        TeachingProfile(**fields)


def test_request_has_bounded_active_page_context_effective_profile_and_exact_selection(board):
    record, _ = image_record()
    hidden, _ = image_record()
    apply(board[0], [{'op': 'add_object', 'page_id': board[1], 'object': new_object('image', image_ref=hidden['image_ref'])}])
    profile = TeachingProfile(revision=8, year_level=5, instructions='Default short sentences')
    controller, _ = make_controller(board, profile=profile)
    prepared = controller.prepare('Use these precise words', selected_images=[record],
        lesson_context={'year_level': 6, 'instructions': 'Use the current science lesson'},
        selected_object_ids=[board[2]['id']], required_wording=['precise words'])
    context = json.loads(prepared['context'])
    assert context['page']['id'] == board[1]
    assert 'Original pupil explanation' in prepared['context']
    assert 'PRIVATE OTHER PAGE' not in prepared['context']
    assert 'UNRELATED HISTORY' not in prepared['context']
    assert hidden['image_ref']['version_id'] not in prepared['context']
    assert context['selected_images'] == [record]
    assert context['selected_object_ids'] == [board[2]['id']]
    assert context['effective_context']['year_level'] == 6
    assert context['effective_context']['profile_revision'] == 8
    assert context['effective_context']['profile_instructions'] == profile.instructions
    assert 'current instruction > lesson context' in context['effective_context']['precedence']
    assert hashlib.sha256(prepared['context'].encode()).hexdigest() == prepared['context_sha256']
    assert controller.profile == profile  # Requests do not learn/overwrite profile.


@pytest.mark.parametrize('options', [{'lesson_context': {'history': 'secret'}},
    {'selected_object_ids': [str(uuid.uuid4())]}, {'selected_object_ids': 'not a list'},
    {'required_wording': ['']}, {'local_only': 1}, {'selected_images': [{'path': 'private'}]}])
def test_request_rejects_out_of_scope_or_unsupported_context(board, options):
    controller, _ = make_controller(board)
    with pytest.raises(BoardAgentError):
        controller.prepare('Explain', **options)


def test_request_context_limit_is_bytes_and_not_a_silent_truncation(board):
    apply(board[0], [{'op': 'update_object', 'page_id': board[1], 'object_id': board[2]['id'],
                    'changes': {'text': '\u6c34'*17000}}])
    controller, _ = make_controller(board)
    with pytest.raises(BoardAgentError, match='48 KiB'):
        controller.prepare('Explain')


def test_completed_ordinary_edit_is_one_atomic_batch_and_undo_redo(board):
    session = board[0]
    before = session.teacher_view()
    controller, executor = make_controller(board, lambda prepared: result_envelope(prepared, commands=[
        {'op': 'update_object', 'page_id': board[1], 'object_id': board[2]['id'], 'changes': {'text': 'Evaporation'}},
        {'op': 'update_object', 'page_id': board[1], 'object_id': board[3]['id'], 'changes': {'x': 750}},
    ]))
    request_id = controller.start(controller.prepare('Revise this explanation'))
    assert controller.snapshot(request_id)['status'] == 'working'
    executor.run()
    assert session.teacher_view() == before  # Worker completion alone cannot publish.
    result = controller.poll(request_id)
    assert result['status'] == 'applied' and not result['requires_confirmation']
    after = session.teacher_view()
    assert after['revision'] == before['revision'] + 1
    assert session.pupil_view()['document'] == after['document']
    undone = session.teacher_undo(expected_revision=after['revision'], expected_token=after['token'])
    assert undone['document']['pages'] == before['document']['pages']
    redone = session.teacher_redo(expected_revision=undone['revision'], expected_token=undone['token'])
    assert redone['document']['pages'] == after['document']['pages']
    assert controller.poll(request_id)['status'] == 'applied'  # Cannot replay after Undo/Redo.


@pytest.mark.parametrize(('stage', 'message'), [
    ('searching', 'Resource planning'),
    ('acquiring', 'Image acquisition'),
    ('composing', 'Page composition'),
    ('validating', 'Page validation'),
])
def test_unexpected_failure_identifies_stage_without_exposing_provider_details(board, stage, message):
    def preparer(prepared, report, cancelled):
        report(stage, 'Fixture stage')
        raise RuntimeError('PRIVATE TOKEN AND PROVIDER URL')
    preparer.remote = False
    controller, executor = make_controller(board, resource_preparer=preparer)
    before = board[0].pupil_view()
    try:
        _, state = complete(controller, executor)
        assert state['status'] == 'failed'
        assert message in state['message']
        assert 'PRIVATE' not in state['message']
        assert board[0].pupil_view() == before
    finally:
        controller.close()


def test_prepare_cannot_be_tampered_replayed_or_borrowed_by_another_controller(board):
    controller, executor = make_controller(board)
    prepared = controller.prepare('Explain')
    changed = copy.deepcopy(prepared)
    changed['context'] += ' '
    with pytest.raises(BoardAgentError):
        controller.start(changed)
    other, _ = make_controller(board)
    with pytest.raises(BoardAgentError):
        other.start(prepared)
    controller.start(prepared)
    with pytest.raises(BoardAgentError):
        controller.start(prepared)


@pytest.mark.parametrize('change', ['edit', 'navigate', 'freeze', 'close'])
def test_stale_revision_navigation_freeze_or_closed_session_never_publishes(board, change):
    controller, executor = make_controller(board)
    request_id = controller.start(controller.prepare('Explain'))
    session = board[0]
    view = session.teacher_view()
    if change == 'edit':
        apply(session, [{'op': 'update_object', 'page_id': board[1], 'object_id': board[2]['id'], 'changes': {'text': 'New teacher work'}}])
    elif change == 'navigate':
        session.teacher_navigate(board[4]['id'], expected_token=view['token'])
    elif change == 'freeze':
        session.freeze(expected_token=view['token'])
    else:
        session.close()
    executor.run()
    result = controller.poll(request_id)
    assert result['status'] == 'stale'
    assert controller.preview(request_id) is None
    if change != 'close':
        assert 'Warmth causes' not in json.dumps(session.teacher_view())


def test_started_while_frozen_updates_teacher_only_then_resume_presents_atomically(board):
    session = board[0]
    session.freeze(expected_token=session.teacher_view()['token'])
    pupil_before = session.pupil_view()
    controller, executor = make_controller(board)
    _, result = complete(controller, executor)
    assert result['status'] == 'applied'
    assert session.pupil_view() == pupil_before
    assert session.teacher_view()['document'] != pupil_before['document']
    resumed = session.resume(expected_token=session.teacher_view()['token'])
    assert 'Warmth causes evaporation.' in json.dumps(resumed)


@pytest.mark.parametrize('when', ['queued', 'working', 'completed'])
def test_cancel_never_publishes_even_late_results(board, when):
    holder = {}
    def composer(prepared):
        if when == 'working':
            holder['controller'].cancel(prepared['request_id'])
        return edit_result(board, prepared)
    controller, executor = make_controller(board, composer)
    holder['controller'] = controller
    before = board[0].teacher_view()
    request_id = controller.start(controller.prepare('Explain'))
    if when == 'queued':
        controller.cancel(request_id)
    executor.run()
    if when == 'completed':
        controller.cancel(request_id)
    assert controller.poll(request_id)['status'] == 'cancelled'
    assert board[0].teacher_view() == before


def test_new_request_supersedes_old_without_publishing_its_result(board):
    controller, executor = make_controller(board)
    first = controller.start(controller.prepare('Earlier explanation'))
    second = controller.start(controller.prepare('New explanation'))
    executor.run()
    assert controller.poll(first)['status'] == 'stale'
    executor.run()
    assert controller.poll(second)['status'] == 'applied'


def test_progress_target_is_not_a_timeout_and_continues_truthfully(board):
    now = [2.0]
    controller, executor = make_controller(board, clock=lambda: now[0])
    request_id = controller.start(controller.prepare('Explain'))
    now[0] = 18.0
    snapshot = controller.poll(request_id)
    assert snapshot['status'] == 'working' and snapshot['target_exceeded']
    assert snapshot['elapsed_seconds'] == 16
    assert controller.preview(request_id) is None
    executor.run()
    assert controller.poll(request_id)['status'] == 'applied'
    now[0] = 99
    assert controller.snapshot(request_id)['elapsed_seconds'] == 16


@pytest.mark.parametrize('bad_result', ['exception', 'json', 'duplicate', 'nonfinite', 'large', 'unsupported',
    'request', 'digest', 'revision', 'session', 'code', 'scope', 'invalid_second', 'off_page', 'wording'])
def test_failed_validation_has_no_partial_edits_undo_entry_or_pupil_update(board, bad_result):
    def make_result(prepared):
        value = edit_result(board, prepared)
        if bad_result == 'exception':
            raise RuntimeError('PRIVATE PROVIDER ERROR')
        if bad_result == 'json':
            return 'not JSON'
        if bad_result == 'duplicate':
            return '{"schema":1,"schema":1}'
        if bad_result == 'nonfinite':
            return '{"schema":NaN}'
        if bad_result == 'large':
            return ' '*20001
        if bad_result == 'unsupported':
            value['execute'] = 'shell'
        if bad_result in ('request', 'digest', 'revision', 'session'):
            key = {'request': 'request_id', 'digest': 'context_sha256', 'revision': 'expected_revision', 'session': 'session_token'}[bad_result]
            value[key] = 99 if bad_result == 'revision' else 'WRONG'
        if bad_result == 'code':
            value['commands'] = [{'op': 'execute_python', 'source': 'print(1)'}]
        if bad_result == 'scope':
            value['commands'][0]['page_id'] = board[4]['id']
        if bad_result == 'invalid_second':
            value['commands'].append({'op': 'update_object', 'page_id': board[1], 'object_id': board[3]['id'], 'changes': {'font_size': -1}})
        if bad_result == 'off_page':
            value['commands'][0]['changes']['x'] = 2000
        return value
    controller, executor = make_controller(board, make_result)
    before = board[0].teacher_view()
    pupil = board[0].pupil_view()
    options = {'required_wording': ['MUST KEEP EXACT']} if bad_result == 'wording' else {}
    request_id, result = complete(controller, executor, **options)
    assert result['status'] in {'failed', 'stale'}
    assert 'PRIVATE PROVIDER ERROR' not in str(result)
    assert board[0].teacher_view() == before
    assert board[0].pupil_view() == pupil
    assert controller.preview(request_id) is None


def test_required_wording_and_required_image_omission_are_not_silently_accepted(board):
    image, data = image_record(required=True)
    controller, executor = make_controller(board, resource_resolver=lambda ref: data)
    before = board[0].teacher_view()
    _, result = complete(controller, executor, selected_images=[image], required_wording=['Keep this wording'])
    assert result['status'] == 'failed'
    assert board[0].teacher_view() == before


@pytest.mark.parametrize('broken', ['unavailable', 'hash', 'decode', 'dimensions'])
def test_required_images_validate_all_bytes_before_atomic_publish(board, broken):
    record, data = image_record(required=True)
    if broken == 'decode':
        data = b'not an image'
        record['image_ref']['sha256'] = hashlib.sha256(data).hexdigest()
    if broken == 'dimensions':
        record['width'] = 900
    def resolver(ref):
        if broken == 'unavailable':
            raise OSError('missing')
        return b'wrong bytes' if broken == 'hash' else data
    def composition(prepared):
        result = edit_result(board, prepared)
        result['commands'].append({'op': 'add_object', 'page_id': board[1],
            'object': new_object('image', image_ref=record['image_ref'], x=800, y=400)})
        return result
    controller, executor = make_controller(board, composition, resource_resolver=resolver)
    before = board[0].teacher_view()
    _, result = complete(controller, executor, selected_images=[record])
    assert result['status'] == 'failed'
    assert board[0].teacher_view() == before


def test_new_image_not_in_trusted_shortlist_cannot_be_claimed_approved_by_model(board):
    record, data = image_record()
    def composition(prepared):
        return result_envelope(prepared, commands=[{'op': 'add_object', 'page_id': board[1],
            'object': new_object('image', image_ref=record['image_ref'])}])
    controller, executor = make_controller(board, composition, resource_resolver=lambda ref: data)
    _, result = complete(controller, executor)
    assert result['status'] == 'failed'


def test_generated_first_use_requires_exact_completed_preview_then_one_apply(board):
    record, data = image_record(generated=True, required=True)
    def composition(prepared):
        result = edit_result(board, prepared)
        result['commands'].append({'op': 'add_object', 'page_id': board[1],
            'object': new_object('image', image_ref=record['image_ref'], x=800, y=400)})
        return result
    controller, executor = make_controller(board, composition, resource_resolver=lambda ref: data)
    before = board[0].teacher_view()
    request_id, result = complete(controller, executor, selected_images=[record])
    assert result['status'] == 'awaiting_confirmation'
    assert result['confirmation_reasons'] == ['first_generated_image_use']
    assert board[0].teacher_view() == before
    assert controller.preview(request_id)['pages'][0]['objects'][-1]['image_ref'] == record['image_ref']
    with pytest.raises(BoardAgentError):
        controller.confirm(request_id, 'different preview')
    assert controller.confirm(request_id, result['proposal_digest'])['status'] == 'applied'
    with pytest.raises(BoardAgentError):
        controller.confirm(request_id, result['proposal_digest'])


def test_saved_approved_library_image_ordinary_add_is_direct(board):
    record, data = image_record()
    controller, executor = make_controller(board, lambda prepared: result_envelope(prepared, commands=[{
        'op': 'add_object', 'page_id': board[1], 'object': new_object('image', image_ref=record['image_ref'])}]),
        resource_resolver=lambda ref: data)
    _, result = complete(controller, executor, selected_images=[record])
    assert result['status'] == 'applied' and not result['requires_confirmation']


@pytest.mark.parametrize('template_name', ['title_body', 'title_image'])
def test_whole_page_template_replacement_preview_deterministic_layout_confirm_and_undo(board, template_name):
    record, data = image_record()
    template = {'name': template_name, 'title': 'The water cycle',
                'body': 'Water evaporates, condenses and returns as rain.',
                'image_ref': record['image_ref'] if template_name == 'title_image' else None}
    controller, executor = make_controller(board, lambda prepared: result_envelope(prepared, template=template),
                                            resource_resolver=lambda ref: data)
    before = board[0].teacher_view()
    request_id, result = complete(controller, executor, selected_images=[record])
    assert result['status'] == 'awaiting_confirmation'
    assert result['confirmation_reasons'] == ['whole_page_replacement']
    assert board[0].teacher_view() == before
    assert controller.confirm(request_id, result['proposal_digest'])['status'] == 'applied'
    after = board[0].teacher_view()
    assert after['document']['pages'][0]['title'] == 'The water cycle'
    assert after['document']['pages'][1] == before['document']['pages'][1]
    restored = board[0].teacher_undo(expected_revision=after['revision'], expected_token=after['token'])
    assert restored['document']['pages'] == before['document']['pages']


def test_empty_page_template_can_publish_directly_and_supplied_wording_survives():
    session = BoardSession()
    fake = (session, session.teacher_view()['page_id'], None, None, None)
    controller, executor = make_controller(fake, lambda prepared: result_envelope(prepared, template={
        'name': 'title_body', 'title': 'Rainfall in millimetres', 'body': 'Keep this exactly.', 'image_ref': None}))
    _, result = complete(controller, executor, required_wording=['Keep this exactly.'])
    assert result['status'] == 'applied'
    assert 'Keep this exactly.' in json.dumps(session.pupil_view())


def test_destructive_commands_removing_every_original_object_need_preview(board):
    controller, executor = make_controller(board, lambda prepared: result_envelope(prepared, commands=[
        {'op': 'remove_object', 'page_id': board[1], 'object_id': obj['id']} for obj in board[2:4]]))
    _, result = complete(controller, executor)
    assert result['status'] == 'awaiting_confirmation'
    assert result['confirmation_reasons'] == ['whole_page_replacement']


@pytest.mark.parametrize('after_preview', ['edit', 'missing_media'])
def test_confirmation_revalidates_revision_and_required_media(board, after_preview):
    record, data = image_record(generated=True)
    available = [True]
    def resolver(ref):
        if not available[0]:
            raise OSError('removed after preview')
        return data
    controller, executor = make_controller(board, lambda prepared: result_envelope(prepared, commands=[{
        'op': 'add_object', 'page_id': board[1], 'object': new_object('image', image_ref=record['image_ref'])}]),
        resource_resolver=resolver)
    request_id, result = complete(controller, executor, selected_images=[record])
    if after_preview == 'edit':
        apply(board[0], [{'op': 'update_object', 'page_id': board[1], 'object_id': board[2]['id'], 'changes': {'text': 'Newer work'}}])
    else:
        available[0] = False
    before = board[0].teacher_view()
    assert controller.confirm(request_id, result['proposal_digest'])['status'] in {'stale', 'failed'}
    assert board[0].teacher_view() == before


def test_resource_preparation_reseals_exact_snapshot_before_composition(board):
    record, data = image_record(generated=True, required=True)
    seen = []
    def resources(prepared, report, cancelled):
        report('acquiring', 'Saving a reusable resource before composition.')
        return [record]
    resources.remote = False
    def composition(prepared):
        seen.append(prepared)
        return result_envelope(prepared, commands=[{'op': 'add_object', 'page_id': board[1],
            'object': new_object('image', image_ref=record['image_ref'])}])
    controller, executor = make_controller(board, composition, resource_preparer=resources, resource_resolver=lambda ref: data)
    prepared = controller.prepare('Add a required image')
    request_id = controller.start(prepared)
    executor.run()
    result = controller.poll(request_id)
    assert result['status'] == 'awaiting_confirmation'
    assert seen[0]['context_sha256'] != prepared['context_sha256']
    assert seen[0]['request_id'] == prepared['request_id']
    assert controller.confirm(request_id, result['proposal_digest'])['status'] == 'applied'


def test_reselected_current_exact_image_is_coalesced_without_losing_required_or_generated_guard(board):
    record, data = image_record()
    acquired = copy.deepcopy(record)
    acquired.update(required=True, generated_unreviewed=True)
    seen = []
    def resources(*args):
        return [acquired]
    resources.remote = False
    def composition(prepared):
        seen.append(json.loads(prepared['context']))
        return result_envelope(prepared, commands=[{'op': 'add_object', 'page_id': board[1],
            'object': new_object('image', image_ref=record['image_ref'])}])
    controller, executor = make_controller(board, composition, resource_preparer=resources, resource_resolver=lambda ref: data)
    _, result = complete(controller, executor, selected_images=[record])
    assert result['status'] == 'awaiting_confirmation'
    assert result['confirmation_reasons'] == ['first_generated_image_use']
    assert len(seen[0]['selected_images']) == 1
    assert seen[0]['selected_images'][0]['required'] and seen[0]['selected_images'][0]['generated_unreviewed']


def test_coalesced_trusted_chart_kind_and_credit_survive_reselection(board):
    record, data = chart_record()
    acquired = copy.deepcopy(record)
    acquired['credit'] = 'Teacher supplied class dataset'
    record.pop('visual_kind')
    def resources(*args):
        return [acquired]
    resources.remote = False
    seen = []
    def composition(prepared):
        seen.append(json.loads(prepared['context'])['selected_images'])
        return result_envelope(prepared, commands=[
            {'op': 'add_object', 'page_id': board[1], 'object': new_object('image', image_ref=record['image_ref'], x=80,y=100,width=1080,height=540)},
            {'op': 'add_object', 'page_id': board[1], 'object': new_object('text', text=acquired['credit'], x=80,y=770,width=1400,height=100,font_size=20)},
        ])
    controller, executor = make_controller(board, composition, resource_preparer=resources, resource_resolver=lambda ref: data)
    _, result = complete(controller, executor, selected_images=[record])
    assert result['status'] == 'applied', result
    assert len(seen[0]) == 1 and seen[0][0]['credit'] == acquired['credit'] and seen[0][0]['visual_kind'] == 'chart'


@pytest.mark.parametrize('conflict', ['asset', 'hash', 'width', 'height', 'credit', 'visual_kind'])
def test_same_version_conflicting_trusted_acquisition_metadata_never_publishes(board, conflict):
    record, data = image_record()
    record.update(credit='Original teacher credit', visual_kind='image')
    acquired = copy.deepcopy(record)
    if conflict == 'asset':
        acquired['image_ref']['asset_id'] = str(uuid.uuid4())
    elif conflict == 'hash':
        acquired['image_ref']['sha256'] = 'b'*64
    elif conflict in ('width', 'height'):
        acquired[conflict] += 1
    elif conflict == 'credit':
        acquired['credit'] = 'Conflicting creator credit'
    else:
        acquired['visual_kind'] = 'chart'
    def resources(*args):
        return [acquired]
    resources.remote = False
    controller, executor = make_controller(board, resource_preparer=resources, resource_resolver=lambda ref: data)
    before = board[0].pupil_view()
    _, result = complete(controller, executor, selected_images=[record])
    assert result['status'] == 'failed'
    assert board[0].pupil_view() == before


def test_required_commons_credit_cannot_be_removed_by_model(board):
    record, data = image_record()
    record['credit'] = 'Photo by A. Teacher, CC BY 4.0, https://creativecommons.org/licenses/by/4.0/'
    controller, executor = make_controller(board, lambda prepared: result_envelope(prepared, commands=[{
        'op': 'add_object', 'page_id': board[1], 'object': new_object('image', image_ref=record['image_ref'])}]),
        resource_resolver=lambda ref: data)
    before = board[0].teacher_view()
    _, result = complete(controller, executor, selected_images=[record])
    assert result['status'] == 'failed' and 'credit is missing' in result['message']
    assert board[0].teacher_view() == before


def test_image_template_puts_required_credit_in_readable_reserved_footer(board):
    record, data = image_record()
    record['credit'] = 'Photo by A. Teacher, CC BY 4.0, https://creativecommons.org/licenses/by/4.0/'
    controller, executor = make_controller(board, lambda prepared: result_envelope(prepared, template={
        'name': 'title_image', 'title': 'Water cycle', 'body': 'Water evaporates.', 'image_ref': record['image_ref']}),
        resource_resolver=lambda ref: data)
    request_id, result = complete(controller, executor, selected_images=[record])
    assert result['status'] == 'awaiting_confirmation'
    objects = controller.preview(request_id)['pages'][0]['objects']
    footer = next(obj for obj in objects if obj.get('text') == record['credit'])
    assert footer['font_size'] == 20 and footer['y'] == 770
    assert all(obj['y'] + obj['height'] <= footer['y'] for obj in objects if obj is not footer)
    assert controller.confirm(request_id, result['proposal_digest'])['status'] == 'applied'


@pytest.mark.parametrize('style', ['tiny', 'low_contrast', 'covered', 'rotated', 'readable'])
def test_required_credit_needs_readable_contrast_size_and_unobscured_space(board, style):
    record, data = image_record()
    record['credit'] = 'Photo by A. Teacher, CC BY 4.0'
    def composition(prepared):
        credit = new_object('text', text=record['credit'], x=70, y=770, width=1400, height=100,
                            font_size=20, colour='#374151')
        if style == 'tiny':
            credit['font_size'] = 1
        elif style == 'low_contrast':
            credit['colour'] = '#EEEEEE'
        elif style == 'rotated':
            credit['rotation'] = 90
        commands = [{'op': 'add_object', 'page_id': board[1],
            'object': new_object('image', image_ref=record['image_ref'], x=800, y=400)},
            {'op': 'add_object', 'page_id': board[1], 'object': credit}]
        if style == 'covered':
            commands.append({'op': 'add_object', 'page_id': board[1],
                'object': new_object('shape', x=70, y=770, width=1400, height=100)})
        return result_envelope(prepared, commands=commands)
    controller, executor = make_controller(board, composition, resource_resolver=lambda ref: data)
    before = board[0].pupil_view()
    _, result = complete(controller, executor, selected_images=[record])
    assert result['status'] == ('applied' if style == 'readable' else 'failed')
    if style != 'readable':
        assert board[0].pupil_view() == before


def chart_record(width=1440, height=720):
    record, _ = image_record(required=True)
    stream = io.BytesIO(); Image.new('RGB', (width, height), 'white').save(stream, format='PNG')
    data = stream.getvalue()
    record.update(width=width, height=height, visual_kind='chart', title='Rainfall in millimetres')
    record['image_ref']['sha256'] = hashlib.sha256(data).hexdigest()
    return record, data


@pytest.mark.parametrize('template_name', ['title_chart', 'title_image'])
def test_full_width_chart_template_or_promoted_image_keeps_readable_source_scale(board, template_name):
    record, data = chart_record()
    controller, executor = make_controller(board, lambda prepared: result_envelope(prepared, template={
        'name': template_name, 'title': 'Rainfall in millimetres', 'body': 'Compare the measured monthly rainfall.',
        'image_ref': record['image_ref']}), resource_resolver=lambda ref: data)
    request_id, result = complete(controller, executor, selected_images=[record])
    assert result['status'] == 'awaiting_confirmation', result
    objects = controller.preview(request_id)['pages'][0]['objects']
    chart = next(obj for obj in objects if obj['type'] == 'image')
    assert chart['width'] >= 1080 and chart['height'] >= 540
    assert chart['y'] >= 280 and chart['y'] + chart['height'] <= 850
    assert chart['width']/record['width'] == pytest.approx(chart['height']/record['height'])
    assert controller.confirm(request_id, result['proposal_digest'])['status'] == 'applied'


@pytest.mark.parametrize('failure', ['source_too_large', 'long_body', 'half_width_command', 'distorted_command', 'untrusted_kind'])
def test_chart_layout_refuses_unreadable_scale_or_unsupported_trusted_kind(board, failure):
    record, data = chart_record(2400, 1200) if failure == 'source_too_large' else chart_record()
    if failure == 'untrusted_kind':
        record.pop('visual_kind')
    def composition(prepared):
        if failure in {'half_width_command', 'distorted_command'}:
            return result_envelope(prepared, commands=[{'op': 'add_object', 'page_id': board[1],
                'object': new_object('image', image_ref=record['image_ref'], x=80, y=100,
                                     width=600 if failure == 'half_width_command' else 1200, height=540)}])
        return result_envelope(prepared, template={'name': 'title_chart', 'title': 'Rainfall',
            'body': 'x'*161 if failure == 'long_body' else 'Measured rainfall.', 'image_ref': record['image_ref']})
    controller, executor = make_controller(board, composition, resource_resolver=lambda ref: data)
    before = board[0].pupil_view()
    _, result = complete(controller, executor, selected_images=[record])
    assert result['status'] == 'failed'
    assert board[0].pupil_view() == before


@pytest.mark.parametrize('failure', ['long_credit', 'long_body', 'unsupported_template', 'hidden_command'])
def test_templates_reject_overflow_and_unsupported_executable_payload(board, failure):
    record, data = image_record()
    if failure == 'long_credit':
        record['credit'] = 'Credit '*70
    def composition(prepared):
        template = {'name': 'title_image', 'title': 'Water cycle', 'body': 'Water evaporates.', 'image_ref': record['image_ref']}
        if failure == 'long_body':
            template['body'] = 'x'*561
        if failure == 'unsupported_template':
            template['name'] = 'run_code'
        result = result_envelope(prepared, template=template)
        if failure == 'hidden_command':
            result['commands'] = edit_result(board, prepared)['commands']
        return result
    controller, executor = make_controller(board, composition, resource_resolver=lambda ref: data)
    before = board[0].teacher_view()
    _, result = complete(controller, executor, selected_images=[record])
    assert result['status'] == 'failed'
    assert board[0].teacher_view() == before


@pytest.mark.parametrize('failure', ['false', 'raise', 'concurrent_edit'])
def test_renderer_layout_validator_runs_before_publication_and_cannot_mutate_candidate(board, failure):
    calls = []
    def validator(document, page_id):
        calls.append((document, page_id))
        document['title'] = 'Mutating the copy cannot alter owned candidate'
        if failure == 'false':
            return False
        if failure == 'raise':
            raise BoardAgentError('The explanation does not fit. Shorten it.')
        apply(board[0], [{'op': 'update_object', 'page_id': board[1], 'object_id': board[2]['id'], 'changes': {'text': 'New teacher edit'}}])
    controller, executor = make_controller(board, page_validator=validator)
    _, result = complete(controller, executor)
    assert len(calls) == 1 and calls[0][1] == board[1]
    assert result['status'] in {'failed', 'stale'}
    if failure == 'raise':
        assert 'Shorten it' in result['message']
    assert 'Warmth causes evaporation.' not in json.dumps(board[0].teacher_view())


def test_confirmation_rechecks_renderer_and_close_prevents_late_publication(board):
    checks = []
    controller, executor = make_controller(board, lambda prepared: result_envelope(prepared, template={
        'name': 'title_body', 'title': 'New page', 'body': 'Evaporation.', 'image_ref': None}),
        page_validator=lambda document, page_id: checks.append(page_id))
    request_id, result = complete(controller, executor)
    assert result['status'] == 'awaiting_confirmation'
    assert controller.confirm(request_id, result['proposal_digest'])['status'] == 'applied'
    assert checks == [board[1], board[1]]
    later = controller.start(controller.prepare('Another explanation'))
    before = board[0].teacher_view()
    controller.close()
    executor.run()
    assert controller.snapshot(later)['status'] == 'cancelled'
    with pytest.raises(BoardAgentError, match='closed'):
        controller.poll(later)
    assert board[0].teacher_view() == before


def test_local_only_blocks_unknown_remote_composer_before_any_worker_call(board):
    calls = []
    def remote(*args):
        calls.append(True)
    controller = BoardAgentController(board[0], composer=remote, executor=ManualExecutor())
    with pytest.raises(BoardAgentError, match='local-only'):
        controller.start(controller.prepare('Explain', local_only=True))
    assert not calls
    local, executor = make_controller(board)
    _, result = complete(local, executor, local_only=True)
    assert result['status'] == 'applied'


def test_owner_thread_is_the_only_publication_authority(board):
    controller, executor = make_controller(board)
    request_id = controller.start(controller.prepare('Explain'))
    executor.run()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pytest.raises(BoardAgentError, match='owning UI thread'):
            pool.submit(controller.poll, request_id).result()
    assert controller.poll(request_id)['status'] == 'applied'


class FakeHermesService:
    def __init__(self, result, states=None):
        self.result, self.states = result, list(states or [{'status': 'completed', 'run_id': 'run-1'}])
        self.calls = []
        self.selection = None

    def prepare(self, task, context):
        self.calls.append('prepare')
        self.selection = {'task': task, 'context': context}
        return {'request_id': 'saved-hermes-request'}

    def submit(self, request_id):
        self.calls.append(('submit', request_id))
        return self.states.pop(0)

    def poll(self, request_id):
        self.calls.append(('poll', request_id))
        return self.states.pop(0)

    def preview(self, request_id):
        self.calls.append(('preview', request_id))
        return {**self.selection, 'status': 'completed', 'text': self.result}

    def discard(self, request_id):
        self.calls.append(('discard', request_id))

    def stop(self, request_id):
        self.calls.append(('stop', request_id))
        return {'status': 'stopping'}


def test_hermes_adapter_uses_exact_prepared_service_identity_poll_and_preview(board):
    controller, _ = make_controller(board)
    prepared = controller.prepare('Explain')
    expected = json.dumps(edit_result(board, prepared))
    service = FakeHermesService(expected, [{'status': 'running', 'run_id': 'run-1'}, {'status': 'completed', 'run_id': 'run-1'}])
    adapter = HermesBoardComposer(service, wait=lambda cancelled: None)
    assert adapter(prepared, lambda *args: None, lambda: False) == expected
    assert service.calls == ['prepare', ('submit', 'saved-hermes-request'), ('poll', 'saved-hermes-request'), ('preview', 'saved-hermes-request')]
    assert service.selection == {'task': prepared['task'], 'context': prepared['context']}
    with pytest.raises(BoardAgentError):
        adapter(prepared, lambda *args: None, lambda: False)
    assert service.calls.count('prepare') == 1


@pytest.mark.parametrize('state', [{'status': 'uncertain'}, {'status': 'http_error'}, {'status': 'failed', 'run_id': 'run-1'},
    {'status': 'local_only'}, {'status': 'unknown'}, {'status': 'running', 'run_id': 'run-1', 'approval_pending': True}])
def test_hermes_failure_uncertainty_and_approval_do_not_retry_or_publish(board, state):
    service = FakeHermesService('{}', [state])
    adapter = HermesBoardComposer(service, wait=lambda cancelled: None)
    controller = BoardAgentController(board[0], composer=adapter, executor=ManualExecutor())
    before = board[0].teacher_view()
    request_id = controller.start(controller.prepare('Explain'))
    controller._executor.run()
    assert controller.poll(request_id)['status'] == 'failed'
    assert board[0].teacher_view() == before
    assert service.calls == ['prepare', ('submit', 'saved-hermes-request')]


def test_hermes_cancel_before_dispatch_discards_same_prepared_identity(board):
    controller, _ = make_controller(board)
    prepared = controller.prepare('Explain')
    service = FakeHermesService('{}')
    adapter = HermesBoardComposer(service)
    with pytest.raises(BoardAgentError):
        adapter(prepared, lambda *args: None, lambda: True)
    assert service.calls == ['prepare', ('discard', 'saved-hermes-request')]


def test_hermes_cancel_after_dispatch_requests_stop_without_claiming_termination(board):
    controller, _ = make_controller(board)
    prepared = controller.prepare('Explain')
    cancelled = [False]
    service = FakeHermesService('{}', [{'status': 'running', 'run_id': 'run-1'}])
    original_submit = service.submit
    def submit(request_id):
        cancelled[0] = True
        return original_submit(request_id)
    service.submit = submit
    adapter = HermesBoardComposer(service)
    with pytest.raises(BoardAgentError, match='reconcile'):
        adapter(prepared, lambda *args: None, lambda: cancelled[0])
    assert service.calls[-1] == ('stop', 'saved-hermes-request')


def test_hermes_local_only_makes_no_service_calls(board):
    controller, _ = make_controller(board)
    prepared = controller.prepare('Explain', local_only=True)
    service = FakeHermesService('{}')
    adapter = HermesBoardComposer(service)
    with pytest.raises(BoardAgentError, match='local-only'):
        adapter(prepared, lambda *args: None, lambda: False)
    assert service.calls == []
