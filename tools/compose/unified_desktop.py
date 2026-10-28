"""One teacher window, independent Teaching Board and Voice Companion workspaces.

Windows native Tk hosting preserves the existing companion. The pupil window
remains owned by the Board and is never a teacher-workspace tab.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QTabWidget, QInputDialog

from board_candidate import (BoardCandidate, BoardModel, BoardSession, BoardStore,
    MediaStore, SavedImageLibrary, CANDIDATE_ROOT, candidate_directory,
    validate_candidate_storage, image_resolver, demo_model, load_board_settings)
from companion_host import CompanionHost
from desktop_instance import DesktopInstance


def feature_data_root():
    configured = os.environ.get('ESP32_COMPANION_DATA_DIR')
    return Path(configured) if configured else Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'ESP32ClassroomCompanion-Feature'


def validate_companion_root(root, board_root):
    root = Path(root).expanduser().absolute()
    for entry in (root, *root.parents):
        if entry.is_symlink() or entry.is_junction():
            raise ValueError('Companion data must not redirect through links or junctions.')
        if entry.name.casefold() == 'esp32classroomcompanion':
            raise ValueError('Use an isolated feature companion profile; stable companion data is protected.')
    root, board_root = root.resolve(), Path(board_root).resolve()
    if root == board_root or root in board_root.parents or board_root in root.parents:
        raise ValueError('Choose separate Board lesson and companion data folders.')
    return root


class UnifiedDesktop(QMainWindow):
    def __init__(self, board, companion, *, parent=None):
        super().__init__(parent)
        self.board, self.companion = board, companion
        if board.agent_panel:
            board.agent_panel.companion_settings_root = Path(getattr(companion, 'data_root', feature_data_root()))
        self._close_pending = False
        self._close_committed = False
        self.tabs = QTabWidget()
        self.tabs.setAccessibleName('Teacher workspaces')
        self.tabs.addTab(board, 'Teaching Board')
        self.tabs.addTab(companion, 'Voice companion')
        self.setCentralWidget(self.tabs)
        self.setWindowTitle('Classroom Companion — teacher')
        self.resize(1320, 900)
        self.setMinimumSize(940, 720)
        self.statusBar().showMessage('Teaching Board ready · Voice companion starting')
        board.file_buttons['Save and close'].clicked.disconnect()
        board.file_buttons['Save and close'].clicked.connect(self.close)
        board.file_buttons['Open saved lessons'].clicked.disconnect()
        board.file_buttons['Open saved lessons'].clicked.connect(self.open_saved_lesson)
        files = self.menuBar().addMenu('File')
        files.addAction('Open saved lesson…', self.open_saved_lesson)
        files.addAction('Open saved lessons folder (recovery)', board.open_lesson_folder)
        files.addSeparator()
        files.addAction('Save and close application', self.close)
        companion.stateChanged.connect(self.statusBar().showMessage)
        companion.showRequested.connect(self.show_companion)
        companion.closeRequested.connect(self.close)
        companion.closePrepared.connect(self._companion_prepared)
        companion.closeBlockedCode.connect(self._close_blocked_code)
        companion.closed.connect(self._companion_closed)
        self._microphone_timer = QTimer(self)
        self._microphone_timer.timeout.connect(self._update_microphone_state)
        self._microphone_timer.start(150)

    def show_companion(self):
        if self._close_pending:
            return
        self.tabs.setCurrentWidget(self.companion)
        self.showNormal(); self.raise_(); self.activateWindow()

    def open_saved_lesson(self):
        if self._close_pending:
            return
        if self.board.session.teacher_view()['frozen']:
            self.board.error = 'Resume the pupil display before opening a different lesson. Your frozen view is unchanged.'
            self.board.refresh()
            self.tabs.setCurrentWidget(self.board)
            return
        from board_lessons import refresh_saved_lesson_access
        try:
            catalogue = refresh_saved_lesson_access((self.board.store.root,))
            entries = catalogue['entries']
            if not entries:
                self.statusBar().showMessage('No saved lessons are available yet. Save or copy your current lesson first.')
                return
            labels = [record['title'] + ' · ' + record['key'][:8] for record in entries]
            choice, accepted = QInputDialog.getItem(self, 'Open saved lesson',
                'Choose a saved lesson to open in this teacher window:', labels, 0, False)
            if not accepted:
                return
            entry = entries[labels.index(choice)]
            if self.board.open_saved_lesson(CANDIDATE_ROOT / entry['path']):
                self.tabs.setCurrentWidget(self.board)
                self.statusBar().showMessage('Saved lesson opened · Voice companion remains available.')
        except Exception as error:
            self.statusBar().showMessage('Saved lesson could not open: ' + str(error)[:300])

    def _update_microphone_state(self):
        panel = self.board.agent_panel
        self.companion.set_peer_microphone(bool(panel and panel._audio))

    def _cancel_close(self, reason='Application remains open.'):
        self._close_pending = False
        self.board.setEnabled(True)
        self.companion.cancel_close()
        self.statusBar().showMessage(reason)

    def _close_blocked_code(self, code):
        if self._close_pending and code == 'pending_text':
            choice = QMessageBox.question(self, 'Text waiting to paste',
                'The voice companion has text waiting for Paste Ready. Close and discard that queued text?',
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel)
            if choice == QMessageBox.StandardButton.Discard:
                self.companion.prepare_close(discard_queued_text=True)
            else:
                self._cancel_close('Paste or retain your queued text before closing.')

    def _companion_prepared(self, accepted, reason):
        if not self._close_pending:
            return
        # pending_text has a separate Discard/Cancel flow; preserve the close
        # preflight while its explicit decision is outstanding.
        if not accepted:
            self._cancel_close(reason)
            return
        self.statusBar().showMessage('Closing the voice companion safely…')
        self.companion.commit_close()

    def _companion_closed(self):
        if not self._close_pending or self._close_committed:
            return
        self._close_committed = True
        self.board.finish_close()
        self._microphone_timer.stop()
        self.close()

    def closeEvent(self, event):
        if self._close_committed:
            event.accept(); return
        event.ignore()
        if self._close_pending:
            return
        if not self.board.prepare_close(wait_for_work=True):
            self.tabs.setCurrentWidget(self.board)
            self.statusBar().showMessage('The Teaching Board needs attention before closing.')
            return
        self._close_pending = True
        self.board.setEnabled(False)
        if not self.companion.is_running:
            self._companion_closed()
        else:
            self.statusBar().showMessage('Checking whether both workspaces can close…')
            self.companion.prepare_close()


def create_board(data_root, *, demo=False, settings_root=None, library_root=None, settings_selection_path=None):
    validate_candidate_storage(data_root)
    existing = any((data_root / name).exists() for name in ('lesson.json', 'lesson.previous.json'))
    if existing and demo:
        raise ValueError('Demo requires a fresh candidate folder; the existing lesson was preserved.')
    store = BoardStore(data_root)
    media = MediaStore(data_root / 'media')
    resolver = image_resolver(media)
    session = (BoardSession.open(store, image_resolver=resolver) if existing else
               BoardSession(demo_model(media) if demo else BoardModel(), store=store, image_resolver=resolver))
    config = load_board_settings(settings_root) if settings_root else None
    source = SavedImageLibrary(library_root).root if library_root else None
    board = BoardCandidate(session, store=store, resolver=resolver, agent_config=config, library_root=source,
                           agent_settings_root=settings_root, settings_selection_path=settings_selection_path)
    if source and board.agent_panel:
        board.agent_panel.pending_sources.append(source)
        board.agent_panel.index_timer.start(0)
    return board


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=candidate_directory, default=CANDIDATE_ROOT / 'review')
    parser.add_argument('--companion-data-root', type=Path, default=feature_data_root())
    parser.add_argument('--companion-python', type=Path, default=Path(sys.executable))
    parser.add_argument('--board-settings-root', type=Path)
    parser.add_argument('--library-root', type=Path)
    parser.add_argument('--demo', action='store_true')
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName('Classroom Companion')
    instance = None
    try:
        validate_candidate_storage(args.data_root)
        profile = validate_companion_root(args.companion_data_root, args.data_root)
        instance = DesktopInstance(args.data_root, profile)
        if not instance.acquire():
            raise ValueError('This lesson or companion profile is already open in another teacher window. Return to that window first.')
        os.environ['ESP32_COMPANION_MICROPHONE_LEASE'] = str(profile / 'unified-microphone.lock')
        board = create_board(args.data_root, demo=args.demo, settings_root=args.board_settings_root,
                             library_root=args.library_root, settings_selection_path=profile / 'board-settings-selection.json')
        board.claim_lesson = instance.claim_lesson
        companion = CompanionHost(profile, python_executable=args.companion_python)
        window = UnifiedDesktop(board, companion)
        window.show(); board.pupil.show()
        companion.start()
        if board.session.teacher_view()['dirty']:
            board.save_timer.start(300)
        return app.exec()
    except Exception as error:
        QMessageBox.critical(None, 'Classroom Companion could not open',
                             str(error) + '\nExisting lessons and companion data were preserved.')
        return 1
    finally:
        if instance:
            instance.release()


if __name__ == '__main__':
    sys.exit(main())
