"""Native Qt integration checks; input is synthetic, not hardware acceptance."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem, QGraphicsItem
from board_candidate import (BoardCandidate, CANDIDATE_ROOT, candidate_directory,
                             validate_candidate_storage, demo_model, image_resolver, page_from)
from board_model import BoardModel
from board_session import BoardSession, BoardSessionError
from board_store import BoardStore
from media_store import MediaStore


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def candidate(app, tmp_path):
    media = MediaStore(tmp_path/'media')
    store = BoardStore(tmp_path)
    resolver = image_resolver(media)
    session = BoardSession(demo_model(media), store=store, image_resolver=resolver)
    window = BoardCandidate(session, store=store, resolver=resolver)
    yield window
    window.save_timer.stop()
    window.property_timer.stop(); window.group_timer.stop()
    window.session.close()
    window.pupil.hide(); window.hide(); window.deleteLater()
    app.processEvents()


def test_reserved_root_and_link_redirects_rejected(tmp_path):
    with pytest.raises(ValueError):
        candidate_directory(Path.home()/'ESP32ClassroomCompanion')
    outside = tmp_path/'outside'; outside.mkdir()
    root = tmp_path/'candidate'; root.mkdir()
    link = root/'media'
    if os.name == 'nt':
        import _winapi
        _winapi.CreateJunction(str(outside), str(link))
    else:
        link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='links|junctions'):
        validate_candidate_storage(root)


def test_large_logical_image_uses_bounded_source_pixmap(candidate):
    view = candidate.session.teacher_view(); page = page_from(view)
    image = next(o for o in page['objects'] if o['type'] == 'image')
    candidate.apply([dict(op='update_object', page_id=page['id'], object_id=image['id'],
                          changes=dict(width=100000, height=100000))])
    item = next(i for i in candidate.teacher_canvas.scene().items() if isinstance(i, QGraphicsPixmapItem))
    assert item.pixmap().width() == 480
    assert item.pixmap().height() == 280
    # Scene bounds can include Qt's selection decoration; measure drawn pixels.
    assert item.mapRectToScene(QRectF(0, 0, 480, 280)).width() == pytest.approx(100000)


def test_pixel_sized_wrapped_text(candidate):
    text = next(i for i in candidate.teacher_canvas.scene().items() if i.data(1) == 'text')
    assert text.font().pixelSize() > 0
    assert text.textWidth() > 0


def test_fixed_page_is_white_clipped_and_distinct_from_viewport(candidate):
    for canvas in (candidate.teacher_canvas, candidate.pupil_canvas):
        assert canvas.scene().backgroundBrush().color().name() == '#dde2e7'
        assert canvas.page_item.brush().color().name() == '#ffffff'
        assert canvas.page_item.rect().width() / canvas.page_item.rect().height() == pytest.approx(16/9)
        assert canvas.page_item.flags() & QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape
        assert all(item.parentItem() is not None for item in canvas.scene().items() if item.data(0))


def test_stale_property_form_cannot_restore_old_values(candidate):
    view = candidate.session.teacher_view(); page = page_from(view)
    obj = page['objects'][0]
    candidate.select(obj['id'])
    candidate.fields['x'].setValue(400)
    candidate.apply([dict(op='update_object', page_id=page['id'], object_id=obj['id'], changes=dict(x=999))])
    candidate.apply_properties()
    assert page_from(candidate.session.teacher_view())['objects'][0]['x'] == 999
    assert candidate.error
    candidate.reload_selected_fields()
    candidate.fields['x'].setValue(400)
    candidate.apply_properties()
    assert page_from(candidate.session.teacher_view())['objects'][0]['x'] == 400


def test_rename_undo_keeps_visible_name_truthful(candidate):
    original = candidate.session.teacher_view()['document']['title']
    candidate.name.setText('Renamed lesson'); candidate.name.setModified(True)
    candidate.capture_name_edit('Renamed lesson'); candidate.rename()
    assert candidate.session.teacher_view()['document']['title'] == 'Renamed lesson'
    candidate.undo()
    assert candidate.name.text() == original
    candidate.redo()
    assert candidate.name.text() == 'Renamed lesson'


def test_freeze_holds_pupil_view_and_disables_controls(candidate):
    candidate.freeze(); before = candidate.session.pupil_view()
    candidate.add_object('text'); candidate.navigate(1)
    assert candidate.session.pupil_view() == before
    assert not candidate.pupil_mode.isEnabled()
    assert all(not button.isEnabled() for button in candidate.pupil_nav)
    candidate.ink(True, [[10, 10], [100, 100]], (before['revision'], before['token'], 'synthetic'))
    assert candidate.session.pupil_view() == before
    candidate.resume()
    assert candidate.session.pupil_view()['document'] == candidate.session.teacher_view()['document']
    assert candidate.pupil_mode.isEnabled()


def test_save_only_refresh_preserves_in_progress_stroke(candidate):
    candidate.add_object('text')
    canvas = candidate.teacher_canvas
    canvas.begin_ink(QPointF(50, 50), 'mouse')
    canvas.extend_ink(QPointF(150, 150))
    capture, points = canvas.capture, canvas.points[:]
    candidate.autosave()
    assert canvas.capture == capture and canvas.points == points
    candidate.freeze()
    assert canvas.capture is None and canvas.points == []


def test_navigation_rejects_delayed_ink(candidate):
    before = candidate.session.teacher_view()
    candidate.navigate(1)
    count = sum(len(p['objects']) for p in candidate.session.teacher_view()['document']['pages'])
    candidate.ink(False, [[20, 20], [100, 100]], (before['revision'], before['token'], 'synthetic'))
    assert sum(len(p['objects']) for p in candidate.session.teacher_view()['document']['pages']) == count
    assert candidate.error


def test_save_failure_visible_and_retry_preserves_edits(candidate, monkeypatch):
    candidate.add_object('text')
    model = candidate.session.teacher_view()['document']
    original = candidate.store.save
    def fail(_model):
        raise OSError('synthetic storage refusal')
    monkeypatch.setattr(candidate.store, 'save', fail)
    candidate.autosave()
    assert candidate.session.teacher_view()['dirty']
    assert 'save failed' in candidate.status.text().lower()
    assert candidate.session.teacher_view()['document'] == model
    monkeypatch.setattr(candidate.store, 'save', original)
    candidate.autosave()
    assert not candidate.session.teacher_view()['dirty']


def test_reopen_preserves_state_history_and_invalidates_previous_session(candidate):
    candidate.add_object('text'); candidate.autosave()
    expected = candidate.session.teacher_view()['document']
    old_session = candidate.session
    candidate.reopen()
    assert candidate.session.teacher_view()['document'] == expected
    with pytest.raises(BoardSessionError):
        old_session.teacher_view()
    candidate.undo()
    assert candidate.session.teacher_view()['revision'] > expected['revision']


def test_previous_checkpoint_recovery_notice(candidate):
    candidate.autosave(); candidate.add_object('text'); candidate.autosave()
    candidate.store.current_path.write_text('synthetic damage', encoding='utf-8')
    candidate.reopen()
    assert candidate.recovery_notice
    assert 'Recovered previous save' in candidate.status.text()


def test_unavailable_image_is_placeholder_without_model_mutation(candidate):
    before = candidate.session.teacher_view()['document']
    candidate.session = BoardSession(BoardModel(before))
    candidate.teacher_canvas.view = None; candidate.pupil_canvas.view = None
    candidate.refresh()
    assert candidate.media_unavailable
    assert 'image is unavailable' in candidate.status.text()
    assert candidate.session.teacher_view()['document'] == before
    assert not any(isinstance(i, QGraphicsPixmapItem) for i in candidate.teacher_canvas.scene().items())
    assert all(not bool(i.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
               for i in candidate.pupil_canvas.scene().items())
