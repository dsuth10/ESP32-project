"""A plain image request uses typed application layout, including full credits."""
import io
import json
from pathlib import Path
import sys
import time

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_agent import BoardAgentController, result_envelope
from board_model import BoardModel, new_object
from board_session import BoardSession
from board_runtime import PrimaryBoardComposer
from media_store import MediaStore
from board_recovery import BoardRecoveryStore


def setup(tmp_path, monkeypatch, *, generated=False):
    store = MediaStore(tmp_path / 'media')
    data = io.BytesIO(); Image.new('RGB', (120, 160), '#c19a6b').save(data, 'PNG')
    image = store.import_bytes(data.getvalue(), title='A dog', origin='generated' if generated else 'web')
    session = BoardSession(BoardModel(), image_resolver=lambda ref: store.blob_path(ref['sha256']).read_bytes())
    composer = PrimaryBoardComposer({'LOCAL_ONLY': '0'})
    calls = []
    def malformed(task, raw):
        calls.append(raw)
        context = json.loads(raw)
        # The actual failure omitted schema, used type instead of op and sent
        # an incomplete object. Do not weaken Board validation to accept it.
        return json.dumps({'request_id': context['request_id'], 'operation': 'edit',
                           'commands': [{'type': 'add_object', 'object': {'type': 'image'}}]})
    monkeypatch.setattr(composer, 'complete', malformed)
    controller = BoardAgentController(session, composer=composer)
    selected = {'image_ref': {k:image[k] for k in ('asset_id', 'version_id', 'sha256')},
                'title': 'A dog', 'width':120, 'height':160, 'required':True,
                'generated_unreviewed':generated,
                'credit':'A dog — by Fixture Photographer — ' + 'A detailed source title and source URL. ' * 9 + 'CC BY 4.0'}
    return session, controller, composer, selected, calls


def finish(controller, request_id):
    for _ in range(200):
        state = controller.poll(request_id)
        if state['status'] != 'working': return state
        time.sleep(.005)
    pytest.fail('Image placement did not finish')


def test_plain_dog_request_publishes_cached_image_without_model_command_guessing(tmp_path, monkeypatch):
    session, controller, _, image, calls = setup(tmp_path, monkeypatch)
    try:
        prepared = controller.prepare('I need you to put an image of a dog up on the teaching board.', selected_images=[image])
        state = finish(controller, controller.start(prepared))
        assert state['status'] == 'applied', state['message']
        page = session.pupil_view()['document']['pages'][0]
        picture = next(o for o in page['objects'] if o['type'] == 'image')
        assert picture['image_ref'] == image['image_ref']
        assert picture['width'] / picture['height'] == pytest.approx(.75)
        assert any(o.get('text') == image['credit'] for o in page['objects'])
        assert calls == [], 'A plain image placement needs no second model call'
        view = session.teacher_view()
        session.teacher_undo(expected_revision=view['revision'], expected_token=view['token'])
        assert not session.pupil_view()['document']['pages'][0]['objects']
        view = session.teacher_view()
        session.teacher_redo(expected_revision=view['revision'], expected_token=view['token'])
        assert session.pupil_view()['document']['pages'][0]['objects'] == page['objects']
    finally:
        controller.close(); session.close()


def test_generated_image_still_requires_first_use_preview(tmp_path, monkeypatch):
    session, controller, _, image, calls = setup(tmp_path, monkeypatch, generated=True)
    try:
        request = controller.start(controller.prepare('Put an image of a dog on the teaching board.', selected_images=[image]))
        state = finish(controller, request)
        assert state['status'] == 'awaiting_confirmation', state['message']
        assert 'first_generated_image_use' in state['confirmation_reasons']
        assert not session.pupil_view()['document']['pages'][0]['objects']
        assert controller.confirm(request, state['proposal_digest'])['status'] == 'applied'
        assert calls == []
    finally:
        controller.close(); session.close()


@pytest.mark.parametrize('instruction', [
    'I need you to generate an image of a horse and put it up on the board',
    'Generate an image of a horse and put it on the board.',
    'Please create a picture of a horse and display it on the teaching board.',
    'Could you draw an illustration of a horse and then show it on the board?',
    'Make me an image of a horse.',
])
def test_generation_and_placement_phrasing_uses_typed_layout_and_preview(tmp_path, monkeypatch, instruction):
    session, controller, _, image, calls = setup(tmp_path, monkeypatch, generated=True)
    try:
        request = controller.start(controller.prepare(instruction, selected_images=[image]))
        state = finish(controller, request)
        assert state['status'] == 'awaiting_confirmation', state
        assert not session.pupil_view()['document']['pages'][0]['objects']
        assert controller.confirm(request, state['proposal_digest'])['status'] == 'applied'
        assert calls == []
    finally:
        controller.close(); session.close()


@pytest.mark.parametrize('instruction', [
    'Put an image of a dog on the board and explain its features.',
    'Put an image of a dog with labels on the board.',
    'Compare dogs and cats.',
])
def test_complex_briefs_still_reach_composer(tmp_path, monkeypatch, instruction):
    session, controller, composer, image, calls = setup(tmp_path, monkeypatch)
    try:
        composer(controller.prepare(instruction, selected_images=[image]), lambda *a:None, lambda:False)
        assert len(calls) == 1
    finally:
        controller.close(); session.close()


def test_existing_content_is_never_replaced_by_simple_image_layout(tmp_path, monkeypatch):
    session, controller, composer, image, calls = setup(tmp_path, monkeypatch)
    try:
        page = session.teacher_view()['page_id']
        view = session.teacher_view()
        session.teacher_apply([{'op':'add_object','page_id':page,'object':new_object('text',text='Keep this teaching content')}],
                              expected_revision=view['revision'], expected_token=view['token'])
        composer(controller.prepare('Put an image of a dog on the board.', selected_images=[image]), lambda *a:None, lambda:False)
        assert len(calls) == 1
        assert session.teacher_view()['document']['pages'][0]['objects'][0]['text'] == 'Keep this teaching content'
    finally:
        controller.close(); session.close()


def test_invalid_model_response_is_saved_as_not_presented(tmp_path, monkeypatch):
    session, controller, _, image, _ = setup(tmp_path, monkeypatch)
    controller.recovery_store = BoardRecoveryStore(tmp_path / 'requests')
    try:
        request = controller.start(controller.prepare('Explain dogs and add a picture.', selected_images=[image]))
        state = finish(controller, request)
        assert state['status'] == 'failed'
        record = controller.recovery_store.get(request)
        assert record['status'] == 'needs_attention'
        assert 'not presented' in record['message']
        assert record['result'], 'Retain the original response for diagnosis'
    finally:
        controller.close(); session.close()


def test_native_layout_fits_long_source_url_and_retains_exact_credit(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from board_agent_ui import validate_page_layout
    app = QApplication.instance() or QApplication([])
    session, controller, _, image, _ = setup(tmp_path, monkeypatch)
    image['credit'] = ('Dog photo — by Fixture Photographer — Own work — '
        'https://commons.wikimedia.org/wiki/File:Search_and_Rescue_Dog_Long_Filename_With_Underscores_2026.jpg '
        '— CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/) — Changes: Scaled to fit; no crop')
    controller.page_validator = lambda document, page: validate_page_layout(document,page)
    try:
        request = controller.start(controller.prepare('Put an image of a dog on the teaching board.', selected_images=[image]))
        state = finish(controller, request)
        assert state['status'] == 'applied', state['message']
    finally:
        controller.close(); session.close()
