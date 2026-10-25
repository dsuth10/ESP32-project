"""Local teacher/pupil authority, atomic presentation and explicit autosave boundary.

The UI schedules saves and passes captured tokens; this module owns no timer,
display, microphone or network. View/freeze/navigation state is session-local.
Only the lesson and its bounded edit history are persisted by BoardStore.
"""
from __future__ import annotations

import copy
import hashlib
import threading
import uuid

from board_model import BoardModel, BoardValidationError, BoardConflictError, new_object
from board_store import BoardStore

MAX_IMAGE_BYTES = 32 * 1024 * 1024


class BoardSessionError(RuntimeError):
    pass


class BoardAuthorityError(BoardSessionError):
    pass


class BoardSessionSaveError(BoardSessionError):
    pass


class BoardMediaError(BoardSessionError):
    pass


class BoardSession:
    def __init__(self, model=None, *, store=None, image_resolver=None):
        if model is not None and not isinstance(model, BoardModel):
            raise BoardValidationError('A board session requires a validated BoardModel.')
        if store is not None and not isinstance(store, BoardStore):
            raise BoardValidationError('A board session requires an isolated BoardStore.')
        if image_resolver is not None and not callable(image_resolver):
            raise BoardValidationError('The local image resolver must be callable.')
        # The caller cannot mutate the owned model behind the role/token boundary.
        self._model = BoardModel.from_state(model.export_state()) if model else BoardModel()
        self._store, self._image_resolver = store, image_resolver
        self._lock = threading.RLock()
        self._session_id, self._generation = str(uuid.uuid4()), 0
        self._closed = self._frozen = False
        self._teacher_page = self._model.snapshot()['pages'][0]['id']
        self._published = self._model.snapshot()
        self._pupil_page = self._teacher_page
        self._published_token = self._token()
        self._saved_revision = None
        self._save_error = None
        self._recovery_status = 'new'

    @classmethod
    def open(cls, store, *, image_resolver=None):
        if not isinstance(store, BoardStore):
            raise BoardValidationError('Open an isolated BoardStore.')
        model = store.load()
        session = cls(model, store=store, image_resolver=image_resolver)
        session._saved_revision = model.revision
        session._recovery_status = store.recovery_status
        return session

    def _token(self):
        return f'{self._session_id}:{self._generation}'

    def _ensure_open(self):
        if self._closed:
            raise BoardSessionError('This board session is closed.')

    def _expect(self, expected_token):
        self._ensure_open()
        if not isinstance(expected_token, str) or expected_token != self._token():
            raise BoardConflictError('The board view changed. Review this action against the current session.')

    @staticmethod
    def _find_page(document, page_id):
        for page in document['pages']:
            if page['id'] == page_id:
                return page
        raise BoardValidationError('Page was not found in this lesson.')

    def _publish(self):
        document = self._model.snapshot()
        if not any(page['id'] == self._teacher_page for page in document['pages']):
            self._teacher_page = document['pages'][0]['id']
        self._published = document
        self._pupil_page = self._teacher_page
        self._published_token = self._token()

    def _completed_edit(self):
        self._generation += 1
        document = self._model.snapshot()
        if not any(page['id'] == self._teacher_page for page in document['pages']):
            self._teacher_page = document['pages'][0]['id']
        if not self._frozen:
            self._publish()

    def teacher_view(self):
        with self._lock:
            self._ensure_open()
            document = self._model.snapshot()
            return {'document': document, 'page_id': self._teacher_page,
                    'revision': document['revision'], 'token': self._token(),
                    'frozen': self._frozen, 'read_only': False, 'role': 'teacher',
                    'can_edit_layout': True, 'can_annotate': True, 'can_navigate': True,
                    'dirty': document['revision'] != self._saved_revision,
                    'saved_revision': self._saved_revision, 'save_error': self._save_error,
                    'recovery_status': self._recovery_status}

    def pupil_view(self):
        with self._lock:
            self._ensure_open()
            return {'document': copy.deepcopy(self._published), 'page_id': self._pupil_page,
                    'revision': self._published['revision'], 'token': self._published_token,
                    'frozen': self._frozen, 'read_only': self._frozen, 'role': 'pupil',
                    'can_edit_layout': False, 'can_annotate': not self._frozen,
                    'can_navigate': not self._frozen}

    def teacher_apply(self, commands, *, expected_revision, expected_token, edit_group=None):
        with self._lock:
            self._expect(expected_token)
            self._model.apply(commands, expected_revision=expected_revision, edit_group=edit_group)
            self._completed_edit()
            return self.teacher_view()

    def teacher_undo(self, *, expected_revision, expected_token):
        with self._lock:
            self._expect(expected_token)
            self._model.undo(expected_revision=expected_revision)
            self._completed_edit()
            return self.teacher_view()

    def teacher_redo(self, *, expected_revision, expected_token):
        with self._lock:
            self._expect(expected_token)
            self._model.redo(expected_revision=expected_revision)
            self._completed_edit()
            return self.teacher_view()

    def teacher_navigate(self, page_id, *, expected_token):
        with self._lock:
            self._expect(expected_token)
            self._find_page(self._model.snapshot(), page_id)
            if page_id != self._teacher_page:
                self._model.end_edit_group()
                self._teacher_page = page_id
                self._generation += 1
                if not self._frozen:
                    self._publish()
            return self.teacher_view()

    def freeze(self, *, expected_token):
        with self._lock:
            self._expect(expected_token)
            if not self._frozen:
                self._model.end_edit_group()
                self._frozen = True
                self._generation += 1
                self._published_token = self._token()
            return self.pupil_view()

    def resume(self, *, expected_token):
        with self._lock:
            self._expect(expected_token)
            if self._frozen:
                self._model.end_edit_group()
                self._frozen = False
                self._generation += 1
                self._publish()
            return self.pupil_view()

    def _expect_pupil(self, expected_token):
        self._ensure_open()
        if self._frozen:
            raise BoardAuthorityError('The pupil display is frozen and read-only.')
        self._expect(expected_token)

    def pupil_navigate(self, page_id, *, expected_token):
        with self._lock:
            self._expect_pupil(expected_token)
            self._find_page(self._published, page_id)
            if page_id != self._pupil_page:
                self._model.end_edit_group()
                self._teacher_page = page_id
                self._generation += 1
                self._publish()
            return self.pupil_view()

    def pupil_add_ink(self, ink_object, *, expected_revision, expected_token):
        with self._lock:
            self._expect_pupil(expected_token)
            if (not isinstance(ink_object, dict) or ink_object.get('type') != 'ink'
                    or ink_object.get('locked') is not False):
                raise BoardAuthorityError('Pupil actions can add unlocked ink strokes only.')
            self._model.apply([{'op': 'add_object', 'page_id': self._pupil_page,
                                'object': ink_object}], expected_revision=expected_revision)
            self._completed_edit()
            return self.pupil_view()

    def pupil_erase_ink(self, object_id, *, expected_revision, expected_token):
        with self._lock:
            self._expect_pupil(expected_token)
            page = self._find_page(self._model.snapshot(), self._pupil_page)
            obj = next((obj for obj in page['objects'] if obj['id'] == object_id), None)
            if not obj or obj['type'] != 'ink' or obj['locked']:
                raise BoardAuthorityError('Pupil erasing can remove unlocked ink strokes only.')
            self._model.apply([{'op': 'remove_object', 'page_id': self._pupil_page,
                                'object_id': object_id}], expected_revision=expected_revision)
            self._completed_edit()
            return self.pupil_view()

    def save(self, *, expected_token):
        """Synchronous autosave boundary; token-bound UI timers must reschedule stale work.

        Return the actual durable revision. Failures raise and retain the dirty
        document plus a safe notice. Navigation/Freeze are intentionally unsaved.
        """
        with self._lock:
            self._expect(expected_token)
            if self._store is None:
                self._save_error = 'No local lesson store is configured.'
                raise BoardSessionSaveError(self._save_error)
            try:
                saved_revision = self._store.save(self._model)
            except Exception:
                self._save_error = 'Lesson save failed. Unsaved edits remain in this session; check storage and reopen/reconcile before retrying.'
                raise BoardSessionSaveError(self._save_error) from None
            self._saved_revision = saved_revision
            self._save_error = None
            return saved_revision

    def resolve_image(self, image_ref):
        """Return pinned local bytes only; the trusted resolver owns store lookup.

        The renderer must validate/decode supported image content before display.
        Missing media never creates a job or triggers retrieval/generation.
        """
        with self._lock:
            self._ensure_open()
            reference = new_object('image', image_ref=image_ref)['image_ref']
            resolver = self._image_resolver
        if resolver is None:
            raise BoardMediaError('This saved image is unavailable locally.')
        try:
            data = resolver(copy.deepcopy(reference))
        except Exception:
            raise BoardMediaError('This saved image could not be read locally.') from None
        if (not isinstance(data, bytes) or not 1 <= len(data) <= MAX_IMAGE_BYTES
                or hashlib.sha256(data).hexdigest() != reference['sha256']):
            raise BoardMediaError('This saved image is missing, damaged or exceeds the local size limit.')
        return data

    def close(self):
        """Invalidate delayed callbacks without writing; the UI must handle dirty close."""
        with self._lock:
            self._closed = True
            self._generation += 1
