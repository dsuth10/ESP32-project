"""Real Board/Qt integration with a synthetic child host; no providers or hardware."""
from pathlib import Path
import sys

import pytest
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget, QInputDialog

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_candidate import BoardCandidate, image_resolver
from board_model import BoardModel, new_lesson
from board_session import BoardSession, BoardSessionError
from board_store import BoardStore
from media_store import MediaStore
from desktop_instance import DesktopInstance, LessonInstances
from unified_desktop import UnifiedDesktop, validate_companion_root, CANDIDATE_ROOT


class SyntheticHost(QWidget):
    stateChanged = Signal(str)
    showRequested = Signal()
    closeRequested = Signal()
    closePrepared = Signal(bool, str)
    closeBlockedCode = Signal(str)
    closed = Signal()

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.prepares = []
        self.commits = 0
        self.cancels = 0
        self.peer_microphone = False

    def prepare_close(self, *, discard_queued_text=False):
        self.prepares.append(discard_queued_text)

    def commit_close(self):
        self.commits += 1

    def cancel_close(self):
        self.cancels += 1

    def set_peer_microphone(self, active):
        self.peer_microphone = active


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def desktop(app, tmp_path):
    root = tmp_path / 'lesson'
    media = MediaStore(root / 'media')
    store = BoardStore(root)
    resolver = image_resolver(media)
    session = BoardSession(BoardModel(), store=store, image_resolver=resolver)
    board = BoardCandidate(session, store=store, resolver=resolver)
    host = SyntheticHost()
    window = UnifiedDesktop(board, host)
    yield window
    window._microphone_timer.stop()
    if not board.session._closed:
        board.finish_close()
    window.hide(); board.pupil.hide(); window.deleteLater()
    app.processEvents()


def test_switching_workspaces_preserves_frozen_pupil_and_teacher_document(desktop, app):
    board = desktop.board
    board.freeze()
    published = board.session.pupil_view()
    board.add_object('text')
    edited = board.session.teacher_view()
    desktop.tabs.setCurrentWidget(desktop.companion)
    app.processEvents()
    assert board.session.pupil_view() == published
    assert board.session.teacher_view() == edited
    desktop.tabs.setCurrentWidget(board)
    app.processEvents()
    assert board.session.teacher_view() == edited
    assert board.session.pupil_view() == published
    assert board.pupil.isWindow()
    assert desktop.tabs.count() == 2
    assert desktop.tabs.indexOf(board.pupil) == -1


def test_board_save_veto_never_asks_companion_to_close(desktop, monkeypatch):
    monkeypatch.setattr(desktop.board, 'prepare_close', lambda **kwargs: False)
    desktop.close()
    assert desktop.companion.prepares == []
    assert desktop.companion.commits == 0
    assert not desktop._close_pending
    assert not desktop.board.session._closed


def test_board_save_and_close_button_uses_the_shared_close_handshake(desktop):
    desktop.board.file_buttons['Save and close'].click()
    assert desktop.companion.prepares == [False]
    assert desktop._close_pending
    assert not desktop.board.session._closed
    desktop.companion.closePrepared.emit(False, 'Keep working')
    assert desktop.board.isEnabled()


def test_embedded_window_close_request_uses_the_shared_close_handshake(desktop):
    desktop.companion.closeRequested.emit()
    assert desktop.companion.prepares == [False]
    assert desktop._close_pending
    assert not desktop.board.session._closed
    desktop.companion.closePrepared.emit(False, 'Keep working')
    assert desktop.board.isEnabled()


def test_board_microphone_work_blocks_shared_close_before_voice_preflight(desktop):
    # This sentinel only represents Board ownership; no audio stream is opened.
    desktop.board.agent_panel._audio = object()
    try:
        desktop.close()
        assert desktop.companion.prepares == []
        assert not desktop._close_pending
        assert not desktop.board.session._closed
        assert 'microphone' in desktop.board.error
    finally:
        desktop.board.agent_panel._audio = None


def test_companion_veto_preserves_board_session_and_reenables_editing(desktop):
    desktop.board.add_object('text')
    expected = desktop.board.session.teacher_view()['document']
    desktop.close()
    assert desktop._close_pending
    assert not desktop.board.isEnabled()
    desktop.companion.closePrepared.emit(False, 'Finish the recording first.')
    assert not desktop._close_pending
    assert desktop.board.isEnabled()
    assert desktop.companion.cancels == 1
    assert desktop.companion.commits == 0
    assert desktop.board.session.teacher_view()['document'] == expected
    desktop.board.add_object('rectangle')
    assert desktop.board.session.teacher_view()['document'] != expected


def test_pending_text_cancel_preserves_both_workspaces(desktop, monkeypatch):
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Cancel)
    desktop.close()
    desktop.companion.closeBlockedCode.emit('pending_text')
    assert not desktop._close_pending
    assert desktop.companion.prepares == [False]
    assert desktop.companion.commits == 0
    assert desktop.board.isEnabled()
    assert not desktop.board.session._closed


def test_pending_text_discard_reprepares_explicitly_before_committing(desktop, monkeypatch):
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Discard)
    desktop.close()
    desktop.companion.closeBlockedCode.emit('pending_text')
    assert desktop.companion.prepares == [False, True]
    assert desktop.companion.commits == 0
    desktop.companion.closePrepared.emit(True, 'Ready')
    assert desktop.companion.commits == 1
    assert not desktop.board.session._closed


def test_board_only_commits_close_when_companion_has_actually_exited(desktop):
    desktop.close()
    desktop.companion.closePrepared.emit(True, 'Ready')
    assert desktop.companion.commits == 1
    assert not desktop.board.session._closed
    desktop.companion.closed.emit()
    assert desktop._close_committed
    with pytest.raises(BoardSessionError):
        desktop.board.session.teacher_view()


def test_duplicate_closed_notifications_cannot_close_board_twice(desktop, monkeypatch):
    finishes = []
    original = desktop.board.finish_close
    def finish():
        finishes.append(True)
        original()
    monkeypatch.setattr(desktop.board, 'finish_close', finish)
    desktop.close()
    desktop.companion.closePrepared.emit(True, 'Ready')
    desktop.companion.closed.emit()
    desktop.companion.closed.emit()
    assert finishes == [True]


def test_companion_library_request_changes_teacher_workspace_only(desktop, monkeypatch):
    # Window activation belongs to the native smoke check; this test verifies
    # routing/privacy without taking desktop focus from another worker.
    for method in ('showNormal', 'raise_', 'activateWindow'):
        monkeypatch.setattr(desktop, method, lambda: None)
    before = desktop.board.session.pupil_view()
    desktop.companion.showRequested.emit()
    assert desktop.tabs.currentWidget() == desktop.companion
    assert desktop.board.session.pupil_view() == before


@pytest.mark.parametrize('relation', ['same', 'companion_inside_board', 'board_inside_companion'])
def test_companion_and_board_data_cannot_overlap(tmp_path, relation):
    base = tmp_path / 'profiles'
    if relation == 'same':
        companion, board = base, base
    elif relation == 'companion_inside_board':
        companion, board = base / 'voice', base
    else:
        companion, board = base, base / 'lesson'
    with pytest.raises(ValueError, match='separate'):
        validate_companion_root(companion, board)


def test_stable_companion_profile_cannot_be_selected(tmp_path):
    with pytest.raises(ValueError, match='stable'):
        validate_companion_root(tmp_path / 'ESP32ClassroomCompanion', tmp_path / 'lesson')


def test_second_teacher_cannot_open_same_lesson_with_another_companion_profile(tmp_path):
    first = DesktopInstance(tmp_path / 'lesson', tmp_path / 'voice-one')
    competing = DesktopInstance(tmp_path / 'lesson', tmp_path / 'voice-two')
    try:
        assert first.acquire()
        assert not competing.acquire()
    finally:
        first.release(); competing.release()


def test_second_teacher_cannot_open_same_companion_profile_with_another_lesson(tmp_path):
    first = DesktopInstance(tmp_path / 'lesson-one', tmp_path / 'voice')
    competing = DesktopInstance(tmp_path / 'lesson-two', tmp_path / 'voice')
    try:
        assert first.acquire()
        assert not competing.acquire()
    finally:
        first.release(); competing.release()


def test_failed_second_lock_releases_first_lock_for_other_teacher_window(tmp_path):
    first = DesktopInstance(tmp_path / 'lesson-one', tmp_path / 'voice-one')
    competing = DesktopInstance(tmp_path / 'lesson-two', tmp_path / 'voice-one')
    independent = DesktopInstance(tmp_path / 'lesson-two', tmp_path / 'voice-two')
    try:
        assert first.acquire()
        # This first locks lesson-two, then fails to lock voice-one.
        assert not competing.acquire()
        assert independent.acquire()
    finally:
        first.release(); competing.release(); independent.release()


def test_closed_teacher_window_releases_both_stores_for_reopening(tmp_path):
    first = DesktopInstance(tmp_path / 'lesson', tmp_path / 'voice')
    replacement = DesktopInstance(tmp_path / 'lesson', tmp_path / 'voice')
    try:
        assert first.acquire()
        first.release()
        assert replacement.acquire()
    finally:
        first.release(); replacement.release()


def test_distinct_teacher_stores_can_open_independently(tmp_path):
    first = DesktopInstance(tmp_path / 'lesson-one', tmp_path / 'voice-one')
    second = DesktopInstance(tmp_path / 'lesson-two', tmp_path / 'voice-two')
    try:
        assert first.acquire()
        assert second.acquire()
    finally:
        first.release(); second.release()


def test_claiming_new_lesson_does_not_create_its_atomic_copy_destination(tmp_path):
    destination = tmp_path / 'new-copy'
    instances = LessonInstances()
    try:
        instances.claim_lesson(destination)
        assert not destination.exists()
        assert (destination.parent / '.desktop-lesson-locks').is_dir()
    finally:
        instances.release()


def test_standalone_board_and_unified_teacher_cannot_own_the_same_lesson(tmp_path):
    root = tmp_path / 'lesson'
    standalone = LessonInstances()
    unified = DesktopInstance(root, tmp_path / 'voice')
    try:
        standalone.claim_lesson(root)
        assert not unified.acquire()
        standalone.release()
        assert unified.acquire()
        with pytest.raises(ValueError, match='already open'):
            standalone.claim_lesson(root)
    finally:
        standalone.release(); unified.release()


def test_saved_copy_remains_protected_alongside_original_until_teacher_closes(desktop):
    board = desktop.board
    original = board.store.root
    destination = original.parent / 'copied-lesson'
    instances = DesktopInstance(original, original.parent / 'voice')
    competing = LessonInstances()
    assert instances.acquire()
    board.claim_lesson = instances.claim_lesson
    try:
        board.add_object('text')
        assert board._save_copy(destination, 'Separate lesson copy')
        assert board.store.root == destination
        assert (destination / 'lesson.json').is_file()
        for root in (original, destination):
            with pytest.raises(ValueError, match='already open'):
                competing.claim_lesson(root)
        instances.release()
        competing.claim_lesson(destination)
    finally:
        instances.release(); competing.release()


def test_saved_lesson_picker_replaces_board_session_inside_same_teacher_window(desktop, monkeypatch):
    import board_lessons
    board, companion = desktop.board, desktop.companion
    old_session = board.session
    destination = board.store.root.parent / 'chosen-saved-lesson'
    BoardStore(destination).save(BoardModel(new_lesson('Chosen saved lesson')))
    record = {'title': 'Chosen saved lesson', 'key': '0123456789abcdef',
              'path': destination.relative_to(CANDIDATE_ROOT).as_posix()}
    monkeypatch.setattr(board_lessons, 'refresh_saved_lesson_access',
                        lambda *args: {'entries': [record]})
    monkeypatch.setattr(QInputDialog, 'getItem', lambda *args: ('Chosen saved lesson · 01234567', True))
    desktop.tabs.setCurrentWidget(companion)
    desktop.open_saved_lesson()
    assert desktop.board is board
    assert desktop.companion is companion
    assert desktop.tabs.count() == 2
    assert desktop.tabs.currentWidget() == board
    assert board.store.root == destination
    assert board.session.teacher_view()['document']['title'] == 'Chosen saved lesson'
    with pytest.raises(BoardSessionError):
        old_session.teacher_view()
    assert companion.prepares == [] and companion.commits == 0


def test_frozen_pupil_blocks_saved_lesson_switch_and_picker(desktop, monkeypatch):
    board = desktop.board
    board.freeze()
    before = board.session.pupil_view()
    def must_not_prompt(*args):
        raise AssertionError('Frozen pupils must be protected before choosing another lesson')
    monkeypatch.setattr(QInputDialog, 'getItem', must_not_prompt)
    desktop.open_saved_lesson()
    assert board.session.pupil_view() == before
    assert 'Resume' in board.error


def test_saved_lesson_switch_save_veto_preserves_session_and_target(desktop, monkeypatch):
    board = desktop.board
    original = board.session
    destination = board.store.root.parent / 'unavailable-target'
    monkeypatch.setattr(board, 'prepare_close', lambda **kwargs: False)
    assert not board.open_saved_lesson(destination)
    assert board.session is original
    assert not original._closed
    assert not destination.exists()


def test_missing_saved_lesson_never_creates_empty_lesson_or_replaces_session(desktop):
    board = desktop.board
    original = board.session
    destination = board.store.root.parent / 'missing-saved-lesson'
    assert not board.open_saved_lesson(destination)
    assert not destination.exists()
    assert board.session is original
    assert not original._closed
    assert 'No new lesson was created' in board.error
