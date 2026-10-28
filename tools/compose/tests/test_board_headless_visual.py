"""Headless teacher/pupil screenshots for the Add image workflow.

Saves captures under .local/board-tester-debug/screenshots/. Qt offscreen only;
this is not a Windows or classroom pass.
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem, QInputDialog

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import board_candidate as gui
import board_lessons
from board_image_picker import ImagePicker
from board_images import prepare_file
from board_model import BoardModel
from board_session import BoardSession
from board_store import BoardStore
from media_store import MediaStore


EVIDENCE = Path(__file__).resolve().parents[3] / '.local' / 'board-tester-debug' / 'screenshots'


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def write_png(path, size, colour):
    Image.new('RGB', size, colour).save(path, 'PNG')


def grab(window, name):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    window.show(); window.pupil.show(); QApplication.processEvents()
    window.grab().save(str(EVIDENCE / f'{name}-teacher.png'))
    window.pupil.grab().save(str(EVIDENCE / f'{name}-pupil.png'))
    pixmaps = [item for item in window.pupil_canvas.scene().items() if isinstance(item, QGraphicsPixmapItem)]
    return pixmaps


def test_headless_add_image_formats_move_resize_save_freeze_and_copy(app, tmp_path, monkeypatch):
    candidate_root = tmp_path / 'candidate'
    candidate_root.mkdir()
    monkeypatch.setattr(gui, 'CANDIDATE_ROOT', candidate_root)
    monkeypatch.setattr(board_lessons, 'CANDIDATE_ROOT', candidate_root)
    files = tmp_path / 'files'; files.mkdir()
    write_png(files / 'plain.png', (320, 180), '#1d4ed8')
    Image.new('RGB', (640, 400), '#b45309').save(files / 'photo.jpg', 'JPEG', quality=90)
    Image.new('RGB', (200, 200), '#15803d').save(files / 'tile.webp', 'WEBP')
    Image.new('RGB', (2400, 1600), '#0f766e').save(files / 'large.jpg', 'JPEG', quality=85)
    write_png(files / 'tiny.png', (12, 12), '#e11d48')
    Image.new('RGBA', (180, 120), (30, 64, 175, 120)).save(files / 'transparent.png', 'PNG')
    (files / 'wrong.jpg').write_bytes((files / 'plain.png').read_bytes())
    (files / 'corrupt.png').write_bytes(b'this is not an image')
    jpeg = Image.new('RGB', (80, 40), '#1e3a8a')
    jpeg.putpixel((0, 0), (255, 255, 255))
    exif = Image.Exif(); exif[0x0112] = 6
    jpeg.save(files / 'phone.jpg', 'JPEG', exif=exif, quality=95)

    library = MediaStore(tmp_path / 'library')
    library.import_bytes((files / 'plain.png').read_bytes(), 'Library PNG', tags=['fixture'],
                         source={'attribution': 'Dummy library', 'licence': 'CC0'})

    store = BoardStore(candidate_root / 'review')
    resolver = gui.image_resolver(MediaStore(store.root / 'media'))
    window = gui.BoardCandidate(BoardSession(BoardModel(), store=store, image_resolver=resolver),
                                store=store, resolver=resolver)
    notes = []
    try:
        window.show(); window.pupil.show(); app.processEvents()
        grab(window, '00-blank')
        for index, name in enumerate(('plain.png', 'photo.jpg', 'tile.webp', 'large.jpg',
                                      'tiny.png', 'transparent.png', 'phone.jpg'), start=1):
            prepared = prepare_file(files / name)
            assert window.insert_prepared_image(prepared), (name, window.error)
            obj = gui.page_from(window.session.teacher_view())['objects'][-1]
            pixmaps = grab(window, f'{index:02d}-insert-{Path(name).stem}')
            assert pixmaps and not pixmaps[0].pixmap().isNull(), name
            notes.append(f'{name}: {obj["width"]:.0f}x{obj["height"]:.0f} pupil_pixmaps={len(pixmaps)}')
            window.undo()
        # Content is trusted over the extension: PNG bytes named .jpg still insert.
        assert window.insert_prepared_image(prepare_file(files / 'wrong.jpg'))
        grab(window, '07b-wrong-extension-png-bytes')
        window.undo()
        with pytest.raises(ValueError):
            prepare_file(files / 'corrupt.png')
        picker = ImagePicker(window, library_root=library.root, decoder=gui.decode_image)
        assert picker.prepared is not None
        picker.grab().save(str(EVIDENCE / 'library-picker.png'))
        assert window.insert_prepared_image(picker.prepared)
        picker.deleteLater()
        obj = gui.page_from(window.session.teacher_view())['objects'][-1]
        window.select(obj['id'])
        window.fields['x'].setValue(120); window.fields['y'].setValue(80)
        assert window.flush_pending_edits()
        grab(window, '08-moved')
        window.fields['width'].setValue(max(obj['width'] * 1.3, 300))
        assert window.flush_pending_edits()
        locked = gui.page_from(window.session.teacher_view())['objects'][-1]
        assert locked['width'] / locked['height'] == pytest.approx(obj['width'] / obj['height'], rel=1e-3, abs=0.01)
        grab(window, '09-resize-locked')
        window.aspect_lock.setChecked(False)
        window.fields['height'].setValue(locked['height'] * 0.7)
        assert window.flush_pending_edits()
        grab(window, '10-resize-unlocked')
        window.undo(); window.redo()
        grab(window, '11-undo-redo')
        window.freeze()
        pinned = window.session.pupil_view()
        window.add_object('text')
        assert window.session.pupil_view() == pinned
        grab(window, '12-frozen')
        window.resume()
        grab(window, '13-resumed')
        assert window.save_now()
        monkeypatch.setattr(QInputDialog, 'getText', lambda *args, **kwargs: ('Screenshot copy', True))
        assert window.save_copy()
        grab(window, '14-save-copy')
        (EVIDENCE / 'notes.txt').write_text('\n'.join(notes), encoding='utf-8')
        assert (EVIDENCE / '02-insert-photo-pupil.png').is_file()
        assert (EVIDENCE / '12-frozen-pupil.png').is_file()
        assert (EVIDENCE / '14-save-copy-teacher.png').is_file()
    finally:
        window.save_timer.stop(); window.property_timer.stop(); window.group_timer.stop()
        window.session.close(); window.pupil.hide(); window.hide(); window.deleteLater()
        app.processEvents()
