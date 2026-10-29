"""Regressions for Teaching Board save, tiny images, Add image placement and EXIF.

Headless Qt only. No provider calls, firmware writes or live Windows UI.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem, QInputDialog

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import board_candidate as gui
import board_lessons
from board_images import prepare_file, SavedImageLibrary
from board_model import BoardModel
from board_session import BoardSession
from board_store import BoardStore
from media_store import MediaStore


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def editor(app, tmp_path):
    store = BoardStore(tmp_path / 'lesson')
    resolver = gui.image_resolver(MediaStore(store.root / 'media'))
    window = gui.BoardCandidate(BoardSession(BoardModel(), store=store, image_resolver=resolver),
                                store=store, resolver=resolver)
    yield window
    window.save_timer.stop(); window.property_timer.stop(); window.group_timer.stop()
    if not window.session._closed:
        window.session.close()
    window.pupil.hide(); window.hide(); window.deleteLater()
    app.processEvents()


def png_bytes(size=(320, 180), colour='blue'):
    stream = io.BytesIO()
    Image.new('RGB', size, colour).save(stream, 'PNG')
    return stream.getvalue()


def exif_jpeg(size=(80, 40), orientation=6, colour='navy'):
    """Landscape pixels tagged as a 90° CW phone photo (displayed portrait)."""
    image = Image.new('RGB', size, colour)
    image.putpixel((0, 0), (255, 255, 255))
    exif = Image.Exif()
    exif[0x0112] = orientation
    stream = io.BytesIO()
    image.save(stream, 'JPEG', exif=exif, quality=95)
    return stream.getvalue()


def pixmap_items(canvas):
    return [item for item in canvas.scene().items() if isinstance(item, QGraphicsPixmapItem)]


def test_tiny_local_image_is_grown_to_a_usable_page_size(editor, tmp_path):
    path = tmp_path / 'icon.png'
    path.write_bytes(png_bytes((12, 12), 'green'))
    assert editor.insert_prepared_image(prepare_file(path))
    obj = gui.page_from(editor.session.teacher_view())['objects'][-1]
    assert obj['type'] == 'image'
    assert min(obj['width'], obj['height']) == pytest.approx(gui.MIN_INSERTED_IMAGE_SIDE)
    assert obj['width'] == pytest.approx(obj['height'])
    assert pixmap_items(editor.teacher_canvas)
    assert pixmap_items(editor.pupil_canvas)
    assert not pixmap_items(editor.pupil_canvas)[0].pixmap().isNull()


def test_large_photo_still_fits_within_sixty_percent_of_the_page(editor, tmp_path):
    path = tmp_path / 'photo.jpg'
    Image.new('RGB', (4000, 3000), '#334455').save(path, 'JPEG', quality=85)
    assert editor.insert_prepared_image(prepare_file(path))
    page = gui.page_from(editor.session.teacher_view())
    obj = page['objects'][-1]
    assert obj['width'] <= page['width'] * 0.6 + 0.1
    assert obj['height'] <= page['height'] * 0.6 + 0.1
    assert obj['width'] / obj['height'] == pytest.approx(4 / 3)


def test_add_image_stays_above_the_board_assistant(editor):
    assert editor.agent_panel is not None
    layout = editor.side_scroll.widget().layout()
    widgets = [layout.itemAt(index).widget() for index in range(layout.count())
               if layout.itemAt(index).widget() is not None]
    assert widgets.index(editor.add_image_button) < widgets.index(editor.agent_panel)
    assert editor.add_image_toolbar.text() == 'Add image…'


def test_exif_rotated_phone_photo_is_stored_and_placed_upright(editor, tmp_path):
    path = tmp_path / 'phone.jpg'
    original = exif_jpeg()
    path.write_bytes(original)
    prepared = prepare_file(path)
    assert (prepared.width, prepared.height) == (40, 80)
    assert prepared.data != original
    assert editor.insert_prepared_image(prepared)
    obj = gui.page_from(editor.session.teacher_view())['objects'][-1]
    assert obj['width'] / obj['height'] == pytest.approx(0.5)
    pixmap = pixmap_items(editor.pupil_canvas)[0].pixmap()
    assert pixmap.width() / pixmap.height() == pytest.approx(0.5)
    stored = editor.session.resolve_image(obj['image_ref'])
    mime, width, height = MediaStore._inspect(stored)
    assert (width, height) == (40, 80)
    assert mime == 'image/jpeg'


def test_save_close_copy_undo_freeze_and_fresh_process_keep_images(app, tmp_path, monkeypatch):
    """Reproduce the reported save failure across the teacher save/reopen paths."""
    candidate_root = tmp_path / 'candidate'
    candidate_root.mkdir()
    monkeypatch.setattr(gui, 'CANDIDATE_ROOT', candidate_root)
    monkeypatch.setattr(board_lessons, 'CANDIDATE_ROOT', candidate_root)
    lesson_root = candidate_root / 'review'
    library = MediaStore(tmp_path / 'saved-library')
    parent = library.import_bytes(png_bytes((200, 120), 'teal'), 'Water cycle', tags=['science'],
                                  source={'attribution': 'Synthetic fixture', 'licence': 'CC0'})
    child = library.add_generated(png_bytes((200, 120), 'orange'), 'Water cycle labelled',
                                  asset_id=parent['asset_id'], parent_version_id=parent['version_id'],
                                  source={'attribution': 'Synthetic fixture', 'licence': 'CC BY 4.0'})
    library.set_canonical(parent['asset_id'], child['version_id'])
    store = BoardStore(lesson_root)
    resolver = gui.image_resolver(MediaStore(store.root / 'media'))
    window = gui.BoardCandidate(BoardSession(BoardModel(), store=store, image_resolver=resolver),
                                store=store, resolver=resolver)
    try:
        window.show(); window.pupil.show(); app.processEvents()
        window.add_page()
        second_page = window.session.teacher_view()['page_id']
        picker = __import__('board_image_picker', fromlist=['ImagePicker']).ImagePicker(
            window, library_root=library.root, decoder=gui.decode_image)
        chosen = next(row for row in picker.records if row['version_id'] == child['version_id'])
        picker.version_list.setCurrentRow(next(i for i, row in enumerate(picker.records)
                                              if row['version_id'] == chosen['version_id']))
        assert window.insert_prepared_image(picker.prepared)
        picker.deleteLater()
        inserted = gui.page_from(window.session.teacher_view())['objects'][-1]
        assert inserted['image_ref']['version_id'] == child['version_id']
        window.fields['x'].setValue(80); assert window.flush_pending_edits()
        window.undo(); window.redo()
        window.freeze()
        pinned = window.session.pupil_view()
        window.add_object('text')
        assert window.session.pupil_view() == pinned
        window.resume()
        assert window.save_now()
        assert not window.session.teacher_view()['dirty']
        assert (lesson_root / 'lesson.json').is_file()
        assert json.loads((lesson_root / gui.VIEW_STATE_NAME).read_text(encoding='utf-8'))['page_id'] == second_page
        assert window.prepare_close()
        saved_document = window.session.teacher_view()['document']
        window.finish_close()
        app.processEvents()
    finally:
        if not window.session._closed:
            window.session.close()
        window.pupil.hide(); window.hide(); window.deleteLater()
        app.processEvents()

    library.root.joinpath('media.sqlite3').unlink()
    reopened_store = BoardStore(lesson_root)
    reopened = gui.BoardCandidate(BoardSession.open(reopened_store, image_resolver=gui.image_resolver(
        MediaStore(lesson_root / 'media'))), store=reopened_store,
        resolver=gui.image_resolver(MediaStore(lesson_root / 'media')))
    try:
        assert reopened.session.teacher_view()['page_id'] == second_page
        page = gui.page_from(reopened.session.teacher_view())
        image = next(obj for obj in page['objects'] if obj['type'] == 'image')
        assert image['image_ref'] == inserted['image_ref']
        assert reopened.session.resolve_image(image['image_ref'])
        assert pixmap_items(reopened.pupil_canvas)
        monkeypatch.setattr(QInputDialog, 'getText', lambda *args, **kwargs: ('Independent copy', True))
        assert reopened.save_copy()
        catalogue = board_lessons.refresh_saved_lesson_access((reopened.store.root,))
        titles = {entry['title'] for entry in catalogue['entries']}
        assert 'Untitled lesson' in titles or saved_document['title'] in titles
        assert 'Independent copy' in titles
        assert reopened.session.teacher_view()['page_id'] == second_page
    finally:
        reopened.save_timer.stop(); reopened.property_timer.stop(); reopened.group_timer.stop()
        reopened.session.close(); reopened.pupil.hide(); reopened.hide(); reopened.deleteLater()
        app.processEvents()

    code = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from board_candidate import BoardCandidate, image_resolver, VIEW_STATE_NAME
from board_session import BoardSession
from board_store import BoardStore
from media_store import MediaStore
from PySide6.QtWidgets import QApplication
root = Path(sys.argv[2])
app = QApplication([])
store = BoardStore(root)
resolver = image_resolver(MediaStore(root / 'media'))
window = BoardCandidate(BoardSession.open(store, image_resolver=resolver), store=store, resolver=resolver)
view = window.session.teacher_view()
page = next(p for p in view['document']['pages'] if p['id'] == view['page_id'])
image = next(o for o in page['objects'] if o['type'] == 'image')
print(json.dumps({'page_id': view['page_id'], 'expected': json.loads((root / VIEW_STATE_NAME).read_text())['page_id'],
                  'sha256': image['image_ref']['sha256'], 'objects': len(page['objects'])}))
window.session.close()
"""
    result = subprocess.run(
        [sys.executable, '-c', code, str(Path(gui.__file__).parent), str(lesson_root)],
        capture_output=True, text=True, check=False, env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload['page_id'] == payload['expected'] == second_page
    assert payload['sha256'] == inserted['image_ref']['sha256']
    assert payload['objects'] >= 1
