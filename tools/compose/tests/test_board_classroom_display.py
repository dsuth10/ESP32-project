"""Board pupil placement uses the Classroom display role. Qt offscreen only."""
from __future__ import annotations

from pathlib import Path
import sys

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from board_candidate import BoardCandidate
from board_model import BoardModel
from board_session import BoardSession
from board_store import BoardStore
from media_store import MediaStore
from monitor_shortcut import MISSING_DISPLAY_MESSAGE, load_shortcut_settings, save_shortcut_settings
from window_monitor_manager import BOARD_PUPIL_TITLE, MonitorInfo, Rect


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def board(app, tmp_path):
    root = tmp_path / 'lesson'
    media = MediaStore(root / 'media')
    store = BoardStore(root)
    session = BoardSession(BoardModel(), store=store, image_resolver=lambda *_: None)
    candidate = BoardCandidate(session, store=store)
    yield candidate
    if not candidate.session._closed:
        candidate.finish_close()
    candidate.pupil.hide()
    app.processEvents()


def _classroom():
    bounds = Rect(1920, 0, 3840, 1080)
    return MonitorInfo(
        2, 'Classroom panel', '\\\\.\\DISPLAY2', '\\\\?\\DISPLAY#BOARD', 'PRM', '0001',
        bounds, bounds, 96)


def test_board_selector_uses_classroom_display_name_not_display_index(board, tmp_path):
    settings_root = tmp_path / 'companion'
    settings = load_shortcut_settings(settings_root)
    settings['profiles']['Home']['classroom_display'] = _classroom().identity_record()
    save_shortcut_settings(settings, settings_root)
    board.watch_classroom_board_requests(settings_root)
    assert board.screens.count() == 1
    assert 'Display 1' not in board.screens.itemText(0)
    assert 'Display 2' not in board.screens.itemText(0)
    assert 'Classroom panel' in board.screens.itemText(0)
    assert 'Classroom panel' in board.classroom_display_label.text()


def test_move_pupil_missing_classroom_display_does_not_move(board, tmp_path, monkeypatch):
    settings_root = tmp_path / 'companion'
    classroom = _classroom()
    settings = load_shortcut_settings(settings_root)
    settings['profiles']['Home']['classroom_display'] = classroom.identity_record()
    settings['profiles']['Home']['last_seen_identities'] = [classroom.durable_key()]
    save_shortcut_settings(settings, settings_root)
    board.classroom_settings_root = settings_root
    laptop = MonitorInfo(
        1, 'Laptop', '\\\\.\\DISPLAY1', '\\\\?\\DISPLAY#LAPTOP', 'LGD', '0099',
        Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080), 96, is_primary=True)
    monkeypatch.setattr('window_monitor_manager.FakeWindowMonitorBackend.list_monitors',
                        lambda self: [laptop])
    before = board.session.pupil_view()
    origin = board.pupil.pos()
    board.move_pupil()
    assert board.error == MISSING_DISPLAY_MESSAGE
    assert board.session.pupil_view() == before
    assert board.pupil.pos() == origin


def test_bring_pupil_forward_while_frozen_does_not_resume_or_navigate(board, tmp_path):
    board.freeze()
    pinned = board.session.pupil_view()
    board.add_object('text')
    result = board.bring_pupil_to_work_area(Rect(100, 40, 900, 700))
    assert result['ok'] is True
    assert result['unchanged'] is True
    assert result['show_checked'] is True
    assert board.show_pupil.isChecked()
    assert board.pupil.isVisible()
    assert board.pupil.windowTitle() == BOARD_PUPIL_TITLE
    assert board.session.pupil_view() == pinned
    assert board.session.teacher_view()['frozen'] is True
    board.resume()
    assert board.session.pupil_view()['document'] == board.session.teacher_view()['document']


def test_board_request_file_places_pupil_without_changing_a_frozen_page(board, tmp_path):
    import json
    from monitor_shortcut import BOARD_PRESENCE_NAME, BOARD_RECEIPT_NAME, BOARD_REQUEST_NAME

    settings_root = tmp_path / 'companion'
    board.watch_classroom_board_requests(settings_root)
    presence = json.loads((settings_root / BOARD_PRESENCE_NAME).read_text(encoding='utf-8'))
    assert presence['running'] is True
    assert presence['title'] == BOARD_PUPIL_TITLE
    board.freeze()
    pinned = board.session.pupil_view()
    (settings_root / BOARD_REQUEST_NAME).write_text(json.dumps({
        'id': 'req-1',
        'work_area': [100, 40, 900, 700],
    }), encoding='utf-8')
    board._poll_classroom_board_request()
    receipt = json.loads((settings_root / BOARD_RECEIPT_NAME).read_text(encoding='utf-8'))
    assert receipt['id'] == 'req-1'
    assert receipt['ok'] is True
    assert receipt['unchanged'] is True
    assert board.session.pupil_view() == pinned
    assert board.show_pupil.isChecked()
