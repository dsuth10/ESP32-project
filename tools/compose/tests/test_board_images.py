"""Offline import durability/privacy using synthetic images and stores."""
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import uuid

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_images import SavedImageLibrary, prepare_file, import_prepared, read_image
from media_store import MediaStore


def image_bytes(size=(320, 180), colour='blue'):
    stream = io.BytesIO(); Image.new('RGB', size, colour).save(stream, 'PNG'); return stream.getvalue()


def test_local_file_copied_without_source_path_or_prompt(tmp_path):
    path = tmp_path / 'private source.png'; data = image_bytes(); path.write_bytes(data)
    prepared = prepare_file(path)
    media = MediaStore(tmp_path / 'lesson/media')
    record = import_prepared(media, prepared)
    path.unlink()
    assert media.blob_path(record['sha256']).read_bytes() == data
    assert record['source'] == {}
    assert record['width'] / record['height'] == pytest.approx(16/9)


def test_library_retains_selected_identity_and_provenance_without_source_writes(tmp_path):
    source = MediaStore(tmp_path / 'source')
    first = source.import_bytes(image_bytes(), 'Original', source={'creator': 'Teacher', 'licence': 'CC0',
        'attribution': 'Teacher illustration', 'private': 'excluded'}, prompt='private original prompt')
    second = source.add_generated(image_bytes(colour='red'), 'Refined', asset_id=first['asset_id'],
                                  parent_version_id=first['version_id'], prompt='private refinement')
    source.set_canonical(first['asset_id'], first['version_id'], canonical_title='Original')
    source.create_job('generation', 'private job')
    before = {p.relative_to(source.root): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in source.root.rglob('*') if p.is_file()}
    library = SavedImageLibrary(source.root)
    assert library.assets('original')[0]['canonical_version_id'] == first['version_id']
    selected = next(r for r in library.versions(first['asset_id']) if r['version_id'] == second['version_id'])
    prepared = library.prepare(selected)
    lesson = MediaStore(tmp_path / 'lesson/media')
    copied = import_prepared(lesson, prepared)
    assert all(copied[key] == second[key] for key in ('asset_id', 'version_id', 'sha256', 'parent_version_id'))
    assert copied['source'] == second['source']
    assert lesson.list_jobs() == []
    with lesson._connect() as db:
        assert db.execute('SELECT count(*) FROM local_prompt').fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM sync_outbox').fetchone()[0] == 0
    assert before == {p.relative_to(source.root): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in source.root.rglob('*') if p.is_file()}
    # Choosing an older version remains deterministic after a canonical change.
    source.set_canonical(first['asset_id'], second['version_id'])
    older = next(r for r in library.versions(first['asset_id']) if r['version_id'] == first['version_id'])
    assert library.prepare(older).data == image_bytes()


def test_missing_library_is_not_created(tmp_path):
    absent = tmp_path / 'absent'
    with pytest.raises(ValueError, match='existing'):
        SavedImageLibrary(absent)
    assert not absent.exists()


@pytest.mark.parametrize('contents', [b'', b'not an image', b'x'*(20*1024*1024+1)],
                         ids=['empty', 'unsupported', 'oversized'])
def test_invalid_files_rejected_before_cache_write(tmp_path, contents):
    path = tmp_path / 'image.png'; path.write_bytes(contents)
    with pytest.raises(ValueError):
        prepare_file(path)


def test_image_bomb_rejected(tmp_path):
    path = tmp_path / 'large.png'; path.write_bytes(image_bytes((5100, 5000)))
    with pytest.raises(ValueError, match='megapixel'):
        prepare_file(path)


def test_library_missing_or_changed_blob_is_rejected(tmp_path):
    store = MediaStore(tmp_path / 'source'); record = store.import_bytes(image_bytes(), 'Saved')
    library = SavedImageLibrary(store.root); selected = library.versions(record['asset_id'])[0]
    store.blob_path(record['sha256']).write_bytes(image_bytes(colour='red'))
    with pytest.raises(ValueError, match='damaged'):
        library.prepare(selected)
    store.blob_path(record['sha256']).unlink()
    with pytest.raises(ValueError, match='unavailable'):
        library.prepare(selected)


def test_snapshot_change_is_rejected(tmp_path):
    store = MediaStore(tmp_path / 'source'); record = store.import_bytes(image_bytes(), 'Saved')
    library = SavedImageLibrary(store.root); selected = library.versions(record['asset_id'])[0]
    selected['title'] = 'stale'
    with pytest.raises(ValueError, match='changed'):
        library.prepare(selected)


def test_prepared_library_can_be_imported_after_source_removed(tmp_path):
    source = MediaStore(tmp_path / 'source'); record = source.import_bytes(image_bytes(), 'Saved')
    library = SavedImageLibrary(source.root)
    prepared = library.prepare(library.versions(record['asset_id'])[0])
    source.blob_path(record['sha256']).unlink(); source.path.unlink()
    lesson = MediaStore(tmp_path / 'lesson/media'); copied = import_prepared(lesson, prepared)
    assert lesson.blob_path(copied['sha256']).read_bytes() == prepared.data
    # A repeat uses the same version, rather than creating an unrelated variant.
    assert import_prepared(lesson, prepared)['version_id'] == copied['version_id']


def test_search_filters_before_result_limit_and_preserves_unicode_casefold(tmp_path):
    source = MediaStore(tmp_path / 'source')
    old = source.import_bytes(image_bytes(), 'Older WÄTER cycle')
    with source._connect() as db:
        db.execute('UPDATE asset SET updated_at=? WHERE asset_id=?', ('1999', old['asset_id']))
        db.executemany('INSERT INTO asset VALUES (?,?,?,NULL,0,0,?,?)',
                       [(str(uuid.uuid4()), f'Recent image {i}', '[]', '2026', '2026') for i in range(510)])
    library = SavedImageLibrary(source.root)
    assert len(library.assets()) == 500
    assert library.assets('wÄter')[0]['asset_id'] == old['asset_id']


def test_canonical_remains_available_outside_recent_version_limit(tmp_path):
    source = MediaStore(tmp_path / 'source')
    old = source.import_bytes(image_bytes(), 'Older canonical')
    source.set_canonical(old['asset_id'], old['version_id'])
    with source._connect() as db:
        row = list(db.execute('SELECT * FROM asset_version WHERE version_id=?', (old['version_id'],)).fetchone())
        recent = []
        for index in range(510):
            values = row.copy(); values[0] = str(uuid.uuid4()); values[-1] = '2099'; recent.append(tuple(values))
        db.executemany('INSERT INTO asset_version VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', recent)
    versions = SavedImageLibrary(source.root).versions(old['asset_id'])
    assert len(versions) == 501
    assert versions[-1]['version_id'] == old['version_id']
