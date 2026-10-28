"""Save-complaint probes: kill mid-save, unwritable folders, freeze, two windows, long lessons.

Headless Qt and BoardStore only. No provider calls, firmware writes or live Windows UI.
"""
from __future__ import annotations

import errno
import io
import json
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import board_candidate as gui
from board_images import prepare_file
from board_model import BoardConflictError, BoardModel, new_object, new_page
from board_session import BoardSession
from board_store import BoardStore, BoardStoreError
from desktop_instance import LessonInstances
from media_store import MediaStore


COMPOSE_ROOT = Path(__file__).resolve().parents[1]


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


def png_bytes(size=(48, 32), colour='teal'):
    stream = io.BytesIO()
    Image.new('RGB', size, colour).save(stream, 'PNG')
    return stream.getvalue()


def write_png(path, size=(48, 32), colour='teal'):
    path.write_bytes(png_bytes(size, colour))
    return path


def test_sigkill_before_replace_leaves_the_last_complete_checkpoint(tmp_path):
    """Unclean exit after writing .board-pending-* but before os.replace."""
    if os.name == 'nt':
        pytest.skip('SIGKILL mid-save is a POSIX process-kill check')
    root = tmp_path / 'isolated-lesson'
    store = BoardStore(root)
    model = BoardModel()
    model.apply([{'op': 'rename_lesson', 'title': 'Committed before kill'}], expected_revision=0)
    store.save(model)
    committed = (root / 'lesson.json').read_bytes()

    script = r'''
import os, signal, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from board_model import BoardModel
from board_store import BoardStore
root = Path(sys.argv[2])
store = BoardStore(root)
model = store.load()
model.apply([{'op': 'rename_lesson', 'title': 'Must not survive kill'}], expected_revision=model.revision)
real_replace = os.replace
def die_before_current(source, destination):
    if Path(destination).name == 'lesson.json':
        Path(sys.argv[3]).write_text('ready', encoding='utf-8')
        os.kill(os.getpid(), signal.SIGKILL)
    return real_replace(source, destination)
os.replace = die_before_current
store.save(model)
'''
    marker = tmp_path / 'killed'
    result = subprocess.run(
        [sys.executable, '-c', script, str(COMPOSE_ROOT), str(root), str(marker)],
        capture_output=True, text=True, timeout=20)
    assert result.returncode != 0
    assert marker.read_text(encoding='utf-8') == 'ready'
    assert (root / 'lesson.json').read_bytes() == committed
    recovered = BoardStore(root).load()
    assert recovered.snapshot()['title'] == 'Committed before kill'
    pending = list(root.glob('.board-pending-*'))
    assert pending, 'SIGKILL must skip the pending-file cleanup'


def test_sigkill_during_the_first_save_leaves_no_promoted_lesson(tmp_path):
    if os.name == 'nt':
        pytest.skip('SIGKILL mid-save is a POSIX process-kill check')
    root = tmp_path / 'brand-new'
    script = r'''
import os, signal, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from board_model import BoardModel
from board_store import BoardStore
root = Path(sys.argv[2])
store = BoardStore(root)
model = BoardModel()
model.apply([{'op': 'rename_lesson', 'title': 'Never committed'}], expected_revision=0)
real_replace = os.replace
def die_before_current(source, destination):
    if Path(destination).name == 'lesson.json':
        os.kill(os.getpid(), signal.SIGKILL)
    return real_replace(source, destination)
os.replace = die_before_current
store.save(model)
'''
    result = subprocess.run(
        [sys.executable, '-c', script, str(COMPOSE_ROOT), str(root)],
        capture_output=True, text=True, timeout=20)
    assert result.returncode != 0
    assert not (root / 'lesson.json').exists()
    with pytest.raises(BoardStoreError, match='No saved lesson'):
        BoardStore(root).load()


def test_read_only_or_full_folder_keeps_the_last_checkpoint_and_stays_dirty(editor):
    editor.add_object('text')
    assert editor.save_now()
    saved = editor.store.current_path.read_bytes()
    editor.add_object('text')
    assert editor.session.teacher_view()['dirty']

    def refuse(destination, data):
        raise OSError(errno.ENOSPC, 'No space left on device')

    with patch.object(editor.store, '_atomic_write', side_effect=refuse):
        assert not editor.save_now()
    assert editor.session.teacher_view()['dirty']
    assert 'save failed' in editor.session.teacher_view()['save_error'].casefold()
    assert editor.store.current_path.read_bytes() == saved

    def read_only(destination, data):
        raise OSError(errno.EROFS, 'Read-only file system')

    with patch.object(editor.store, '_atomic_write', side_effect=read_only):
        assert not editor.save_now()
    assert editor.session.teacher_view()['dirty']
    assert editor.store.current_path.read_bytes() == saved


def test_chmod_read_only_folder_refuses_save_when_the_process_is_not_root(editor):
    if os.name == 'nt' or os.geteuid() == 0:
        pytest.skip('chmod is not an effective write barrier for this process')
    editor.add_object('text')
    assert editor.save_now()
    saved = editor.store.current_path.read_bytes()
    editor.add_object('rectangle')
    mode = editor.store.root.stat().st_mode
    os.chmod(editor.store.root, 0o555)
    try:
        assert not editor.save_now()
        assert editor.session.teacher_view()['dirty']
        assert editor.store.current_path.read_bytes() == saved
    finally:
        os.chmod(editor.store.root, mode)


def test_save_while_frozen_persists_teacher_edits_but_not_the_freeze(editor, tmp_path, monkeypatch):
    candidate_root = tmp_path / 'candidate'
    candidate_root.mkdir()
    monkeypatch.setattr(gui, 'CANDIDATE_ROOT', candidate_root)
    editor.add_page()
    second = editor.session.teacher_view()['page_id']
    editor.freeze()
    assert editor.session.teacher_view()['frozen']
    path = write_png(tmp_path / 'frozen.png', (80, 40), 'navy')
    assert editor.insert_prepared_image(prepare_file(path))
    pinned = editor.session.pupil_view()
    assert not any(obj['type'] == 'image' for page in pinned['document']['pages'] for obj in page['objects'])
    assert editor.save_now()
    assert not editor.save_copy()
    assert 'Resume the pupil display' in editor.error
    assert not editor.session.teacher_view()['dirty']
    assert editor.session.teacher_view()['frozen']
    lesson = json.loads(editor.store.current_path.read_text(encoding='utf-8'))
    assert 'frozen' not in lesson['state']['document']
    assert json.loads((editor.store.root / gui.VIEW_STATE_NAME).read_text(encoding='utf-8'))['page_id'] == second
    editor.session.close()
    reopened_store = BoardStore(editor.store.root)
    reopened = gui.BoardCandidate(BoardSession.open(reopened_store, image_resolver=gui.image_resolver(
        MediaStore(editor.store.root / 'media'))), store=reopened_store,
        resolver=gui.image_resolver(MediaStore(editor.store.root / 'media')))
    try:
        view = reopened.session.teacher_view()
        assert not view['frozen']
        assert view['page_id'] == second
        page = gui.page_from(view)
        assert any(obj['type'] == 'image' for obj in page['objects'])
        assert reopened.session.resolve_image(next(obj['image_ref'] for obj in page['objects'] if obj['type'] == 'image'))
    finally:
        reopened.save_timer.stop(); reopened.property_timer.stop(); reopened.group_timer.stop()
        reopened.session.close(); reopened.pupil.hide(); reopened.hide(); reopened.deleteLater()


def test_two_teacher_windows_cannot_own_or_clobber_the_same_lesson(app, tmp_path):
    root = tmp_path / 'shared-lesson'
    first_store = BoardStore(root)
    first = gui.BoardCandidate(BoardSession(BoardModel(), store=first_store,
                                            image_resolver=gui.image_resolver(MediaStore(root / 'media'))),
                               store=first_store, resolver=gui.image_resolver(MediaStore(root / 'media')))
    owners = LessonInstances()
    second = None
    try:
        owners.claim_lesson(root)
        with pytest.raises(ValueError, match='already open'):
            LessonInstances().claim_lesson(root)
        first.add_object('text')
        assert first.save_now()
        second_store = BoardStore(root)
        second = gui.BoardCandidate(BoardSession.open(second_store, image_resolver=gui.image_resolver(
            MediaStore(root / 'media'))), store=second_store, resolver=gui.image_resolver(MediaStore(root / 'media')))
        first.add_object('text')
        assert first.save_now()
        second.add_object('rectangle')
        assert not second.save_now()
        assert 'save failed' in second.session.teacher_view()['save_error'].casefold()
        reopened = BoardStore(root).load()
        page = reopened.snapshot()['pages'][0]
        kinds = [obj['type'] for obj in page['objects']]
        assert kinds == ['text', 'text']
        assert 'rectangle' not in {obj.get('shape') for obj in page['objects']}
        held = BoardStore(root)
        with first_store._exclusive():
            with pytest.raises(BoardStoreError, match='busy'):
                held.save(BoardModel())
    finally:
        owners.release()
        for window in (first, second):
            if window is None:
                continue
            window.save_timer.stop(); window.property_timer.stop(); window.group_timer.stop()
            if not window.session._closed:
                window.session.close()
            window.pupil.hide(); window.hide(); window.deleteLater()
        app.processEvents()


def test_overlapping_saves_from_two_stores_leave_one_complete_checkpoint(tmp_path):
    root = tmp_path / 'race'
    first, second = BoardStore(root), BoardStore(root)
    model = BoardModel()
    first.save(model)
    a, b = first.load(), second.load()
    started = threading.Barrier(2)
    errors = []

    def writer(store, owned, title):
        owned.apply([{'op': 'rename_lesson', 'title': title}], expected_revision=owned.revision)
        started.wait()
        try:
            store.save(owned)
        except Exception as error:
            errors.append(error)

    workers = [
        threading.Thread(target=writer, args=(first, a, 'Writer A')),
        threading.Thread(target=writer, args=(second, b, 'Writer B')),
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=5)
        assert not worker.is_alive()
    recovered = BoardStore(root).load()
    assert recovered.snapshot()['title'] in {'Writer A', 'Writer B'}
    assert errors, 'one overlapping saver must be refused'
    assert any(isinstance(error, (BoardStoreError, BoardConflictError)) for error in errors)


def test_long_lesson_with_many_images_saves_and_reopens_on_the_last_page(editor, tmp_path):
    page_ids = [editor.session.teacher_view()['page_id']]
    for index in range(9):
        editor.add_page()
        page_ids.append(editor.session.teacher_view()['page_id'])
    inserted = []
    for index, page_id in enumerate(page_ids):
        view = editor.session.teacher_view()
        editor.session.teacher_navigate(page_id, expected_token=view['token'])
        for copy in range(2):
            path = write_png(tmp_path / f'p{index}-{copy}.png', (36 + index, 24 + copy),
                             (40 + index * 8, 80, 120 + copy * 40))
            assert editor.insert_prepared_image(prepare_file(path))
            inserted.append(gui.page_from(editor.session.teacher_view())['objects'][-1]['image_ref'])
    last_page = editor.session.teacher_view()['page_id']
    assert editor.save_now()
    assert len(inserted) == 20
    assert json.loads((editor.store.root / gui.VIEW_STATE_NAME).read_text(encoding='utf-8'))['page_id'] == last_page
    editor.session.close()
    store = BoardStore(editor.store.root)
    reopened = gui.BoardCandidate(BoardSession.open(store, image_resolver=gui.image_resolver(
        MediaStore(store.root / 'media'))), store=store, resolver=gui.image_resolver(MediaStore(store.root / 'media')))
    try:
        view = reopened.session.teacher_view()
        assert view['page_id'] == last_page
        assert len(view['document']['pages']) == 10
        found = []
        for page in view['document']['pages']:
            for obj in page['objects']:
                if obj['type'] == 'image':
                    found.append(obj['image_ref'])
                    assert reopened.session.resolve_image(obj['image_ref'])
        assert found == inserted
        assert not reopened.session.teacher_view()['dirty']
    finally:
        reopened.save_timer.stop(); reopened.property_timer.stop(); reopened.group_timer.stop()
        reopened.session.close(); reopened.pupil.hide(); reopened.hide(); reopened.deleteLater()


def test_session_save_during_freeze_does_not_write_freeze_into_the_checkpoint(tmp_path):
    store = BoardStore(tmp_path / 'lesson')
    session = BoardSession(BoardModel(), store=store)
    apply_view = session.teacher_view()
    session.teacher_apply([{'op': 'add_page', 'page': new_page('Later')},
                           {'op': 'add_object', 'page_id': apply_view['page_id'],
                            'object': new_object('text', text='Keep me')}],
                          expected_revision=apply_view['revision'], expected_token=apply_view['token'])
    session.freeze(expected_token=session.teacher_view()['token'])
    session.save(expected_token=session.teacher_view()['token'])
    reopened = BoardSession.open(BoardStore(store.root))
    assert not reopened.teacher_view()['frozen']
    assert any(obj.get('text') == 'Keep me' for obj in reopened.teacher_view()['document']['pages'][0]['objects'])
