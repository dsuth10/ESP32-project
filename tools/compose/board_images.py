"""Explicit, offline image imports into a lesson-owned immutable media store.

Source libraries are opened read-only: browsing never creates/migrates a store,
reads prompts/jobs/settings or starts sync. Prepared choices pin bytes and IDs.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import uuid

from media_store import MediaStore

MAX_BYTES = 20 * 1024 * 1024
SOURCE_KEYS = {'url', 'creator', 'licence', 'attribution', 'provider', 'model'}


def safe_path(value):
    path = Path(value).expanduser().absolute()
    for entry in (path, *path.parents):
        if entry.is_symlink() or entry.is_junction():
            raise ValueError('Image locations must not redirect through links or junctions.')
    return path.resolve()


def read_image(path):
    path = safe_path(path)
    if not path.is_file():
        raise ValueError('The chosen image is unavailable locally.')
    with path.open('rb') as stream:
        data = stream.read(MAX_BYTES + 1)
    MediaStore._inspect(data)
    return data


@dataclass(frozen=True)
class PreparedImage:
    data: bytes
    title: str
    width: int
    height: int
    # Version records are ordered oldest parent first, selected version last.
    versions: tuple = ()


def prepare_file(path):
    data = read_image(path)
    _, width, height = MediaStore._inspect(data)
    return PreparedImage(data, Path(path).stem[:200] or 'Imported image', width, height)


class SavedImageLibrary:
    def __init__(self, root):
        self.root = safe_path(root)
        self.database = safe_path(self.root / 'media.sqlite3')
        if not self.database.is_file():
            raise ValueError('Choose an existing saved image library folder containing media.sqlite3.')
        with self.connect() as db:
            if db.execute('PRAGMA user_version').fetchone()[0] != 2:
                raise ValueError('This image library needs a supported companion version before it can be browsed.')

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database.as_uri() + '?mode=ro', uri=True, timeout=3)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute('PRAGMA query_only=ON')
            yield connection
        finally:
            connection.close()

    def assets(self, query=''):
        words = query.casefold().split()
        result = []
        with self.connect() as db:
            cursor = db.execute('SELECT asset_id,title,tags_json,canonical_version_id FROM asset '
                                'ORDER BY updated_at DESC,asset_id')
            # Filter before the display limit. Stream bounded batches so a known
            # older title remains findable without loading the full catalogue.
            while len(result) < 500:
                rows = cursor.fetchmany(100)
                if not rows:
                    break
                for row in rows:
                    if all(word in (row['title']+' '+row['tags_json']).casefold() for word in words):
                        result.append(dict(row))
                        if len(result) == 500:
                            break
        return result

    def versions(self, asset_id):
        with self.connect() as db:
            rows = db.execute('SELECT * FROM asset_version WHERE asset_id=? '
                              'ORDER BY created_at DESC,version_id DESC LIMIT 500', (asset_id,)).fetchall()
            # A canonical choice can predate the recent-version display window.
            # Always keep that explicit saved choice available in the picker.
            canonical = db.execute('SELECT canonical_version_id FROM asset WHERE asset_id=?',
                                   (asset_id,)).fetchone()
            if canonical and canonical[0] and not any(row['version_id'] == canonical[0] for row in rows):
                row = db.execute('SELECT * FROM asset_version WHERE asset_id=? AND version_id=?',
                                 (asset_id, canonical[0])).fetchone()
                if row:
                    rows.append(row)
        return [self._record(row) for row in rows]

    @staticmethod
    def _record(row):
        value = dict(row)
        source = json.loads(value['source_json'])
        return dict(asset_id=value['asset_id'], version_id=value['version_id'],
                    title=value['version_title'], tags=json.loads(value['version_tags_json']),
                    sha256=value['sha256'], mime=value['mime'], width=value['width'], height=value['height'],
                    byte_size=value['byte_size'], parent_version_id=value['parent_version_id'],
                    source={key: source[key] for key in SOURCE_KEYS if key in source},
                    origin=value['origin'], created_at=value['created_at'])

    def prepare(self, selected):
        """Recheck the displayed immutable record before reading its bounded blob."""
        records, seen, version_id = [], set(), selected['version_id']
        with self.connect() as db:
            while version_id:
                if version_id in seen or len(seen) >= 100:
                    raise ValueError('The saved image has invalid or excessive version ancestry.')
                seen.add(version_id)
                row = db.execute('SELECT * FROM asset_version WHERE version_id=?', (version_id,)).fetchone()
                if row is None:
                    raise ValueError('The saved image version is unavailable.')
                record = self._record(row)
                if record['asset_id'] != selected['asset_id']:
                    raise ValueError('Saved image ancestry belongs to a different asset.')
                records.append(record)
                version_id = record['parent_version_id']
        if records[0] != selected:
            raise ValueError('The saved image changed while choosing it. Select it again.')
        digest = selected['sha256']
        # Validate the digest before using it as part of a path.
        if len(digest) != 64 or any(character not in '0123456789abcdef' for character in digest):
            raise ValueError('The saved image digest is invalid.')
        data = read_image(self.root / 'blobs' / 'sha256' / digest[:2] / digest[2:])
        mime, width, height = MediaStore._inspect(data)
        if (hashlib.sha256(data).hexdigest() != digest or len(data) != selected['byte_size']
                or (mime, width, height) != (selected['mime'], selected['width'], selected['height'])):
            raise ValueError('The saved image is damaged or no longer matches its pinned version.')
        return PreparedImage(data, selected['title'], width, height, tuple(reversed(records)))


def import_prepared(media, prepared):
    """Store bytes durably before publishing the document reference.

    Library identities and selected provenance are retained. Ancestor metadata is
    retained for lineage, but unrelated blobs, prompts and jobs are never copied.
    An interrupted import may leave unreferenced cached media; never a document
    reference to an incompletely written blob.
    """
    mime, width, height = MediaStore._inspect(prepared.data)
    if (width, height) != (prepared.width, prepared.height):
        raise ValueError('Prepared image dimensions do not match its bytes.')
    safe_path(media.root)
    digest = hashlib.sha256(prepared.data).hexdigest()
    if not prepared.versions:
        return media.import_bytes(prepared.data, prepared.title)
    records = copy.deepcopy(prepared.versions)
    selected = records[-1]
    if (selected['sha256'], selected['mime'], selected['byte_size']) != (digest, mime, len(prepared.data)):
        raise ValueError('Prepared image does not match its saved version.')
    blob = safe_path(media.blob_path(digest))
    blob.parent.mkdir(parents=True, exist_ok=True)
    if blob.exists():
        if hashlib.sha256(blob.read_bytes()).hexdigest() != digest:
            raise ValueError('The lesson image cache is damaged; existing media was preserved.')
    else:
        descriptor, temporary = tempfile.mkstemp(prefix='.board-image-', dir=blob.parent)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(prepared.data); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, blob)
        finally:
            Path(temporary).unlink(missing_ok=True)
    for record in records:
        media.apply_remote_event(dict(event_id=str(uuid.uuid4()), kind='version', payload=record))
    return media.get_version(selected['version_id'])
