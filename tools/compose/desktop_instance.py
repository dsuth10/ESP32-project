"""Prevent competing teacher windows from opening the same live stores."""
from audio_lease import ExclusiveFileLease
from pathlib import Path
import hashlib


class LessonInstances:
    def __init__(self):
        self._lessons = {}

    def claim_lesson(self, root):
        root = Path(root).resolve()
        if root in self._lessons:
            return
        identity = hashlib.sha256(str(root).casefold().encode('utf-8')).hexdigest()
        # Keep ownership outside the lesson itself: Save a copy/import require
        # their destination directory not to exist until atomic publication.
        lease = ExclusiveFileLease(root.parent / '.desktop-lesson-locks' / (identity + '.lock'))
        if not lease.acquire():
            raise ValueError('This lesson is already open in another teacher window. Return to that window first.')
        self._lessons[root] = lease

    def release(self):
        for lease in self._lessons.values():
            lease.release()
        self._lessons.clear()


class DesktopInstance:
    def __init__(self, board_root, companion_root):
        self.board_root = board_root
        self.lessons = LessonInstances()
        self.profile = ExclusiveFileLease(companion_root / '.unified-teacher.lock')

    def acquire(self):
        try:
            self.lessons.claim_lesson(self.board_root)
        except ValueError:
            return False
        if not self.profile.acquire():
            self.release()
            return False
        return True

    def claim_lesson(self, root):
        self.lessons.claim_lesson(root)

    def release(self):
        self.lessons.release()
        self.profile.release()
