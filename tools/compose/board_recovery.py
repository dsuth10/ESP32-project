"""Private, durable Board request links and observation-only Hermes recovery.

This journal is outside the portable lesson state. Recovery reads/polls the
original saved Hermes identity; it never prepares, submits or retries a task.
The publication barrier is independent of remote status, including after a crash.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import uuid
import weakref

from board_model import BoardModel, canonical_json, MAX_DOCUMENT_BYTES


MAX_RECORD_BYTES = MAX_DOCUMENT_BYTES + 128 * 1024
MAX_CONTEXT_BYTES = 48 * 1024
MAX_RESULT_BYTES = 20000
_ID = re.compile(r'^[A-Za-z0-9_-]{1,160}$')
_SUCCESS = {'completed', 'succeeded', 'success', 'finished', 'done'}
_TERMINAL = _SUCCESS | {'failed', 'cancelled', 'canceled', 'interrupted'}
_PUBLICATION = {'pending', 'review', 'applying', 'applied', 'cancelled', 'stale', 'failed'}
_FIELDS = {'schema', 'request_id', 'prepared', 'baseline', 'hermes_request_id',
           'status', 'message', 'result', 'run_id', 'publication_status',
           'created_utc', 'updated_utc'}
_ROOT_LOCKS = weakref.WeakValueDictionary()
_ROOT_LOCKS_GUARD = threading.Lock()


class BoardRecoveryError(ValueError):
    """A bounded, safe-to-display recovery error."""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BoardRecoveryError('Saved Board recovery data contains duplicate fields.')
        result[key] = value
    return result


def _decode(data):
    try:
        return json.loads(data, object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise BoardRecoveryError('Saved Board recovery data is invalid or damaged.') from None


def _identity(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise BoardRecoveryError('Invalid saved Board request identity.')
    return value


def _text(value, maximum, label):
    if not isinstance(value, str) or len(value.encode('utf-8')) > maximum:
        raise BoardRecoveryError(label + ' exceeds its supported text limit.')
    return value


def _no_links(path):
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise BoardRecoveryError('Board recovery paths must not use links or junctions.')


def _prepared(value):
    if not isinstance(value, dict) or set(value) != {'request_id', 'task', 'context', 'context_sha256', 'effective_context'}:
        raise BoardRecoveryError('A complete immutable Board request is required for recovery.')
    _identity(value['request_id'])
    _text(value['task'], 12000, 'Board task')
    raw = _text(value['context'], MAX_CONTEXT_BYTES, 'Board context').encode('utf-8')
    context = _decode(raw)
    if (not isinstance(context, dict) or context.get('request_id') != value['request_id']
            or hashlib.sha256(raw).hexdigest() != value['context_sha256']
            or context.get('effective_context') != value['effective_context']):
        raise BoardRecoveryError('Saved Board context does not match its immutable request.')
    return context


def _validate(record):
    if not isinstance(record, dict) or set(record) != _FIELDS or type(record['schema']) is not int or record['schema'] != 1:
        raise BoardRecoveryError('Unsupported saved Board recovery record.')
    context = _prepared(record['prepared'])
    if record['request_id'] != record['prepared']['request_id']:
        raise BoardRecoveryError('Saved Board request identities do not match.')
    baseline = record['baseline']
    if not isinstance(baseline, dict) or set(baseline) != {'document', 'page_id', 'revision'}:
        raise BoardRecoveryError('A complete original lesson snapshot is required for recovery.')
    try:
        BoardModel(baseline['document'])
        pages = baseline['document']['pages']
        if (baseline['document']['lesson_id'] != context['lesson_id']
                or baseline['document']['revision'] != baseline['revision']
                or baseline['revision'] != context['revision']
                or baseline['page_id'] != context['page']['id']
                or not any(page['id'] == baseline['page_id'] for page in pages)):
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise BoardRecoveryError('Saved Board baseline does not match its request.') from None
    for field in ('hermes_request_id', 'run_id'):
        if record[field] is not None:
            _identity(record[field])
    for field, maximum in (('status', 80), ('message', 1000), ('created_utc', 80), ('updated_utc', 80)):
        _text(record[field], maximum, 'Recovery ' + field)
    if record['publication_status'] not in _PUBLICATION:
        raise BoardRecoveryError('Unsupported Board publication state.')
    if record['result'] is not None:
        _text(record['result'], MAX_RESULT_BYTES, 'Recovered result')
        if not isinstance(_decode(record['result']), dict):
            raise BoardRecoveryError('Recovered Board output must be one JSON object.')
    return record


class BoardRecoveryStore:
    def __init__(self, root):
        self.root = Path(root).expanduser().absolute()
        _no_links(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        # Reopening a lesson can overlap its former worker in this process.
        # Share the process lock across store instances before taking the OS
        # lock, which still rejects an independent process without blocking it.
        key = os.path.normcase(str(self.root.resolve()))
        with _ROOT_LOCKS_GUARD:
            self._lock = _ROOT_LOCKS.get(key)
            if self._lock is None:
                self._lock = threading.RLock()
                _ROOT_LOCKS[key] = self._lock

    @contextmanager
    def _exclusive(self):
        with self._lock:
            _no_links(self.root)
            path = self.root / '.recovery.lock'
            _no_links(path)
            with path.open('a+b') as stream:
                stream.seek(0, os.SEEK_END)
                if not stream.tell():
                    stream.write(b'0'); stream.flush()
                stream.seek(0)
                try:
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    raise BoardRecoveryError('Board recovery is busy in another window. Try again shortly.') from None
                try:
                    yield
                finally:
                    stream.seek(0)
                    if os.name == 'nt':
                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _path(self, request_id):
        path = self.root / (_identity(request_id) + '.json')
        _no_links(path)
        return path

    def _read(self, request_id):
        path = self._path(request_id)
        try:
            with path.open('rb') as stream:
                raw = stream.read(MAX_RECORD_BYTES + 1)
        except FileNotFoundError:
            raise
        except OSError:
            raise BoardRecoveryError('The saved Board request could not be read.') from None
        if len(raw) > MAX_RECORD_BYTES:
            raise BoardRecoveryError('The saved Board request exceeds its size limit.')
        envelope = _decode(raw)
        if (not isinstance(envelope, dict) or set(envelope) != {'record', 'sha256'}
                or hashlib.sha256(canonical_json(envelope['record'])).hexdigest() != envelope['sha256']):
            raise BoardRecoveryError('The saved Board request checksum does not match.')
        record = _validate(envelope['record'])
        if record['request_id'] != request_id:
            raise BoardRecoveryError('The saved Board request file has the wrong identity.')
        return record

    def _write(self, record):
        _validate(record)
        raw = canonical_json({'record': record, 'sha256': hashlib.sha256(canonical_json(record)).hexdigest()})
        if len(raw) > MAX_RECORD_BYTES:
            raise BoardRecoveryError('The saved Board request exceeds its size limit.')
        path = self._path(record['request_id'])
        temporary = self.root / ('.writing-' + uuid.uuid4().hex)
        try:
            with temporary.open('xb') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return copy.deepcopy(record)

    def create(self, prepared, baseline):
        context = _prepared(prepared)
        now = _now()
        record = dict(schema=1, request_id=context['request_id'], prepared=copy.deepcopy(prepared),
                      baseline=copy.deepcopy(baseline), hermes_request_id=None, status='prepared',
                      message='Saved locally before composition.', result=None, run_id=None,
                      publication_status='pending', created_utc=now, updated_utc=now)
        with self._exclusive():
            if self._path(record['request_id']).exists():
                existing = self._read(record['request_id'])
                if existing['prepared'] != prepared or existing['baseline'] != baseline:
                    raise BoardRecoveryError('This Board identity already belongs to another immutable request.')
                return copy.deepcopy(existing)
            return self._write(record)

    def get(self, request_id):
        with self._exclusive():
            return copy.deepcopy(self._read(request_id))

    def list_requests(self):
        result = []
        with self._exclusive():
            for path in self.root.glob('*.json'):
                if not _ID.fullmatch(path.stem):
                    continue
                try:
                    result.append(self._read(path.stem))
                except (BoardRecoveryError, OSError, ValueError):
                    result.append(dict(request_id=path.stem, status='needs_attention',
                        message='Saved Board recovery data needs attention; it has not been replayed.',
                        invalid=True, prepared=None, baseline=None, publication_status='blocked',
                        hermes_request_id=None, run_id=None, result=None, created_utc='', updated_utc=''))
        return sorted(result, key=lambda item: item['created_utc'], reverse=True)

    def bind(self, request_id, hermes_request_id):
        _identity(hermes_request_id)
        with self._exclusive():
            record = self._read(request_id)
            if record['hermes_request_id'] not in (None, hermes_request_id):
                raise BoardRecoveryError('The Board request is already linked to another Hermes task.')
            record.update(hermes_request_id=hermes_request_id, updated_utc=_now())
            return self._write(record)

    def update(self, request_id, **fields):
        if not set(fields) <= {'status', 'message', 'result', 'run_id', 'publication_status'}:
            raise BoardRecoveryError('Immutable Board recovery fields cannot be changed.')
        with self._exclusive():
            record = self._read(request_id)
            publication = fields.get('publication_status', record['publication_status'])
            if record['publication_status'] in {'applied', 'cancelled', 'stale', 'failed'} and publication != record['publication_status']:
                fields.pop('publication_status', None)
            elif record['publication_status'] == 'applying' and publication not in {'applying', 'applied'}:
                fields.pop('publication_status', None)
            if record['result'] is not None and fields.get('result', record['result']) != record['result']:
                raise BoardRecoveryError('A saved Board result cannot be replaced or cleared.')
            if record['run_id'] is not None and fields.get('run_id', record['run_id']) != record['run_id']:
                raise BoardRecoveryError('The saved Hermes run identity cannot be replaced.')
            record.update(copy.deepcopy(fields), updated_utc=_now())
            return self._write(record)

    def claim_publication(self, request_id):
        """Claim this result exactly once, before touching the live lesson.

        The claim is intentionally not rolled back after failure: an interruption
        between publication and its receipt must remain a manual-review case.
        """
        with self._exclusive():
            record = self._read(request_id)
            if record['publication_status'] not in {'pending', 'review'}:
                raise BoardRecoveryError('This Board result is already claimed or cannot be published. Review its saved outcome.')
            record.update(publication_status='applying', updated_utc=_now())
            return self._write(record)

    @staticmethod
    def _local_only(service, local_only):
        value = getattr(service, 'config', {}).get('LOCAL_ONLY', False)
        return local_only or value is True or str(value).casefold() in {'1', 'true', 'yes', 'on'}

    def _selection(self, record, service):
        identity = record['hermes_request_id']
        if identity is None:
            raise BoardRecoveryError('This request has no saved Hermes link. It will not be submitted again.')
        preview = service.preview(identity)
        if (preview.get('request_id') != identity or preview.get('task') != record['prepared']['task'].strip()
                or preview.get('context') != record['prepared']['context'].strip()):
            raise BoardRecoveryError('The saved Hermes selection does not match this Board request.')
        return preview

    def refresh(self, request_id, service, *, local_only=False):
        record = self.get(request_id)
        if self._local_only(service, local_only):
            return self.update(request_id, status='local_only', message='Remote status checks are disabled in local-only mode.')
        try:
            preview = self._selection(record, service)
            if preview.get('status') not in _TERMINAL and preview.get('receipt_exists'):
                service.poll(record['hermes_request_id'])
                preview = self._selection(record, service)
            status = str(preview.get('status', 'unknown')).casefold()
            fields = {'status': status, 'message': str(preview.get('message', 'Existing task status recovered.'))[:250]}
            if preview.get('run_id'):
                fields['run_id'] = preview['run_id']
            if preview.get('approval_pending'):
                fields.update(status='needs_attention', message='This existing Hermes task requires separate approval review.')
            elif status in _SUCCESS:
                fields['result'] = preview.get('text', '')
                fields['message'] = 'Completed task recovered. Review the complete page before applying it.'
            elif not preview.get('receipt_exists') and status not in _TERMINAL:
                fields.update(status='needs_attention', message='No run receipt is available. The original task was retained without resubmitting it.')
            return self.update(request_id, **fields)
        except Exception:
            return self.update(request_id, status='needs_attention',
                message='The existing task could not be recovered. Its identity and any saved result were preserved; no task was resubmitted.')

    def stop(self, request_id, service, *, local_only=False):
        record = self.get(request_id)
        if self._local_only(service, local_only):
            return self.update(request_id, status='local_only', message='Remote cancellation is disabled in local-only mode.')
        try:
            preview = self._selection(record, service)
            if not preview.get('receipt_exists'):
                raise BoardRecoveryError('No existing run receipt is available for cancellation.')
            if preview.get('status') not in _TERMINAL:
                service.stop(record['hermes_request_id'])
            return self.refresh(request_id, service, local_only=local_only)
        except Exception:
            return self.update(request_id, status='needs_attention',
                message='Remote cancellation is unconfirmed. Retain this task and refresh its existing receipt; no replacement was submitted.')
