"""Local catalogue integration; source libraries remain read-only.

Only selected, hash-checked image bytes enter the reusable cache and lesson.
Source paths/cursors stay in a private registry and never enter agent context.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re
import sqlite3
import threading
import uuid

from board_images import SavedImageLibrary, import_prepared, safe_path
from board_model import BoardModel, canonical_json, new_lesson
from board_resources import ResourceCatalogue, RELATIONSHIPS
from media_store import MediaStore

MAX_IMPORTED_RESOURCES = 500
MAX_IMPORTED_RELATIONSHIPS = 5000
_PRIVATE_KEYS = {'path', 'root', 'local_path', 'source_path', 'cache_path', 'file_path', 'database_path'}


def _strict_json(value, label):
    try:
        return json.loads(value, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise ValueError(f'The imported {label} is not finite valid JSON.') from None


def _no_private_paths(value):
    if isinstance(value, dict):
        if any(str(key).casefold() in _PRIVATE_KEYS for key in value):
            raise ValueError('Imported catalogue metadata cannot contain local source paths.')
        for child in value.values():
            _no_private_paths(child)
    elif isinstance(value, list):
        for child in value:
            _no_private_paths(child)


class _ResolvedResourceCatalogue(ResourceCatalogue):
    """Catalogue that recognises verified source blobs without copying them."""
    def _media_blob_available(self, media_ref, digest, expected_size=None):
        if getattr(getattr(self, '_index_mode', None), 'metadata_only', False):
            return False
        if super()._media_blob_available(media_ref, digest, expected_size):
            return True
        if not media_ref or not callable(self.resolver):
            return False
        resolved = self.resolver(media_ref.get('asset_id'), media_ref.get('version_id'))
        if not resolved or resolved.get('sha256') != digest:
            return False
        path_value = resolved.get('path')
        if not path_value:
            return False
        try:
            path = safe_path(path_value)
            size = path.stat().st_size
            if not path.is_file() or size > 20 * 1024 * 1024:
                return False
            if expected_size is not None and size != expected_size:
                return False
            hasher = hashlib.sha256()
            with path.open('rb') as stream:
                while chunk := stream.read(64 * 1024):
                    hasher.update(chunk)
            return hasher.hexdigest() == digest
        except (OSError, RuntimeError, ValueError):
            return False


class BoardResourceLibrary:
    def __init__(self, root):
        self.root = safe_path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.media = MediaStore(self.root / 'media')
        self._index_mode = threading.local()
        self.registry = self.root / 'local-sources.sqlite3'
        with sqlite3.connect(self.registry) as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS source_version
                (version_id TEXT PRIMARY KEY, root TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS source_cursor
                (root TEXT PRIMARY KEY, last_rowid INTEGER NOT NULL);''')
        self.catalogue = _ResolvedResourceCatalogue(self.root / 'catalogue', resolver=self._resolve_source_image)

    def _resolve_source_image(self, asset_id, version_id):
        """Resolve only a registered source identity and reverify its blob."""
        with sqlite3.connect(self.registry) as db:
            row = db.execute('SELECT root FROM source_version WHERE version_id=?', (version_id,)).fetchone()
        if not row:
            return None
        source = SavedImageLibrary(row[0])
        with source.connect() as db:
            version_row = db.execute('SELECT * FROM asset_version WHERE version_id=?', (version_id,)).fetchone()
        if version_row is None:
            return None
        version = source._record(version_row)
        if version['asset_id'] != asset_id:
            return None
        path = safe_path(source.root / 'blobs' / 'sha256' / version['sha256'][:2] / version['sha256'][2:])
        if getattr(self._index_mode, 'metadata_only', False):
            return {'asset_id': asset_id, 'version_id': version_id, 'sha256': version['sha256'],
                    'mime': version['mime'], 'byte_size': version['byte_size']}
        prepared = source.prepare(version)
        return {'asset_id': asset_id, 'version_id': version_id, 'sha256': version['sha256'],
                'mime': version['mime'], 'byte_size': len(prepared.data), 'path': str(path)}

    def index_source(self, root, *, batch_size=100):
        """Resumable metadata backfill. No prompts, jobs or credentials are read."""
        if type(batch_size) is not int or not 1 <= batch_size <= 500:
            raise ValueError('Index 1–500 records at a time.')
        source = SavedImageLibrary(root)
        with sqlite3.connect(self.registry) as db:
            row = db.execute('SELECT last_rowid FROM source_cursor WHERE root=?', (str(source.root),)).fetchone()
            cursor = row[0] if row else 0
        with source.connect() as db:
            rows = db.execute('SELECT v.rowid AS cursor,v.*,a.canonical_version_id FROM asset_version v '
                              'JOIN asset a USING(asset_id) WHERE v.rowid>? ORDER BY v.rowid LIMIT ?',
                              (cursor, batch_size)).fetchall()
        for row in rows:
            version = source._record(row)
            approved = row['canonical_version_id'] == version['version_id']
            self._index(version, source.root, approved=approved, availability='metadata_only')
            # A crash before this point simply replays idempotent catalogue work.
            with sqlite3.connect(self.registry) as db:
                db.execute('INSERT OR REPLACE INTO source_cursor VALUES (?,?)', (str(source.root), row['cursor']))
        return {'indexed': len(rows), 'more': len(rows) == batch_size}

    def _index(self, version, source_root, *, approved=False, availability='offline', source_metadata=None):
        ref = {key: version[key] for key in ('asset_id', 'version_id', 'sha256')}
        source = version.get('source', {})
        metadata = {'width': version['width'], 'height': version['height'], 'origin': version.get('origin', 'imported')}
        if source_metadata and source_metadata.get('visual_kind') in {'image', 'chart'}:
            metadata['visual_kind'] = source_metadata['visual_kind']
        title = version.get('version_title', version.get('title', ''))
        if not isinstance(title, str) or not title.strip() or len(title) > 200:
            raise ValueError('A saved version title must fit the immutable catalogue limit.')
        tags = version.get('version_tags', version.get('tags', []))
        provenance = {**source, **(source_metadata or {})}
        # Register the trusted, private source path before catalogue validation
        # asks the resolver to verify the exact version's bytes.
        with sqlite3.connect(self.registry) as db:
            db.execute('INSERT OR REPLACE INTO source_version VALUES (?,?)', (ref['version_id'], str(safe_path(source_root))))
        item = self.catalogue.get_resource_by_version(ref['version_id'])
        if item and not (source_metadata and source_metadata.get('visual_kind') in {'image', 'chart'}):
            # Re-indexing exact retained bytes must preserve typed visual
            # metadata already attached by the chart/resource pipeline.
            if item['metadata'].get('visual_kind') in {'image', 'chart'}:
                metadata['visual_kind'] = item['metadata']['visual_kind']
        if item and item['image_ref'] != ref:
            raise ValueError('A reusable version identity conflicts with its saved hash.')
        if item and (item.get('source_title', item['title']) != title
                     or item.get('source_tags', item['tags']) != tags or item['metadata'] != metadata
                     or any(item['provenance'].get(key) != value for key, value in source.items())):
            raise ValueError('A reusable version identity conflicts with its immutable title, tags or provenance.')
        if item is None:
            self._index_mode.metadata_only = availability == 'metadata_only'
            try:
                item = self.catalogue.save_resource('image', title,
                    resource_id=ref['asset_id'], version_id=ref['version_id'], image_ref=ref,
                    tags=tags, metadata=metadata, provenance=provenance,
                    state='approved' if approved else 'draft', availability=availability,
                    idempotency_key='media:' + ref['version_id'])
            finally:
                self._index_mode.metadata_only = False
        return item

    def retain(self, prepared, *, approved=False):
        version = import_prepared(self.media, prepared)
        return self._index(version, self.media.root, approved=approved)

    def prepare_record(self, record):
        """Resolve and validate without importing or changing review state."""
        actual = self.catalogue.get_resource_by_version(record['version_id'])
        if (not actual or actual['resource_id'] != record['resource_id']
                or actual['content_hash'] != record['content_hash']
                or actual['review_state'] in {'excluded', 'rejected'}):
            raise ValueError('This resource changed or is excluded. Search again.')
        with sqlite3.connect(self.registry) as db:
            row = db.execute('SELECT root FROM source_version WHERE version_id=?', (actual['version_id'],)).fetchone()
        if not row:
            raise ValueError('This exact image has no available local source.')
        source = SavedImageLibrary(row[0])
        versions = source.versions(actual['image_ref']['asset_id'])
        version = next((value for value in versions if value['version_id'] == actual['version_id']), None)
        if not version or version['sha256'] != actual['content_hash']:
            raise ValueError('This pinned image version is unavailable.')
        prepared = source.prepare(version)
        return actual, prepared

    def select(self, record, lesson_media, *, required=True):
        """Resolve an exact current catalogue row, verify bytes, retain both caches."""
        actual, prepared = self.prepare_record(record)
        self.retain(prepared, approved=actual['review_state'] == 'approved')
        local = import_prepared(lesson_media, prepared)
        result = {'image_ref': {key: local[key] for key in ('asset_id', 'version_id', 'sha256')},
                'title': actual['title'], 'width': prepared.width, 'height': prepared.height,
                'required': required,
                'generated_unreviewed': actual['metadata'].get('origin') == 'generated' and actual['review_state'] != 'approved'}
        if actual['provenance'].get('visual_kind') in {'image', 'chart'}:
            result['visual_kind'] = actual['provenance']['visual_kind']
        credit = actual['provenance'].get('attribution', '')
        if credit:
            result['credit'] = credit
        return result

    def import_catalogue(self, source_catalogue_root, source_media_root=None):
        """Merge a validated portable catalogue while keeping roots private.

        The importer consumes only resource versions, aliases, review state and
        pinned relationships. It never opens History, prompts, jobs or settings.
        """
        source_path = safe_path(source_catalogue_root)
        database = source_path / 'board_resources.sqlite3' if source_path.is_dir() else source_path
        database = safe_path(database)
        if not database.is_file():
            raise ValueError('The imported lesson catalogue is unavailable.')
        media_root = safe_path(source_media_root) if source_media_root is not None else None
        with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=3) as db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA query_only=ON')
            version = int(db.execute('PRAGMA user_version').fetchone()[0])
            if version != 1:
                raise ValueError('The imported lesson catalogue has an unsupported schema.')
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            rows = db.execute('SELECT * FROM resource_version ORDER BY created_at,version_id LIMIT ?',
                              (MAX_IMPORTED_RESOURCES + 1,)).fetchall()
            if len(rows) > MAX_IMPORTED_RESOURCES:
                raise ValueError(f'Import at most {MAX_IMPORTED_RESOURCES} resource versions at a time.')
            records = []
            for row in rows:
                item = dict(row)
                item['metadata'] = _strict_json(item['metadata_json'], 'metadata')
                item['provenance'] = _strict_json(item['provenance_json'], 'provenance')
                item['tags'] = _strict_json(item['tags_json'], 'tags')
                _no_private_paths(item['metadata']); _no_private_paths(item['provenance'])
                override = db.execute('SELECT review_state FROM review_override WHERE resource_id=? AND version_id=?',
                    (item['resource_id'], item['version_id'])).fetchone()
                item['review_state'] = override[0] if override else item['review_state']
                item['aliases'] = [alias[0] for alias in db.execute(
                    'SELECT alias FROM resource_alias WHERE resource_id=? AND (version_id=? OR version_id IS NULL) ORDER BY normalised,alias',
                    (item['resource_id'], item['version_id']))]
                item['review_state'] = item['review_state'] or 'draft'
                # Corrections travel separately from immutable source metadata.
                # Remembered names remain personal to the receiving library.
                item['teacher_metadata'] = None
                if 'resource_metadata_override' in tables:
                    correction = db.execute('SELECT * FROM resource_metadata_override WHERE version_id=?',
                                            (item['version_id'],)).fetchone()
                    if correction:
                        item['teacher_metadata'] = dict(correction)
                records.append(item)
            relations = db.execute('SELECT * FROM resource_relationship ORDER BY relationship_id LIMIT ?',
                                   (MAX_IMPORTED_RELATIONSHIPS + 1,)).fetchall()
            if len(relations) > MAX_IMPORTED_RELATIONSHIPS:
                raise ValueError(f'Import at most {MAX_IMPORTED_RELATIONSHIPS} resource relationships at a time.')
            relations = [dict(row) for row in relations]
            for relation in relations:
                relation['metadata'] = _strict_json(relation['metadata_json'], 'relationship metadata')
                _no_private_paths(relation['metadata'])
        if any(record['resource_type'] == 'image' for record in records) and media_root is None:
            raise ValueError('An imported catalogue with images needs its paired media-library folder.')

        registered = []
        if media_root is not None:
            with sqlite3.connect(self.registry) as db:
                for item in records:
                    if item['resource_type'] != 'image':
                        continue
                    if not item['media_asset_id'] or not item['media_version_id'] or not item['content_hash']:
                        raise ValueError('An imported image resource needs an exact media version and hash.')
                    old = db.execute('SELECT root FROM source_version WHERE version_id=?',
                                     (item['media_version_id'],)).fetchone()
                    registered.append((item['media_version_id'], old[0] if old else None))
                    db.execute('INSERT OR REPLACE INTO source_version VALUES (?,?)',
                                (item['media_version_id'], str(media_root)))
        try:
            for item in records:
                image_ref = None
                if item['resource_type'] == 'image':
                    image_ref = {'asset_id': item['media_asset_id'], 'version_id': item['media_version_id'],
                                 'sha256': item['content_hash']}
                    verified = self._resolve_source_image(image_ref['asset_id'], image_ref['version_id'])
                    if not verified or verified['sha256'] != item['content_hash']:
                        raise ValueError('An imported image does not match its exact media bytes.')
                existing = self.catalogue.get_resource_by_version(item['version_id'])
                if existing:
                    expected_ref = image_ref
                    if (existing['resource_id'] != item['resource_id'] or existing['resource_type'] != item['resource_type']
                            or existing.get('source_title', existing['title']) != item['title']
                            or existing.get('source_description', existing['description']) != item['description']
                            or existing.get('source_tags', existing['tags']) != item['tags'] or existing['metadata'] != item['metadata']
                            or existing['provenance'] != item['provenance'] or existing['content_hash'] != item['content_hash']
                            or existing['mime'] != item['mime'] or existing['byte_size'] != item['byte_size']
                            or (expected_ref is not None and existing['image_ref'] != expected_ref)):
                        raise ValueError('An imported resource identity conflicts with an existing immutable version.')
                    for alias in item['aliases']:
                        self.catalogue.add_alias(item['resource_id'], alias, version_id=item['version_id'])
                    continue
                self.catalogue.save_resource(item['resource_type'], item['title'], metadata=item['metadata'],
                    description=item['description'], aliases=item['aliases'], tags=item['tags'],
                    provenance=item['provenance'], resource_id=item['resource_id'], version_id=item['version_id'],
                    content_hash=item['content_hash'], mime=item['mime'], byte_size=item['byte_size'],
                    availability=item['availability'], state=item['review_state'], image_ref=image_ref,
                    idempotency_key='import:' + item['version_id'])
                correction = item.get('teacher_metadata')
                if correction:
                    fields = {key: correction[key] for key in ('title', 'description') if correction.get(key) is not None}
                    for key in ('tags', 'topics', 'year_levels'):
                        if correction.get(key + '_json') is not None:
                            fields[key] = _strict_json(correction[key + '_json'], 'teacher ' + key)
                    self.catalogue.update_metadata(item['version_id'], **fields)
            version_ids = {item['version_id'] for item in records}
            for relation in relations:
                if (relation['source_version_id'] not in version_ids
                        or relation['target_version_id'] not in version_ids):
                    raise ValueError('An imported relationship refers to a version outside this package.')
                if relation['relation'] not in RELATIONSHIPS:
                    raise ValueError('An imported relationship type is unsupported.')
                by_version = {item['version_id']: item['resource_id'] for item in records}
                # Preserve pinned links even when a version has a local
                # rejected/excluded review override (resolve intentionally
                # hides those from normal selection).
                with self.catalogue._connect() as local_db:
                    local_db.execute('PRAGMA foreign_keys=ON')
                    local_db.execute('''INSERT OR IGNORE INTO resource_relationship
                        (source_resource_id,source_version_id,relation,target_resource_id,target_version_id,metadata_json,created_at)
                        VALUES (?,?,?,?,?,?,datetime('now'))''',
                        (by_version[relation['source_version_id']], relation['source_version_id'],
                         relation['relation'], by_version[relation['target_version_id']],
                         relation['target_version_id'], canonical_json(relation['metadata'])))
        except Exception:
            # Uncommitted sources remain private registry entries only; they are
            # harmless and allow an idempotent retry after a partial catalogue merge.
            raise
        return {'resources': len(records), 'relationships': len(relations)}

    def retain_page(self, page, request_id, *, media_store=None):
        """Save an applied page as one immutable local resource with exact image links."""
        try:
            request_uuid = str(uuid.UUID(request_id))
            document = new_lesson('Saved Teaching Board page')
            document['pages'] = [page]
            validated = BoardModel(document).snapshot()['pages'][0]
            metadata = {'schema': 1, 'page': validated}
            raw = canonical_json(metadata)
        except (ValueError, TypeError, KeyError):
            raise ValueError('The applied Board page or request identity is invalid.') from None
        if len(raw) > 64 * 1024:
            raise ValueError('This page is larger than the 64 KiB reusable-resource limit; its action marker remains local.')
        digest = hashlib.sha256(raw).hexdigest()
        page_id = validated['id']
        resource_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'board-page:' + page_id))
        version_id = str(uuid.uuid5(uuid.UUID(request_uuid), 'board-page-version:' + page_id))
        stores = [self.media]
        if media_store is not None and media_store is not self.media:
            stores.append(media_store)
        refs = {}
        for obj in validated['objects']:
            if obj['type'] != 'image':
                continue
            ref = obj['image_ref']
            target = self.catalogue.get_resource_by_version(ref['version_id'])
            if not target:
                found = None
                for store in stores:
                    source = store.get_version(ref['version_id'])
                    if source and source['asset_id'] == ref['asset_id'] and source['sha256'] == ref['sha256']:
                        found = source, store.root
                        break
                if found:
                    self._index(found[0], found[1])
                    target = self.catalogue.get_resource_by_version(ref['version_id'])
            if (not target or target['image_ref'] != ref or target['review_state'] in {'excluded', 'rejected'}):
                raise ValueError('A saved page image lacks an approved exact catalogue version.')
            refs[ref['version_id']] = True
        record = self.catalogue.save_resource('page', validated['title'], metadata=metadata,
            provenance={'kind': 'teaching_board', 'request_id': request_uuid},
            resource_id=resource_id, version_id=version_id, content_hash=digest,
            availability='offline', state='approved', idempotency_key='board-page:' + request_uuid + ':' + page_id)
        for version_ref in refs:
            self.catalogue.add_relationship(record['version_id'], 'uses', version_ref)
        return record

    def approve(self, version_id):
        record = self.catalogue.get_resource_by_version(version_id)
        if not record:
            raise ValueError('This resource is unavailable.')
        self.catalogue.set_review_state(record['resource_id'], record['version_id'], 'approved',
                                        'Teacher accepted this exact resource for Board reuse.')

    def search(self, query='', *, limit=8, **filters):
        return self.catalogue.search(query, resource_types=['image'], limit=limit, **filters)

    def search_resources(self, query='', *, resource_types=None, limit=8, **filters):
        """Search bounded reusable resource types for the Board chooser."""
        return self.catalogue.search(query, resource_types=resource_types, limit=limit, **filters)

    def automatic_match(self, query):
        """Resolve a single exact approved image alias, ignoring other types."""
        query = str(query).strip()
        if not query:
            return None
        record = self.catalogue.resolve(query, resource_types=['image'])
        if record is None or record['resource_type'] != 'image':
            return None
        if record['review_state'] != 'approved' or record['availability'] == 'unavailable':
            return None
        try:
            # Reopen the exact registered source and verify the bytes/hash before
            # an alias can be used without a chooser.
            self.prepare_record(record)
        except (OSError, ValueError):
            return None
        return record
