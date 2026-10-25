"""Frame geometry and native synthetic mouse gestures; no physical acceptance."""
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_resize import HANDLES, handle_positions, local_to_scene, resize_frame


@pytest.mark.parametrize('handle', HANDLES)
@pytest.mark.parametrize('angle', (0, 37, 90, -120))
def test_rotated_resize_preserves_opposite_anchor(handle, angle):
    original = dict(x=200, y=180, width=300, height=160, rotation=angle)
    fx, fy = HANDLES[handle]
    target = local_to_scene(original, (fx*420-(1-fx)*120, fy*250-(1-fy)*90))
    resized = {**original, **resize_frame(original, handle, target)}
    fixed_before = local_to_scene(original, ((1-fx)*300, (1-fy)*160))
    fixed_after = local_to_scene(resized, ((1-fx)*resized['width'], (1-fy)*resized['height']))
    assert fixed_after == pytest.approx(fixed_before)
    if fx != .5:
        assert resized['width'] > original['width']
    if fy != .5:
        assert resized['height'] > original['height']


@pytest.mark.parametrize('handle', HANDLES)
def test_aspect_locked_handles_preserve_ratio_and_fixed_anchor(handle):
    original = dict(x=100, y=100, width=680, height=397, rotation=25)
    fx, fy = HANDLES[handle]
    target = local_to_scene(original, (fx*900-(1-fx)*220, fy*500-(1-fy)*103))
    resized = {**original, **resize_frame(original, handle, target, keep_aspect=True)}
    assert resized['width']/resized['height'] == pytest.approx(680/397)
    assert local_to_scene(resized, ((1-fx)*resized['width'], (1-fy)*resized['height'])) == pytest.approx(
        local_to_scene(original, ((1-fx)*680, (1-fy)*397)))


def test_crossing_edge_stops_without_flipping_and_bounds_stay_finite():
    original = dict(x=100, y=100, width=300, height=160, rotation=0)
    resized = resize_frame(original, 'nw', (10000, 10000))
    assert resized == pytest.approx(dict(x=399.9, y=259.9, width=.1, height=.1))
    locked = resize_frame(original, 'se', (1e9, 1e9), keep_aspect=True)
    assert max(locked['width'], locked['height']) == pytest.approx(100000)
    assert locked['width']/locked['height'] == pytest.approx(300/160)
    assert all(math.isfinite(value) for value in locked.values())


@pytest.fixture(scope='module')
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def candidate(app, tmp_path):
    from board_candidate import BoardCandidate, demo_model, image_resolver
    from board_session import BoardSession
    from board_store import BoardStore
    from media_store import MediaStore
    media = MediaStore(tmp_path/'media'); store = BoardStore(tmp_path)
    resolver = image_resolver(media)
    session = BoardSession(demo_model(media), store=store, image_resolver=resolver)
    window = BoardCandidate(session, store=store, resolver=resolver)
    window.show(); window.pupil.show(); app.processEvents()
    yield window
    window.save_timer.stop()
    if hasattr(window, 'property_timer'):
        window.property_timer.stop()
    window.session.close(); window.pupil.hide(); window.hide(); window.deleteLater()
    app.processEvents()


def value_of(candidate, object_id):
    from board_candidate import page_from
    return next(o for o in page_from(candidate.session.teacher_view())['objects'] if o['id'] == object_id)


def mouse_drag(candidate, object_id, handle, dx, dy, *, release=True):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtTest import QTest
    candidate.select(object_id)
    canvas = candidate.teacher_canvas
    point = canvas.mapFromScene(QPointF(*handle_positions(value_of(candidate, object_id))[handle]))
    QTest.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, pos=point)
    QTest.mouseMove(canvas.viewport(), point+QPoint(dx, dy))
    if release:
        QTest.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=point+QPoint(dx, dy))


def test_native_text_drag_previews_then_commits_one_edit_with_font_unchanged(candidate):
    from board_candidate import page_from
    value = next(o for o in page_from(candidate.session.teacher_view())['objects'] if o['type'] == 'text')
    original = value.copy(); revision = candidate.session.teacher_view()['revision']
    mouse_drag(candidate, value['id'], 'e', -70, 0, release=False)
    assert candidate.teacher_canvas.resize_state is not None
    assert candidate.session.teacher_view()['revision'] == revision
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    canvas = candidate.teacher_canvas
    point = canvas.mapFromScene(QPointF(*handle_positions(original)['e']))
    QTest.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=point)
    # A fresh complete gesture changes frame width without changing font size.
    mouse_drag(candidate, value['id'], 'e', -70, 0)
    resized = value_of(candidate, value['id'])
    assert resized['width'] < original['width']
    assert resized['font_size'] == original['font_size']
    assert candidate.session.teacher_view()['revision'] == revision+1
    assert candidate.session.pupil_view()['document'] == candidate.session.teacher_view()['document']
    candidate.undo()
    assert value_of(candidate, value['id'])['width'] == original['width']
    candidate.redo()
    assert value_of(candidate, value['id'])['width'] == resized['width']


def test_native_image_lock_unlock_and_shape_free_resize(candidate):
    from board_candidate import page_from
    values = page_from(candidate.session.teacher_view())['objects']
    image = next(o for o in values if o['type'] == 'image')
    mouse_drag(candidate, image['id'], 'e', 35, 0)
    resized = value_of(candidate, image['id'])
    assert resized['width']/resized['height'] == pytest.approx(image['width']/image['height'])
    candidate.aspect_locks[image['id']] = False
    before = resized.copy()
    mouse_drag(candidate, image['id'], 'e', 35, 0)
    resized = value_of(candidate, image['id'])
    assert resized['height'] == pytest.approx(before['height'])
    assert resized['width'] > before['width']
    shape = next(o for o in values if o['type'] == 'shape')
    mouse_drag(candidate, shape['id'], 's', 0, 30)
    resized_shape = value_of(candidate, shape['id'])
    assert resized_shape['width'] == shape['width']
    assert resized_shape['height'] > shape['height']


def test_resize_cancelled_on_navigation_and_teacher_edits_stay_private_when_frozen(candidate):
    from board_candidate import page_from
    value = page_from(candidate.session.teacher_view())['objects'][0]
    initial = candidate.session.teacher_view()['document']
    mouse_drag(candidate, value['id'], 'e', -50, 0, release=False)
    candidate.navigate(1)
    assert candidate.teacher_canvas.resize_state is None
    assert candidate.session.teacher_view()['document'] == initial
    candidate.navigate(-1); candidate.freeze()
    pinned = candidate.session.pupil_view()
    mouse_drag(candidate, value['id'], 'e', -50, 0)
    assert value_of(candidate, value['id'])['width'] < value['width']
    assert candidate.session.pupil_view() == pinned
    assert candidate.pupil_canvas.selected_frame() is None
    candidate.resume()
    assert candidate.session.pupil_view()['document'] == candidate.session.teacher_view()['document']
    for _ in range(20):
        candidate.select(value['id']); candidate.navigate(1); candidate.navigate(-1)
    assert candidate.teacher_canvas.resize_state is None


def test_stale_resize_is_cancelled_without_model_changes(candidate):
    from board_candidate import page_from
    value = page_from(candidate.session.teacher_view())['objects'][0]
    candidate.select(value['id']); assert candidate.teacher_canvas.begin_resize('e')
    view = candidate.session.teacher_view()
    candidate.session.freeze(expected_token=view['token'])
    candidate.teacher_canvas.preview_resize(candidate.teacher_canvas.mapFromScene(500, 500).toPointF())
    assert candidate.teacher_canvas.resize_state is None
    assert value_of(candidate, value['id']) == value


@pytest.mark.parametrize('audience', (False, True))
def test_pending_live_text_finishes_before_new_ink_capture(candidate, audience):
    from PySide6.QtCore import QPointF
    from board_candidate import page_from
    value = page_from(candidate.session.teacher_view())['objects'][0]
    candidate.select(value['id'])
    candidate.text.setPlainText('A live edit immediately before drawing')
    assert candidate._pending_fields == {'text'}
    canvas = candidate.pupil_canvas if audience else candidate.teacher_canvas
    canvas.begin_ink(QPointF(50, 150), 'mouse')
    assert not candidate._pending_fields
    assert value_of(candidate, value['id'])['text'] == 'A live edit immediately before drawing'
    capture = canvas.capture
    canvas.extend_ink(QPointF(100, 170))
    candidate.flush_pending_edits(); candidate.autosave()
    assert canvas.capture == capture and len(canvas.points) > 1
    canvas.finish_ink(QPointF(130, 190))
    assert page_from(candidate.session.teacher_view())['objects'][-1]['type'] == 'ink'
    assert not candidate.error


def test_stale_pending_edit_refuses_ink_and_frozen_pupil_does_not_flush(candidate):
    from PySide6.QtCore import QPointF
    from board_candidate import page_from
    value = page_from(candidate.session.teacher_view())['objects'][0]
    candidate.select(value['id']); candidate.freeze()
    candidate.text.setPlainText('Private pending draft')
    document = candidate.session.teacher_view()['document']
    candidate.pupil_canvas.begin_ink(QPointF(50, 150), 'mouse')
    assert candidate.session.teacher_view()['document'] == document
    assert candidate._pending_fields == {'text'}
    assert candidate.pupil_canvas.capture is None
    view = candidate.session.teacher_view()
    candidate.session.teacher_apply([dict(op='update_object', page_id=view['page_id'], object_id=value['id'],
                                         changes=dict(x=400))], expected_revision=view['revision'], expected_token=view['token'])
    candidate.teacher_canvas.begin_ink(QPointF(50, 150), 'mouse')
    assert candidate.teacher_canvas.capture is None
    assert candidate._pending_fields == {'text'}
    assert 'draft is retained' in candidate.error
