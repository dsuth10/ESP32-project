"""Native Qt image picker/editor tests, with synthetic local input only."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QFileDialog
import board_candidate as gui
from board_images import prepare_file, SavedImageLibrary
from board_image_picker import ImagePicker
from board_model import BoardModel
from board_session import BoardSession
from board_store import BoardStore
from media_store import MediaStore
from test_board_images import image_bytes


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def editor(app, tmp_path):
    media = MediaStore(tmp_path/'media'); store = BoardStore(tmp_path); resolver = gui.image_resolver(media)
    session = BoardSession(BoardModel(), store=store, image_resolver=resolver)
    candidate = gui.BoardCandidate(session, store=store, resolver=resolver)
    yield candidate
    candidate.save_timer.stop(); candidate.property_timer.stop(); candidate.group_timer.stop()
    candidate.session.close(); candidate.pupil.hide(); candidate.hide(); candidate.deleteLater(); app.processEvents()


def prepared_file(tmp_path):
    path = tmp_path / 'local.png'; path.write_bytes(image_bytes()); return path, prepare_file(path)


def test_insert_move_resize_undo_redo_and_offline_reopen(editor, tmp_path):
    source, prepared = prepared_file(tmp_path)
    editor.set_tool(False, 'Ink')
    assert editor.insert_prepared_image(prepared)
    view = editor.session.teacher_view(); obj = gui.page_from(view)['objects'][-1]
    assert editor.selected == obj['id']
    assert editor.mode.currentText() == 'Select / move'
    assert obj['width']/obj['height'] == pytest.approx(16/9)
    assert editor.is_aspect_locked(obj['id'])
    editor.undo(); assert not gui.page_from(editor.session.teacher_view())['objects']
    editor.redo(); assert gui.page_from(editor.session.teacher_view())['objects'][-1] == obj
    editor.select(obj['id']); editor.fields['width'].setValue(640); editor.flush_pending_edits()
    resized = gui.page_from(editor.session.teacher_view())['objects'][-1]
    assert resized['height'] == pytest.approx(360)
    editor.fields['x'].setValue(123); editor.flush_pending_edits()
    editor.end_property_group(); editor.save_now(); expected = editor.session.teacher_view()['document']
    source.unlink(); editor.reopen()
    assert editor.session.teacher_view()['document'] == expected
    assert editor.session.resolve_image(obj['image_ref']) == prepared.data
    assert not editor.media_unavailable
    editor.undo(); assert editor.session.teacher_view()['document']['revision'] > expected['revision']


def test_stale_picker_does_not_insert_on_a_changed_page(editor, tmp_path):
    _, prepared = prepared_file(tmp_path); captured = editor.session.teacher_view()
    editor.add_page(); before = editor.session.teacher_view()
    assert not editor.insert_prepared_image(prepared, captured)
    assert editor.session.teacher_view() == before
    assert 'changed while choosing' in editor.error


def test_frozen_insertion_is_private_until_resume(editor, tmp_path):
    _, prepared = prepared_file(tmp_path)
    editor.freeze(); pinned = editor.session.pupil_view()
    assert editor.insert_prepared_image(prepared)
    assert editor.session.pupil_view() == pinned
    editor.resume()
    assert editor.session.pupil_view()['document'] == editor.session.teacher_view()['document']


def test_undone_image_survives_save_reopen_and_redo(editor, tmp_path):
    source, prepared = prepared_file(tmp_path)
    assert editor.insert_prepared_image(prepared)
    reference = gui.page_from(editor.session.teacher_view())['objects'][-1]['image_ref']
    editor.undo(); editor.save_now(); source.unlink(); editor.reopen(); editor.redo()
    assert editor.session.resolve_image(reference) == prepared.data
    assert gui.page_from(editor.session.teacher_view())['objects'][-1]['image_ref'] == reference


def test_local_picker_preview_and_cancel(editor, tmp_path, monkeypatch):
    source, _ = prepared_file(tmp_path)
    picker = ImagePicker(editor, library_root=tmp_path/'absent', decoder=gui.decode_image)
    picker.tabs.setCurrentIndex(1)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(source), 'Images'))
    picker.choose_file()
    assert picker.prepared and picker.insert_button.isEnabled() and not picker.preview.pixmap().isNull()
    before = editor.session.teacher_view()
    picker.reject(); assert editor.session.teacher_view() == before
    picker.tabs.setCurrentIndex(0)
    assert picker.prepared is None and not picker.insert_button.isEnabled()
    picker.deleteLater()


def test_picker_defaults_canonical_and_allows_exact_older_version(editor, tmp_path):
    source = MediaStore(tmp_path/'source')
    first = source.import_bytes(image_bytes(), 'First')
    second = source.add_generated(image_bytes(colour='red'), 'Second', asset_id=first['asset_id'],
                                  parent_version_id=first['version_id'])
    source.set_canonical(first['asset_id'], first['version_id'])
    picker = ImagePicker(editor, library_root=source.root, decoder=gui.decode_image)
    assert picker.prepared.versions[-1]['version_id'] == first['version_id']
    picker.version_list.setCurrentRow(next(i for i, row in enumerate(picker.records)
                                          if row['version_id'] == second['version_id']))
    assert editor.insert_prepared_image(picker.prepared)
    assert gui.page_from(editor.session.teacher_view())['objects'][-1]['image_ref']['version_id'] == second['version_id']
    picker.deleteLater()


def test_add_image_button_accepts_one_prepared_choice(editor, tmp_path, monkeypatch):
    _, prepared = prepared_file(tmp_path)
    def accept_choice(picker):
        picker.prepared = prepared
        return picker.DialogCode.Accepted
    monkeypatch.setattr(ImagePicker, 'exec', accept_choice)
    editor.add_image_button.click()
    assert len(gui.page_from(editor.session.teacher_view())['objects']) == 1
    editor.undo()
    assert not gui.page_from(editor.session.teacher_view())['objects']


def test_corrupt_chooser_preference_recovers_without_creating_source(editor, tmp_path):
    (tmp_path / 'image-library-source.json').write_text('[]', encoding='utf-8')
    assert editor.image_library_root() == tmp_path / 'media'
