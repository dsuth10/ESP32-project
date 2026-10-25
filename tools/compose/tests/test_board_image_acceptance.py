"""Independent synthetic lesson lifecycle checks for the requested image workflow."""
import hashlib
import io
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import board_candidate as gui
from board_images import SavedImageLibrary, prepare_file
from board_lessons import copy_saved_lesson
from board_model import BoardModel
from board_resize import handle_positions
from board_session import BoardSession
from board_store import BoardStore
from media_store import MediaStore


def png(colour, size=(500, 300)):
    stream = io.BytesIO()
    Image.new('RGB', size, colour).save(stream, 'PNG')
    return stream.getvalue()


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
    window.session.close(); window.pupil.hide(); window.hide(); window.deleteLater()
    app.processEvents()


def image_object(editor):
    return next(obj for obj in gui.page_from(editor.session.teacher_view())['objects'] if obj['type'] == 'image')


def test_library_version_survives_source_loss_undo_reopen_and_independent_copy(editor, tmp_path):
    source = MediaStore(tmp_path / 'source-library')
    parent = source.import_bytes(png('blue'), 'Earlier diagram')
    child_bytes = png('green')
    child = source.add_generated(child_bytes, 'Chosen lesson diagram', asset_id=parent['asset_id'],
                                 parent_version_id=parent['version_id'], prompt='PRIVATE PROMPT',
                                 source={'attribution': 'Synthetic school fixture', 'licence': 'CC0'})
    library = SavedImageLibrary(source.root)
    chosen = next(row for row in library.versions(child['asset_id']) if row['version_id'] == child['version_id'])
    assert editor.insert_prepared_image(library.prepare(chosen))
    inserted = image_object(editor)
    assert inserted['image_ref'] == {key: child[key] for key in ('asset_id', 'version_id', 'sha256')}
    source.blob_path(child['sha256']).unlink()
    source.blob_path(parent['sha256']).unlink()
    assert editor.session.resolve_image(inserted['image_ref']) == child_bytes
    editor.undo(); assert not gui.page_from(editor.session.teacher_view())['objects']
    assert editor.save_now()
    editor.reopen(); editor.redo()
    assert image_object(editor) == inserted
    assert editor.save_now()
    copied, store, resolver = copy_saved_lesson(editor.session, editor.store.root,
                                               tmp_path / 'copy', 'Independent lesson')
    try:
        MediaStore(editor.store.root / 'media').blob_path(child['sha256']).unlink()
        copied_image = gui.page_from(copied.teacher_view())['objects'][0]
        assert copied.resolve_image(copied_image['image_ref']) == child_bytes
        metadata = MediaStore(store.root / 'media').get_version(copied_image['image_ref']['version_id'])
        assert metadata['source'] == child['source']
        with sqlite3.connect(store.root / 'media' / 'media.sqlite3') as database:
            assert not database.execute("SELECT 1 FROM local_prompt WHERE prompt != ''").fetchone()
        copied.close()
        reopened = BoardSession.open(BoardStore(store.root), image_resolver=resolver)
        try:
            assert reopened.resolve_image(copied_image['image_ref']) == child_bytes
        finally:
            reopened.close()
    finally:
        copied.close()


def test_fresh_local_image_mouse_numeric_resize_and_process_restart(editor, app, tmp_path):
    image_path = tmp_path / 'Portrait diagram.png'
    data = png('orange', (300, 600)); image_path.write_bytes(data)
    editor.show(); editor.pupil.show(); app.processEvents()
    editor.freeze(); pinned = editor.session.pupil_view()
    assert editor.insert_prepared_image(prepare_file(image_path))
    inserted = image_object(editor)
    assert inserted['width'] / inserted['height'] == pytest.approx(.5)
    assert editor.is_aspect_locked(inserted['id'])
    canvas = editor.teacher_canvas
    point = canvas.mapFromScene(QPointF(*handle_positions(inserted)['e']))
    QTest.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, pos=point)
    QTest.mouseMove(canvas.viewport(), point + QPoint(25, 0))
    QTest.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=point + QPoint(25, 0))
    dragged = image_object(editor)
    assert dragged['width'] > inserted['width']
    assert dragged['width'] / dragged['height'] == pytest.approx(.5)
    editor.fields['height'].setValue(dragged['height'] * .8)
    assert editor.flush_pending_edits()
    resized = image_object(editor)
    # Numeric controls display tenths of a logical unit; allow their rounding.
    assert abs(resized['width'] - .5 * resized['height']) <= .1
    assert editor.session.pupil_view() == pinned
    editor.resume()
    assert editor.session.pupil_view()['document'] == editor.session.teacher_view()['document']
    assert editor.save_now(); image_path.unlink()
    # A separate Python process proves reopen does not rely on GUI memory or source files.
    code = """
import hashlib, json, sys
sys.path.insert(0, sys.argv[1])
from board_lessons import local_image_resolver
from board_session import BoardSession
from board_store import BoardStore
from media_store import MediaStore
from pathlib import Path
root=Path(sys.argv[2])
session=BoardSession.open(BoardStore(root), image_resolver=local_image_resolver(MediaStore(root/'media')))
image=session.teacher_view()['document']['pages'][0]['objects'][0]
assert hashlib.sha256(session.resolve_image(image['image_ref'])).hexdigest()==sys.argv[3]
print(json.dumps(image))
"""
    result = subprocess.run([sys.executable, '-c', code, str(Path(gui.__file__).parent),
                             str(editor.store.root), hashlib.sha256(data).hexdigest()],
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == resized

