"""Live editor and lesson controls using native Qt and synthetic input only."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QInputDialog
import board_candidate as gui
from board_model import BoardModel, new_lesson
from board_session import BoardSession, BoardSessionError
from board_store import BoardStore
from media_store import MediaStore
import board_lessons


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def editor(app, tmp_path):
    media = MediaStore(tmp_path / 'media')
    store = BoardStore(tmp_path)
    resolver = gui.image_resolver(media)
    session = BoardSession(gui.demo_model(media), store=store, image_resolver=resolver)
    window = gui.BoardCandidate(session, store=store, resolver=resolver)
    yield window
    window.property_timer.stop(); window.group_timer.stop(); window.save_timer.stop()
    window.session.close(); window.pupil.hide(); window.hide(); window.deleteLater()
    app.processEvents()


def text_object(editor):
    return next(o for o in gui.page_from(editor.session.teacher_view())['objects'] if o['type'] == 'text')


def selected_object(editor):
    return next(o for o in gui.page_from(editor.session.teacher_view())['objects'] if o['id'] == editor.selected)


def test_text_updates_without_apply_and_preserves_caret(editor):
    editor.select(text_object(editor)['id'])
    editor.text.moveCursor(QTextCursor.MoveOperation.End)
    editor.text.insertPlainText(' changes live')
    position = editor.text.textCursor().position()
    QTest.qWait(170)
    assert selected_object(editor)['text'].endswith(' changes live')
    assert editor.text.textCursor().position() == position
    assert gui.page_from(editor.session.pupil_view())['objects'] == gui.page_from(editor.session.teacher_view())['objects']


def test_live_typing_burst_has_one_durable_undo_entry(editor):
    editor.select(text_object(editor)['id']); original = selected_object(editor)['text']
    editor.text.setPlainText('First live update'); assert editor.flush_pending_edits()
    editor.text.setPlainText('Second live update'); assert editor.flush_pending_edits()
    editor.autosave(); editor.reopen()
    editor.select(text_object(editor)['id']); editor.undo()
    assert selected_object(editor)['text'] == original
    editor.redo()
    assert selected_object(editor)['text'] == 'Second live update'


def test_typing_bursts_and_other_edits_do_not_merge(editor):
    object_count = len(gui.page_from(editor.session.teacher_view())['objects'])
    editor.select(text_object(editor)['id'])
    editor.text.setPlainText('First burst'); assert editor.flush_pending_edits()
    editor.end_property_group()
    editor.text.setPlainText('Second burst'); assert editor.flush_pending_edits()
    editor.undo()
    assert selected_object(editor)['text'] == 'First burst'
    editor.add_object('rectangle'); editor.undo()
    assert len(gui.page_from(editor.session.teacher_view())['objects']) == object_count


def test_pending_edit_flushes_before_navigation_and_reopen(editor):
    object_id = text_object(editor)['id']; editor.select(object_id)
    editor.text.setPlainText('Saved before page change')
    editor.navigate(1); editor.navigate(-1)
    editor.select(object_id)
    assert selected_object(editor)['text'] == 'Saved before page change'
    editor.fields['x'].setValue(321)
    editor.reopen(); editor.select(object_id)
    assert selected_object(editor)['x'] == 321


def test_stale_draft_is_retained_and_blocks_navigation_until_explicit_reload(editor):
    editor.select(text_object(editor)['id'])
    initial = editor.session.teacher_view(); page = gui.page_from(initial)
    editor.text.setPlainText('Uncommitted draft')
    editor.session.teacher_apply([dict(op='update_object', page_id=page['id'], object_id=editor.selected,
                                      changes={'text': 'Newer external edit'})],
                                 expected_revision=initial['revision'], expected_token=initial['token'])
    editor.navigate(1)
    assert editor.session.teacher_view()['page_id'] == initial['page_id']
    assert selected_object(editor)['text'] == 'Newer external edit'
    assert editor.text.toPlainText() == 'Uncommitted draft'
    assert editor._pending_fields and editor.error
    editor.reload_selected_fields()
    assert editor.text.toPlainText() == 'Newer external edit'
    editor.text.setPlainText('Reviewed new edit'); assert editor.flush_pending_edits()
    assert selected_object(editor)['text'] == 'Reviewed new edit'


def test_freeze_holds_live_edit_and_quick_pupil_controls(editor):
    editor.select(text_object(editor)['id']); editor.freeze()
    pinned = editor.session.pupil_view()
    editor.text.setPlainText('Teacher private change'); assert editor.flush_pending_edits()
    assert editor.session.pupil_view() == pinned
    assert all(not button.isEnabled() for button in editor.pupil_tools.values())
    editor.pupil_tools['Erase ink'].click()
    assert editor.pupil_mode.currentText() == 'Ink'
    editor.resume()
    assert editor.session.pupil_view()['document'] == editor.session.teacher_view()['document']
    editor.pupil_tools['Erase ink'].click()
    assert editor.pupil_mode.currentText() == 'Erase ink'
    assert editor.pupil_tools['Erase ink'].isChecked()
    assert not editor.pupil_tools['Ink'].isChecked()
    editor.teacher_tools['Ink'].click()
    assert editor.mode.currentText() == 'Ink'
    assert editor.teacher_tools['Ink'].isChecked()


def test_image_numeric_dimensions_lock_by_default_and_can_unlock(editor):
    image = next(o for o in gui.page_from(editor.session.teacher_view())['objects'] if o['type'] == 'image')
    editor.select(image['id']); assert editor.is_aspect_locked(image['id'])
    editor.fields['width'].setValue(image['width'] * 2)
    assert editor.flush_pending_edits()
    assert selected_object(editor)['height'] == pytest.approx(image['height'] * 2)
    editor.aspect_lock.setChecked(False)
    editor.fields['width'].setValue(image['width'])
    assert editor.flush_pending_edits()
    assert selected_object(editor)['height'] == pytest.approx(image['height'] * 2)
    editor.autosave(); editor.reopen(); editor.select(image['id'])
    assert editor.is_aspect_locked(image['id'])


def test_shape_dimensions_remain_independent(editor):
    editor.add_object('rectangle'); original_height = selected_object(editor)['height']
    editor.fields['width'].setValue(555)
    assert editor.flush_pending_edits()
    assert selected_object(editor)['height'] == original_height


def test_save_now_commits_pending_text_and_name_and_shows_location(editor):
    editor.select(text_object(editor)['id']); editor.text.setPlainText('Latest text')
    editor.name.setText('My saved lesson'); editor.name.setModified(True)
    assert editor.save_now()
    assert not editor.session.teacher_view()['dirty']
    assert editor.store.load().snapshot()['title'] == 'My saved lesson'
    assert str(editor.store.root) in editor.location.text()
    assert {'Save a copy', 'Open saved lessons', 'Save and close'} <= set(editor.file_buttons)


def test_name_draft_then_live_text_saves_both_on_first_click(editor):
    editor.select(text_object(editor)['id'])
    editor.name.setText('Name drafted before text'); editor.name.setModified(True)
    editor.capture_name_edit(editor.name.text())
    editor.text.setPlainText('New text after naming'); assert editor.flush_pending_edits()
    assert editor.save_now()
    saved = editor.store.load().snapshot()
    assert saved['title'] == 'Name drafted before text'
    assert next(o for o in saved['pages'][0]['objects'] if o['id'] == editor.selected)['text'] == 'New text after naming'


def test_name_draft_cannot_overwrite_competing_rename(editor):
    editor.name.setText('Stale intended name'); editor.name.setModified(True)
    editor.capture_name_edit(editor.name.text())
    view = editor.session.teacher_view()
    editor.session.teacher_apply([dict(op='rename_lesson', title='Newer independent name')],
                                 expected_revision=view['revision'], expected_token=view['token'])
    assert not editor.save_now()
    assert editor.session.teacher_view()['document']['title'] == 'Newer independent name'
    assert editor.name.text() == 'Stale intended name'
    assert editor.error


def test_copy_cancel_does_not_switch_session(editor, monkeypatch):
    source = editor.session
    monkeypatch.setattr(QInputDialog, 'getText', lambda *args, **kwargs: ('', False))
    assert not editor.save_copy()
    assert editor.session is source
    assert source.teacher_view()


def test_save_copy_opens_catalogue_containing_both_named_lessons(app, tmp_path, monkeypatch):
    """The real Save a copy -> Open lesson folder path must reveal both saves."""
    candidate_root = tmp_path / 'candidate'
    candidate_root.mkdir()
    monkeypatch.setattr(gui, 'CANDIDATE_ROOT', candidate_root)
    monkeypatch.setattr(board_lessons, 'CANDIDATE_ROOT', candidate_root)
    source = candidate_root / 'original'
    store = BoardStore(source)
    session = BoardSession(BoardModel(new_lesson('First saved lesson')), store=store)
    session.save(expected_token=session.teacher_view()['token'])
    (source / 'Open Teaching Board Lesson.cmd').write_text('@echo off\n', encoding='utf-8')
    window = gui.BoardCandidate(session, store=store)
    opened = []
    monkeypatch.setattr(QInputDialog, 'getText', lambda *args, **kwargs: ('Second saved lesson', True))
    monkeypatch.setattr(gui.QDesktopServices, 'openUrl', lambda url: opened.append(Path(url.toLocalFile())) or True)
    try:
        assert window.save_copy()
        window.open_lesson_folder()
        assert opened, 'Open lesson folder did not open any folder'
        catalogue = opened[-1]
        # A teacher needs one central folder with readable reopen entries for
        # both saved titles, rather than a UUID folder for only the active copy.
        launchers = [path.name for path in catalogue.glob('*.cmd')]
        assert any('First saved lesson' in name for name in launchers), (catalogue, launchers)
        assert any('Second saved lesson' in name for name in launchers), (catalogue, launchers)
        assert window.store.root.parent == catalogue / 'data'
        assert window.store.root.name.startswith('Second saved lesson -- ')
        window.name.setText('Renamed second lesson'); window.name.setModified(True)
        assert window.save_now()
        launchers = [path.name for path in catalogue.glob('*.cmd')]
        assert any('First saved lesson' in name for name in launchers)
        assert any('Renamed second lesson' in name for name in launchers)
        assert not any('Second saved lesson' in name for name in launchers)
    finally:
        window.property_timer.stop(); window.group_timer.stop(); window.save_timer.stop()
        window.session.close(); window.pupil.hide(); window.hide(); window.deleteLater()
        app.processEvents()


def test_catalogue_failure_reports_saved_data_separately(editor, monkeypatch):
    monkeypatch.setattr(gui, 'is_catalogue_lesson', lambda root: True)
    def unavailable(*args, **kwargs):
        raise OSError('synthetic catalogue unavailable')
    monkeypatch.setattr(gui, 'refresh_saved_lesson_access', unavailable)
    editor.select(text_object(editor)['id'])
    editor.text.setPlainText('Durably saved despite catalogue problem')
    assert editor.save_now()
    assert not editor.session.teacher_view()['dirty']
    assert 'Lesson saved, but Saved lessons could not be updated' in editor.status.text()
    assert 'synthetic catalogue unavailable' in editor.status.text()
    assert any(obj.get('text') == 'Durably saved despite catalogue problem'
               for page in editor.store.load().snapshot()['pages'] for obj in page['objects'])


def test_frozen_reopen_and_copy_cannot_publish_teacher_private_changes(editor, tmp_path):
    editor.select(text_object(editor)['id']); editor.freeze()
    pinned = editor.session.pupil_view()
    editor.text.setPlainText('Teacher private change'); assert editor.flush_pending_edits()
    source = editor.session
    assert not editor._save_copy(tmp_path / 'copy', 'Copy')
    assert editor.session is source and editor.session.pupil_view() == pinned
    editor.reopen()
    assert editor.session is source and editor.session.pupil_view() == pinned
    assert 'Resume' in editor.error


def test_copy_failure_keeps_source_active(editor, monkeypatch, tmp_path):
    source = editor.session; root = editor.store.root
    def fail(*args):
        raise OSError('Synthetic copy failure')
    monkeypatch.setattr(gui, 'copy_saved_lesson', fail)
    assert not editor._save_copy(tmp_path / 'copy', 'Copied lesson')
    assert editor.session is source and editor.store.root == root
    assert 'Synthetic copy failure' in editor.error
    assert source.teacher_view()


def test_copy_success_switches_only_after_complete_backend_result(editor, monkeypatch, tmp_path):
    source = editor.session
    destination = tmp_path / 'copy'
    replacement_store = BoardStore(destination)
    replacement_session = BoardSession(BoardModel(new_lesson('Copied lesson')), store=replacement_store)
    replacement_session.save(expected_token=replacement_session.teacher_view()['token'])
    def complete(session, root, target, title):
        assert session is source and source.teacher_view()
        return replacement_session, replacement_store, None
    monkeypatch.setattr(gui, 'copy_saved_lesson', complete)
    assert editor._save_copy(destination, 'Copied lesson')
    assert editor.session is replacement_session and editor.store is replacement_store
    assert 'Copied lesson' in editor.windowTitle()
    assert str(destination) in editor.location.text()
    with pytest.raises(BoardSessionError):
        source.teacher_view()


def test_close_flushes_live_text_to_saved_lesson(editor):
    object_id = text_object(editor)['id']; editor.select(object_id)
    editor.text.setPlainText('Saved on close')
    event = QCloseEvent(); editor.closeEvent(event)
    assert event.isAccepted()
    saved = editor.store.load().snapshot()
    assert next(o for o in saved['pages'][0]['objects'] if o['id'] == object_id)['text'] == 'Saved on close'


def test_failed_pending_flush_refuses_close_and_keeps_draft(editor):
    editor.select(text_object(editor)['id']); before = editor.session.teacher_view()
    editor.text.setPlainText('Keep draft')
    editor.session.teacher_navigate(before['document']['pages'][1]['id'], expected_token=before['token'])
    event = QCloseEvent(); editor.closeEvent(event)
    assert not event.isAccepted()
    assert editor.text.toPlainText() == 'Keep draft'
    assert editor.session.teacher_view()
