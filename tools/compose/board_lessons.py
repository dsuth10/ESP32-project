"""Independent, staged copies of saved isolated Teaching Board lessons.

Only referenced image bytes/provenance and bounded lesson history are copied.
The caller switches sessions only after this helper succeeds; the source stays
open and unchanged. No provider, Office, device or network operation is used.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import uuid

from board_model import BoardModel, BoardConflictError, BoardValidationError
from board_session import BoardSession
from board_store import BoardStore
from media_store import MediaStore

REPOSITORY = Path(__file__).resolve().parents[2]
CANDIDATE_ROOT = REPOSITORY / '.local' / 'teaching-board-candidate'


def saved_lessons_root():
    """One shared, repo-local folder for named lesson reopen entries."""
    root = _directory(CANDIDATE_ROOT / 'saved-lessons')
    root.mkdir(parents=True, exist_ok=True)
    _validate_tree(root)
    return root


def _title_stem(title):
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise BoardValidationError('Lesson title must contain 1–200 characters.')
    # Titles remain unchanged in the document; only Windows filenames are cleaned.
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '-', title.strip()).rstrip(' .')[:48].rstrip(' .')
    if not stem:
        stem = 'Lesson'
    if stem.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                                       *('COM' + str(i) for i in range(1, 10)),
                                       *('LPT' + str(i) for i in range(1, 10))}:
        stem = 'Lesson ' + stem
    return stem


def new_saved_lesson_directory(title):
    data = _directory(saved_lessons_root() / 'data')
    data.mkdir(exist_ok=True)
    return data / (_title_stem(title) + ' -- ' + uuid.uuid4().hex[:12])


def is_catalogue_lesson(root):
    """Keep automated fixtures and diagnostic snapshots out of teacher lessons."""
    try:
        root = _directory(root)
    except ValueError:
        return False
    base = CANDIDATE_ROOT.resolve()
    if root.parent == base / 'saved-lessons' / 'data':
        return True
    return (root.parent == base and root.name != 'saved-lessons'
            and not root.name.startswith(('.', 'pytest', 'smoke', 'crash-', 'feedback-native-smoke')))


def _catalogue_key(root):
    return hashlib.sha256(str(root).casefold().encode('utf-8')).hexdigest()[:16]


def _entry_bytes(key):
    # The title/path are data in JSON, never interpolated into shell commands.
    return ('@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass '
            '-File "%~dp0.open-lesson.ps1" -LessonKey ' + key + '\r\n'
            'if errorlevel 1 pause\r\n').encode('ascii')


def _atomic_catalogue_write(root, name, data):
    destination = root / name
    if destination.is_symlink() or destination.is_junction():
        raise ValueError('Saved lesson access files must not redirect through links.')
    temporary = root / ('.catalogue-pending-' + uuid.uuid4().hex)
    try:
        with temporary.open('xb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _catalogue_script():
    python = str(REPOSITORY / '.local/teaching-board-renderer-env/Scripts/pythonw.exe').replace("'", "''")
    entry = str(REPOSITORY / 'tools/compose/board_candidate.py').replace("'", "''")
    repository = str(REPOSITORY).replace("'", "''")
    return ("param([Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{16}$')][string]$LessonKey)\n"
            "$ErrorActionPreference = 'Stop'\n"
            "$catalogue = Get-Content -LiteralPath (Join-Path $PSScriptRoot '.catalogue.json') -Raw -Encoding UTF8 | ConvertFrom-Json\n"
            "$lesson = @($catalogue.entries | Where-Object { $_.key -ceq $LessonKey })\n"
            "if ($lesson.Count -ne 1) { throw 'This lesson entry is unavailable. Reopen Saved lessons from the application.' }\n"
            "$candidateRoot = Split-Path $PSScriptRoot -Parent\n"
            "$lessonRoot = [IO.Path]::GetFullPath((Join-Path $candidateRoot $lesson[0].path))\n"
            "if (-not $lessonRoot.StartsWith($candidateRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Lesson must stay inside the local candidate folder.' }\n"
            "if (-not ((Test-Path -LiteralPath (Join-Path $lessonRoot 'lesson.json')) -or (Test-Path -LiteralPath (Join-Path $lessonRoot 'lesson.previous.json')))) { throw 'Saved lesson is unavailable; no new lesson was created.' }\n"
            f"$lessonPython = '{python}'\n$lessonEntry = '{entry}'\n"
            "if (-not (Test-Path -LiteralPath $lessonPython -PathType Leaf)) { throw 'Isolated Teaching Board runtime is unavailable.' }\n"
            "$lessonArguments = @(('\"' + $lessonEntry + '\"'), '--data-root', ('\"' + $lessonRoot + '\"'))\n"
            f"Start-Process -FilePath $lessonPython -ArgumentList $lessonArguments -WorkingDirectory '{repository}' -WindowStyle Hidden\n").encode('utf-8-sig')


def refresh_saved_lesson_access(extra_roots=()):
    """Publish named launchers without moving or writing any source lesson.

    Discovery is shallow: direct teacher lesson folders plus saved-lessons/data.
    Registered source paths are retained across renames; diagnostics are excluded.
    """
    root = saved_lessons_root()
    with BoardStore(root)._exclusive():
        manifest = root / '.catalogue.json'
        old = []
        if manifest.exists():
            if manifest.stat().st_size > 2 * 1024 * 1024:
                raise ValueError('Saved lesson catalogue is oversized.')
            previous = json.loads(manifest.read_text(encoding='utf-8'))
            if previous.get('schema') != 1 or not isinstance(previous.get('entries'), list):
                raise ValueError('Saved lesson catalogue is invalid.')
            old = previous['entries']
            for record in old:
                path = _directory(CANDIDATE_ROOT / record['path'])
                key = _catalogue_key(path)
                if (record['key'] != key
                        or record['file'] != _title_stem(record['title']) + ' [' + key + '].cmd'):
                    raise ValueError('Saved lesson catalogue contains an invalid entry.')
        sources = {path for path in CANDIDATE_ROOT.iterdir() if path.is_dir() and is_catalogue_lesson(path)}
        data = root / 'data'
        if data.exists():
            sources.update(path for path in data.iterdir() if path.is_dir() and is_catalogue_lesson(path))
        sources.update(_directory(CANDIDATE_ROOT / item['path']) for item in old)
        sources.update(_directory(path) for path in extra_roots if is_catalogue_lesson(path))
        entries, warnings = [], []
        for source in sorted(sources):
            # Static decoding does not create a lock, database or journal in sources.
            if not (source / 'lesson.json').exists() and not (source / 'lesson.previous.json').exists():
                continue
            try:
                document = None
                for name in ('lesson.json', 'lesson.previous.json'):
                    checkpoint = source / name
                    _directory(checkpoint)
                    try:
                        document = BoardStore._decode(BoardStore._read(checkpoint)).snapshot()
                        break
                    except RuntimeError:
                        continue
                if document is None:
                    raise ValueError('No valid current or previous saved checkpoint.')
                key = _catalogue_key(source)
                entries.append(dict(key=key, path=source.relative_to(CANDIDATE_ROOT.resolve()).as_posix(),
                                    title=document['title'],
                                    file=_title_stem(document['title']) + ' [' + key + '].cmd'))
            except (OSError, ValueError, RuntimeError) as error:
                warnings.append(source.name + ': ' + str(error))
                # Preserve an existing access entry for a damaged lesson for recovery.
                entries.extend(item for item in old if item['path'] == source.relative_to(CANDIDATE_ROOT.resolve()).as_posix())
        for item in entries:
            destination = root / item['file']
            contents = _entry_bytes(item['key'])
            if destination.exists() and destination.read_bytes() != contents:
                raise FileExistsError('An unrelated file occupies saved lesson entry ' + item['file'])
            _atomic_catalogue_write(root, item['file'], contents)
        _atomic_catalogue_write(root, '.open-lesson.ps1', _catalogue_script())
        _atomic_catalogue_write(root, '.catalogue.json', json.dumps(
            dict(schema=1, entries=entries), ensure_ascii=False, indent=2).encode('utf-8'))
        # Delete only known generated entries whose title changed, after publishing.
        current_files = {item['file'] for item in entries}
        for item in old:
            previous_file = root / item['file']
            if (item['file'] not in current_files and previous_file.is_file()
                    and previous_file.read_bytes() == _entry_bytes(item['key'])):
                previous_file.unlink()
        return dict(root=root, entries=entries, warnings=warnings)


def _directory(value):
    raw = Path(value).expanduser().absolute()
    for entry in (raw, *raw.parents):
        if entry.is_symlink() or entry.is_junction():
            raise ValueError('Lesson folders must not redirect through links or junctions.')
    path = raw.resolve()
    allowed = CANDIDATE_ROOT.absolute().resolve()
    if path == allowed or allowed not in path.parents:
        raise ValueError('Choose a lesson subfolder inside .local/teaching-board-candidate/.')
    return path


def _validate_tree(root):
    _directory(root)
    for directory, folders, files in os.walk(root, followlinks=False):
        for name in folders + files:
            entry = Path(directory) / name
            if entry.is_symlink() or entry.is_junction():
                raise ValueError('Lesson storage must not contain links or junctions.')


def _documents(state):
    return [state['document'], *state['undo'], *state['redo']]


def _references(state):
    return [obj['image_ref'] for document in _documents(state)
            for page in document['pages'] for obj in page['objects']
            if obj['type'] == 'image']


def local_image_resolver(store):
    """Resolve only exact local managed versions, with bounded verified bytes."""
    def resolve(reference):
        version = store.get_version(reference['version_id'])
        if not version or any(version[key] != reference[key]
                              for key in ('asset_id', 'version_id', 'sha256')):
            raise ValueError('Pinned image version is unavailable.')
        path = store.blob_path(reference['sha256'])
        for entry in (path, *path.parents):
            if entry.is_symlink() or entry.is_junction():
                raise ValueError('Image storage must not redirect through links or junctions.')
        if store.blobs.resolve() not in path.resolve().parents or path.stat().st_size > 20 * 1024 * 1024:
            raise ValueError('Image is outside managed storage or oversized.')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != reference['sha256']:
            raise ValueError('Pinned image digest does not match.')
        return data
    return resolve


def _metadata(source_root, reference):
    # Read-only SQLite avoids migrations, journal writes or copying local prompts,
    # jobs and unrelated library records from the source.
    database = source_root / 'media' / 'media.sqlite3'
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            'SELECT asset_id, sha256, version_title, version_tags_json, source_json, origin '
            'FROM asset_version WHERE version_id=?', (reference['version_id'],)).fetchone()
    if row is None or row['asset_id'] != reference['asset_id'] or row['sha256'] != reference['sha256']:
        raise ValueError('Pinned image metadata is unavailable.')
    return dict(title=row['version_title'], tags=json.loads(row['version_tags_json']),
                source=json.loads(row['source_json']), origin=row['origin'])


def _write_launcher(root):
    python = str(REPOSITORY / '.local' / 'teaching-board-renderer-env' / 'Scripts' / 'pythonw.exe').replace("'", "''")
    entry = str(REPOSITORY / 'tools' / 'compose' / 'board_candidate.py').replace("'", "''")
    repository = str(REPOSITORY).replace("'", "''")
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        f"$lessonPython = '{python}'\n$lessonEntry = '{entry}'\n"
        "if (-not (Test-Path -LiteralPath $lessonPython -PathType Leaf)) { throw 'Isolated Teaching Board runtime is unavailable.' }\n"
        "$lessonArguments = @(('\"' + $lessonEntry + '\"'), '--data-root', ('\"' + $PSScriptRoot + '\"'))\n"
        f"Start-Process -FilePath $lessonPython -ArgumentList $lessonArguments -WorkingDirectory '{repository}' -WindowStyle Hidden\n"
    )
    (root / 'reopen-lesson.ps1').write_text(script, encoding='utf-8')
    (root / 'Open Teaching Board Lesson.cmd').write_text(
        '@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0reopen-lesson.ps1"\r\nif errorlevel 1 pause\r\n',
        encoding='utf-8', newline='')


def copy_saved_lesson(session, source_root, destination, title):
    """Return (session, store, resolver) for a new, fully validated saved copy.

    Flush and save edits before calling. Destination must be a new sibling or
    a named folder in the shared saved-lessons/data directory. A new lesson identity applies to all copied history;
    copied history keeps its original content but uses the copy's chosen title.
    Existing destinations are never replaced. The source session stays open.
    """
    if not isinstance(session, BoardSession):
        raise BoardValidationError('Copy a saved BoardSession.')
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise BoardValidationError('Copy title must contain 1–200 characters.')
    title = title.strip()
    title.encode('utf-8')
    source_root, destination = _directory(source_root), _directory(destination)
    collection_data = _directory(CANDIDATE_ROOT / 'saved-lessons' / 'data')
    if (destination.parent not in (source_root.parent, collection_data)
            or source_root == destination or source_root in destination.parents):
        raise ValueError('Choose a new sibling or shared saved lesson folder for the copy.')
    if destination.exists():
        raise FileExistsError('The copy destination already exists; choose a new lesson folder.')
    _validate_tree(source_root)
    view = session.teacher_view()
    if view['dirty']:
        raise BoardConflictError('Save your changes before making a copy.')
    source_state = BoardStore(source_root).load().export_state()
    if source_state['document'] != view['document']:
        raise BoardConflictError('The saved lesson changed. Reopen before making a copy.')
    state = copy.deepcopy(source_state)
    identity = str(uuid.uuid4())
    for document in _documents(state):
        document['lesson_id'], document['title'] = identity, title
    BoardModel.from_state(state)
    staging = Path(tempfile.mkdtemp(prefix='.lesson-copy-', dir=destination.parent))
    try:
        media = MediaStore(staging / 'media')
        mapping = {}
        for reference in _references(state):
            key = (reference['asset_id'], reference['version_id'], reference['sha256'])
            if key not in mapping:
                data = session.resolve_image(reference)
                record = media.import_bytes(data, **_metadata(source_root, reference))
                mapping[key] = {field: record[field] for field in ('asset_id', 'version_id', 'sha256')}
        for reference in _references(state):
            key = (reference['asset_id'], reference['version_id'], reference['sha256'])
            reference.update(mapping[key])
        store = BoardStore(staging)
        store.save(BoardModel.from_state(state))
        resolver = local_image_resolver(media)
        validated = BoardSession.open(store, image_resolver=resolver)
        try:
            for reference in _references(state):
                validated.resolve_image(reference)
        finally:
            validated.close()
        _write_launcher(staging)
        _validate_tree(staging)
        # Recheck source/session and destination immediately before publication.
        if session.teacher_view() != view or BoardStore(source_root).load().export_state() != source_state:
            raise BoardConflictError('The source changed while making the copy; retry after saving.')
        _directory(destination)
        if destination.exists():
            raise FileExistsError('The copy destination appeared while copying; it was preserved.')
        # Windows rename is atomic and refuses an existing destination.
        os.rename(staging, destination)
        try:
            store = BoardStore(destination)
            resolver = local_image_resolver(MediaStore(destination / 'media'))
            return BoardSession.open(store, image_resolver=resolver), store, resolver
        except Exception:
            raise RuntimeError(
                f'The copy was saved at {destination}, but could not be opened. '
                'The original lesson remains active. The saved copy was preserved; '
                'use its Open Teaching Board Lesson.cmd launcher to retry opening it.'
            ) from None
    finally:
        # Only our fresh staging folder can be removed; never remove the source,
        # destination, or another lesson when a copy or final reopen fails.
        if staging.exists():
            if staging.parent != destination.parent or not staging.name.startswith('.lesson-copy-'):
                raise ValueError('Unexpected copy staging directory.')
            _validate_tree(staging)
            shutil.rmtree(staging)
