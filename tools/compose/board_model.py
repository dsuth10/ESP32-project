"""Renderer-independent local Teaching Board documents and atomic edit history.

Coordinates are logical canvas units, not physical measurements. Images refer to
immutable application-owned versions; this module resolves no paths or networks.
"""
from __future__ import annotations

import copy
import json
import math
import re
import threading
import uuid

SCHEMA = 1
MAX_DOCUMENT_BYTES = 4 * 1024 * 1024
MAX_STATE_BYTES = 16 * 1024 * 1024
MAX_HISTORY = 20
MAX_REVISION = 2**53 - 1
_COLOUR = re.compile(r'^#[0-9a-fA-F]{6}$')
_HASH = re.compile(r'^[0-9a-f]{64}$')
_COMMON = {'id', 'type', 'x', 'y', 'width', 'height', 'rotation', 'locked'}
_TYPED = {
    'text': {'text', 'font_size', 'colour', 'align'},
    'image': {'image_ref'},
    'shape': {'shape', 'fill', 'stroke', 'stroke_width'},
    'arrow': {'start', 'end', 'colour', 'stroke_width'},
    'ink': {'points', 'colour', 'stroke_width'},
}


class BoardValidationError(ValueError):
    pass


class BoardConflictError(BoardValidationError):
    pass


def canonical_json(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                          allow_nan=False).encode('utf-8')
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise BoardValidationError('Board data must be finite, valid UTF-8 JSON.') from None


def _keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise BoardValidationError(f'{label} has missing or unsupported fields.')


def _text(value, maximum, label, *, empty=True):
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()):
        raise BoardValidationError(f'{label} must be text within {maximum} characters.')
    try:
        value.encode('utf-8')
    except UnicodeError:
        raise BoardValidationError(f'{label} must be valid UTF-8 text.') from None


def _id(value):
    if not isinstance(value, str):
        raise BoardValidationError('Board identities must be canonical UUID strings.')
    try:
        valid = str(uuid.UUID(value)) == value
    except ValueError:
        valid = False
    if not valid:
        raise BoardValidationError('Board identities must be canonical UUID strings.')


def _number(value, low, high, label):
    if type(value) not in (int, float) or not low <= value <= high or not math.isfinite(value):
        raise BoardValidationError(f'{label} must be a finite number from {low} to {high}.')


def _revision(value):
    if type(value) is not int or not 0 <= value <= MAX_REVISION:
        raise BoardValidationError('Revision must be a non-negative safe integer.')


def _colour(value):
    if not isinstance(value, str) or not _COLOUR.fullmatch(value):
        raise BoardValidationError('Colours must use #RRGGBB.')


def _point(value, width, height):
    if not isinstance(value, list) or len(value) != 2:
        raise BoardValidationError('A point must contain two local coordinates.')
    _number(value[0], 0, width, 'Point x')
    _number(value[1], 0, height, 'Point y')


def validate_object(obj):
    if not isinstance(obj, dict) or not isinstance(obj.get('type'), str) or obj['type'] not in _TYPED:
        raise BoardValidationError('Unsupported board object type.')
    kind = obj['type']
    _keys(obj, _COMMON | _TYPED[kind], 'Board object')
    _id(obj['id'])
    for name in ('x', 'y'):
        _number(obj[name], -100000, 100000, name)
    for name in ('width', 'height'):
        _number(obj[name], 0.1, 100000, name)
    _number(obj['rotation'], -360, 360, 'Rotation')
    if type(obj['locked']) is not bool:
        raise BoardValidationError('Object locked must be boolean.')
    if kind == 'text':
        _text(obj['text'], 20000, 'Object text')
        _number(obj['font_size'], 1, 1000, 'Font size')
        _colour(obj['colour'])
        if obj['align'] not in ('left', 'centre', 'right'):
            raise BoardValidationError('Unsupported text alignment.')
    elif kind == 'image':
        ref = obj['image_ref']
        _keys(ref, {'asset_id', 'version_id', 'sha256'}, 'Image reference')
        _id(ref['asset_id']); _id(ref['version_id'])
        if not isinstance(ref['sha256'], str) or not _HASH.fullmatch(ref['sha256']):
            raise BoardValidationError('An image reference needs a SHA-256 digest.')
    elif kind == 'shape':
        if obj['shape'] not in ('rectangle', 'ellipse'):
            raise BoardValidationError('Unsupported shape.')
        _colour(obj['fill']); _colour(obj['stroke'])
        _number(obj['stroke_width'], 0.1, 100, 'Stroke width')
    else:
        _colour(obj['colour'])
        _number(obj['stroke_width'], 0.1, 100, 'Stroke width')
        if kind == 'arrow':
            _point(obj['start'], obj['width'], obj['height'])
            _point(obj['end'], obj['width'], obj['height'])
        else:
            if not isinstance(obj['points'], list) or not 1 <= len(obj['points']) <= 10000:
                raise BoardValidationError('An ink stroke needs 1–10000 points.')
            for point in obj['points']:
                _point(point, obj['width'], obj['height'])
    return obj


def _validate_page(page):
    _keys(page, {'id', 'title', 'width', 'height', 'objects'}, 'Page')
    _id(page['id']); _text(page['title'], 200, 'Page title')
    _number(page['width'], 100, 16000, 'Page width')
    _number(page['height'], 100, 16000, 'Page height')
    if not isinstance(page['objects'], list) or len(page['objects']) > 500:
        raise BoardValidationError('A page supports at most 500 objects.')
    for obj in page['objects']:
        validate_object(obj)


def validate_document(document):
    _keys(document, {'schema', 'lesson_id', 'title', 'revision', 'pages'}, 'Lesson')
    if type(document['schema']) is not int or document['schema'] != SCHEMA:
        raise BoardValidationError('Unsupported board document schema.')
    _id(document['lesson_id']); _text(document['title'], 200, 'Lesson title', empty=False)
    _revision(document['revision'])
    pages = document['pages']
    if not isinstance(pages, list) or not 1 <= len(pages) <= 64:
        raise BoardValidationError('A lesson needs 1–64 pages.')
    identities = {document['lesson_id']}
    objects, points = 0, 0
    for page in pages:
        _validate_page(page)
        for item in [page, *page['objects']]:
            if item['id'] in identities:
                raise BoardValidationError('Page and object identities must be unique within a lesson.')
            identities.add(item['id'])
        objects += len(page['objects'])
        points += sum(len(obj['points']) for obj in page['objects'] if obj['type'] == 'ink')
    if objects > 5000 or points > 100000:
        raise BoardValidationError('Lesson object or ink-point limit exceeded.')
    if len(canonical_json(document)) > MAX_DOCUMENT_BYTES:
        raise BoardValidationError('Lesson exceeds the 4 MiB document limit.')
    return document


def new_object(kind, **fields):
    obj = {'id': str(uuid.uuid4()), 'type': kind, 'x': 0, 'y': 0, 'width': 100,
           'height': 100, 'rotation': 0, 'locked': False}
    defaults = {
        'text': {'text': '', 'font_size': 32, 'colour': '#1F2937', 'align': 'left'},
        'image': {},
        'shape': {'shape': 'rectangle', 'fill': '#FFFFFF', 'stroke': '#1F2937', 'stroke_width': 2},
        'arrow': {'start': [0, 50], 'end': [100, 50], 'colour': '#1F2937', 'stroke_width': 3},
        'ink': {'points': [[0, 0]], 'colour': '#1F2937', 'stroke_width': 3},
    }
    if not isinstance(kind, str) or kind not in defaults:
        raise BoardValidationError('Unsupported board object type.')
    obj.update(defaults[kind]); obj.update(fields)
    validate_object(obj)
    return copy.deepcopy(obj)


def new_page(title='', *, width=1600, height=900, page_id=None):
    page = {'id': page_id or str(uuid.uuid4()), 'title': title, 'width': width,
            'height': height, 'objects': []}
    _validate_page(page)
    return page


def new_lesson(title='Untitled lesson'):
    return {'schema': SCHEMA, 'lesson_id': str(uuid.uuid4()), 'title': title,
            'revision': 0, 'pages': [new_page('Page 1')]}


class BoardModel:
    """Each valid batch/undo/redo advances revision; failed edits leave all state intact."""
    def __init__(self, document=None):
        document = new_lesson() if document is None else document
        validate_document(document)
        self._document = copy.deepcopy(document)
        self._undo, self._redo = [], []
        # A live property editor may coalesce only consecutive edits to the same
        # object. This transient identity is deliberately absent from checkpoints.
        self._edit_group = None
        self._lock = threading.RLock()

    @property
    def revision(self):
        with self._lock:
            return self._document['revision']

    def snapshot(self):
        with self._lock:
            return copy.deepcopy(self._document)

    def _expect(self, expected_revision):
        _revision(expected_revision)
        if expected_revision != self._document['revision']:
            raise BoardConflictError('Lesson changed; review this edit against the current revision.')
        if expected_revision == MAX_REVISION:
            raise BoardValidationError('Lesson revision limit reached.')

    @staticmethod
    def _page(document, page_id):
        _id(page_id)
        for page in document['pages']:
            if page['id'] == page_id:
                return page
        raise BoardValidationError('Page was not found.')

    @staticmethod
    def _object(page, object_id):
        _id(object_id)
        for obj in page['objects']:
            if obj['id'] == object_id:
                return obj
        raise BoardValidationError('Object was not found.')

    @staticmethod
    def _index(value, length):
        if type(value) is not int or not 0 <= value <= length:
            raise BoardValidationError('Object/page position is out of range.')
        return value

    def _command(self, document, command):
        if not isinstance(command, dict) or not isinstance(command.get('op'), str):
            raise BoardValidationError('An edit must be a typed command.')
        op = command['op']
        fields = {
            'rename_lesson': {'title'}, 'add_page': {'page', 'index'},
            'remove_page': {'page_id'}, 'update_page': {'page_id', 'changes'},
            'add_object': {'page_id', 'object', 'index'},
            'remove_object': {'page_id', 'object_id'},
            'update_object': {'page_id', 'object_id', 'changes'},
            'reorder_object': {'page_id', 'object_id', 'index'},
        }
        if op not in fields:
            raise BoardValidationError('Unsupported board command.')
        allowed = fields[op] | {'op'}
        required = allowed - ({'index'} if op in {'add_page', 'add_object'} else set())
        if set(command) - allowed or required - set(command):
            raise BoardValidationError('Command has missing or unsupported fields.')
        if op == 'rename_lesson':
            _text(command['title'], 200, 'Lesson title', empty=False)
            document['title'] = command['title']
            return
        if op == 'add_page':
            _validate_page(command['page'])
            position = self._index(command.get('index', len(document['pages'])), len(document['pages']))
            document['pages'].insert(position, copy.deepcopy(command['page']))
            return
        page = self._page(document, command['page_id'])
        if op == 'remove_page':
            document['pages'].remove(page)
        elif op == 'update_page':
            changes = command['changes']
            if not isinstance(changes, dict) or not changes or set(changes) - {'title', 'width', 'height'}:
                raise BoardValidationError('Page changes support title, width and height only.')
            candidate = {**page, **changes}
            _validate_page(candidate)
            page.update(copy.deepcopy(changes))
        elif op == 'add_object':
            validate_object(command['object'])
            position = self._index(command.get('index', len(page['objects'])), len(page['objects']))
            page['objects'].insert(position, copy.deepcopy(command['object']))
        else:
            obj = self._object(page, command['object_id'])
            if op == 'remove_object':
                page['objects'].remove(obj)
            elif op == 'reorder_object':
                position = self._index(command['index'], len(page['objects']) - 1)
                page['objects'].remove(obj)
                page['objects'].insert(position, obj)
            else:
                changes = command['changes']
                if (not isinstance(changes, dict) or not changes
                        or set(changes) & {'id', 'type', 'image_ref'}):
                    raise BoardValidationError('Object identity, type and image reference are immutable.')
                candidate = {**obj, **changes}
                validate_object(candidate)
                obj.update(copy.deepcopy(changes))

    def _trim_history(self):
        self._undo = self._undo[-MAX_HISTORY:]
        self._redo = self._redo[-MAX_HISTORY:]
        while len(canonical_json(self._state_unlocked())) > MAX_STATE_BYTES:
            if self._undo:
                self._undo.pop(0)
            elif self._redo:
                self._redo.pop(0)
            else:
                raise BoardValidationError('Lesson state exceeds the storage limit.')

    def apply(self, commands, *, expected_revision, edit_group=None):
        with self._lock:
            self._expect(expected_revision)
            if edit_group is not None:
                _id(edit_group)
            if not isinstance(commands, list) or not 1 <= len(commands) <= 100:
                raise BoardValidationError('An edit batch needs 1–100 commands.')
            if len(canonical_json(commands)) > MAX_DOCUMENT_BYTES:
                raise BoardValidationError('Edit batch exceeds the 4 MiB limit.')
            candidate = copy.deepcopy(self._document)
            for command in commands:
                self._command(candidate, command)
            candidate['revision'] = self.revision + 1
            validate_document(candidate)
            group = None
            if edit_group is not None:
                if len(commands) != 1 or commands[0]['op'] != 'update_object':
                    raise BoardValidationError('Live edit groups support one object update only.')
                group = (edit_group, commands[0]['page_id'], commands[0]['object_id'])
            if group is None or group != self._edit_group or not self._undo:
                self._undo.append(self._document)
            self._document, self._redo = candidate, []
            self._edit_group = group
            self._trim_history()
            return self.snapshot()

    def end_edit_group(self):
        """Keep the saved edit history while ending a transient typing burst."""
        with self._lock:
            self._edit_group = None

    def _travel(self, source, destination, expected_revision):
        self._expect(expected_revision)
        if not source:
            raise BoardValidationError('There is no edit to undo or redo.')
        candidate = copy.deepcopy(source[-1])
        candidate['revision'] = self.revision + 1
        validate_document(candidate)
        destination.append(self._document)
        source.pop()
        self._document = candidate
        self._edit_group = None
        self._trim_history()
        return self.snapshot()

    def undo(self, *, expected_revision):
        with self._lock:
            return self._travel(self._undo, self._redo, expected_revision)

    def redo(self, *, expected_revision):
        with self._lock:
            return self._travel(self._redo, self._undo, expected_revision)

    def _state_unlocked(self):
        return {'schema': SCHEMA, 'document': self._document, 'undo': self._undo, 'redo': self._redo}

    def export_state(self):
        with self._lock:
            return copy.deepcopy(self._state_unlocked())

    @classmethod
    def from_state(cls, state):
        _keys(state, {'schema', 'document', 'undo', 'redo'}, 'Board session')
        if type(state['schema']) is not int or state['schema'] != SCHEMA:
            raise BoardValidationError('Unsupported board session schema.')
        validate_document(state['document'])
        for history in (state['undo'], state['redo']):
            if not isinstance(history, list) or len(history) > MAX_HISTORY:
                raise BoardValidationError('Invalid board undo/redo history.')
            for document in history:
                validate_document(document)
                if (document['lesson_id'] != state['document']['lesson_id']
                        or document['revision'] >= state['document']['revision']):
                    raise BoardValidationError('History does not belong to this lesson revision.')
        if len(canonical_json(state)) > MAX_STATE_BYTES:
            raise BoardValidationError('Board session exceeds the 16 MiB state limit.')
        model = cls(state['document'])
        model._undo, model._redo = copy.deepcopy(state['undo']), copy.deepcopy(state['redo'])
        return model
