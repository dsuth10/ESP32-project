"""End-to-end dummy library, media server and no-key provider checks.

Uses synthetic images only. Never calls a live image provider or Hermes.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import threading
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'server'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from board_image_picker import ImagePicker
from board_images import SavedImageLibrary, prepare_file
from board_resource_policy import board_image_issues, board_image_readiness
from board_session import BoardSession
from board_store import BoardStore
from board_model import BoardModel
from media_service import MediaService
from media_store import MediaStore
from media_library_server import create_server
import board_candidate as gui
from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def png(size=(64, 48), colour='blue'):
    stream = io.BytesIO()
    Image.new('RGB', size, colour).save(stream, 'PNG')
    return stream.getvalue()


def build_dummy_library(root: Path) -> MediaStore:
    store = MediaStore(root)
    first = store.import_bytes(png((80, 60), 'navy'), 'Cycle diagram', tags=['water', 'science'],
                               source={'attribution': 'School fixture', 'licence': 'CC0'})
    second = store.add_generated(png((80, 60), 'teal'), 'Cycle diagram labelled',
                                 asset_id=first['asset_id'], parent_version_id=first['version_id'],
                                 source={'attribution': 'School fixture', 'licence': 'CC BY 4.0'})
    store.set_canonical(first['asset_id'], second['version_id'])
    store.import_bytes(png((40, 40), 'gold'), 'Sun icon', tags=['weather'])
    damaged = store.import_bytes(png((32, 32), 'red'), 'Damaged blob', tags=['broken'])
    store.blob_path(damaged['sha256']).write_bytes(b'not-an-image')
    missing = store.import_bytes(png((32, 32), 'purple'), 'Missing blob', tags=['broken'])
    store.blob_path(missing['sha256']).unlink()
    return store


def test_library_search_version_choice_insert_save_and_reopen_without_source(app, tmp_path):
    library = build_dummy_library(tmp_path / 'library')
    saved = SavedImageLibrary(library.root)
    matches = saved.assets('cycle')
    assert len(matches) == 1
    versions = saved.versions(matches[0]['asset_id'])
    assert any(row['version_id'] == matches[0]['canonical_version_id'] for row in versions)
    labelled = next(row for row in versions if 'labelled' in row['title'].casefold())
    assert labelled['source']['licence'] == 'CC BY 4.0'

    damaged = saved.assets('damaged')[0]
    with pytest.raises(ValueError, match='damaged|safe|complete'):
        saved.prepare(saved.versions(damaged['asset_id'])[0])
    missing = saved.assets('missing')[0]
    with pytest.raises(ValueError, match='unavailable'):
        saved.prepare(saved.versions(missing['asset_id'])[0])

    lesson = tmp_path / 'lesson'
    store = BoardStore(lesson)
    resolver = gui.image_resolver(MediaStore(lesson / 'media'))
    window = gui.BoardCandidate(BoardSession(BoardModel(), store=store, image_resolver=resolver),
                                store=store, resolver=resolver)
    try:
        picker = ImagePicker(window, library_root=library.root, decoder=gui.decode_image)
        picker.search.setText('cycle')
        assert picker.assets
        picker.asset_list.setCurrentRow(0)
        picker.version_list.setCurrentRow(next(i for i, row in enumerate(picker.records)
                                              if row['version_id'] == labelled['version_id']))
        assert picker.prepared is not None
        assert window.insert_prepared_image(picker.prepared)
        picker.deleteLater()
        inserted = next(obj for obj in gui.page_from(window.session.teacher_view())['objects']
                        if obj['type'] == 'image')
        assert inserted['image_ref']['version_id'] == labelled['version_id']
        assert window.save_now()
        source_bytes = labelled['sha256']
        for path in library.root.rglob('*'):
            if path.is_file():
                path.unlink()
        window.reopen()
        restored = next(obj for obj in gui.page_from(window.session.teacher_view())['objects']
                        if obj['type'] == 'image')
        assert restored['image_ref']['version_id'] == labelled['version_id']
        data = window.session.resolve_image(restored['image_ref'])
        assert hashlib.sha256(data).hexdigest() == restored['image_ref']['sha256'] == source_bytes
        pupil_pixmaps = [item for item in window.pupil_canvas.scene().items()
                         if isinstance(item, QGraphicsPixmapItem)]
        assert pupil_pixmaps and not pupil_pixmaps[0].pixmap().isNull()
    finally:
        window.save_timer.stop(); window.property_timer.stop(); window.group_timer.stop()
        window.session.close(); window.pupil.hide(); window.hide(); window.deleteLater()
        app.processEvents()


def test_media_server_serves_the_dummy_library_without_provider_calls(tmp_path):
    library = build_dummy_library(tmp_path / 'library')
    saved = SavedImageLibrary(library.root)
    labelled = next(row for row in saved.versions(saved.assets('cycle')[0]['asset_id'])
                    if 'labelled' in row['title'].casefold())
    server = create_server(host='127.0.0.1', port=0, token='dummy-library-token',
                           data_dir=tmp_path / 'server-data', budget_limit_cents=100)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        import urllib.request
        host, port = server.server_address[:2]
        request = urllib.request.Request(
            f'http://{host}:{port}/health',
            headers={'Authorization': 'Bearer dummy-library-token', 'Connection': 'close'})
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 200
        blob = library.blob_path(labelled['sha256']).read_bytes()
        assert hashlib.sha256(blob).hexdigest() == labelled['sha256']
        assert Image.open(io.BytesIO(blob)).size == (80, 60)
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)


def test_missing_provider_keys_fail_cleanly_and_do_not_spend(tmp_path):
    config = {'LOCAL_ONLY': '0', 'IMAGE_PROVIDER': 'gemini', 'IMAGE_GENERATION_ENABLED': '1',
              'GOOGLE_IMAGE_API_KEY': '', 'GOOGLE_IMAGE_SIZE': '1K',
              'GOOGLE_IMAGE_ESTIMATE_1K_AUD_CENTS': '24', 'MEDIA_SYNC_ENABLED': '1',
              'MEDIA_SERVER_URL': 'https://private.invalid', 'MEDIA_SERVER_TOKEN': 'synthetic-token'}
    text = board_image_readiness(config)
    assert 'Google image API key' in text
    assert board_image_issues(config)
    sync = Mock()
    service = MediaService(MediaStore(tmp_path / 'media'), config, sync)
    job = service.prepare_generation('Do not call a real provider')
    with pytest.raises(ValueError, match='key|Google|credential|API'):
        service.generate(job['job_id'])
    sync.reserve_budget.assert_not_called()
    sync.commit_budget.assert_not_called()
    stored = service.store.get_job(job['job_id'])
    assert stored['provider_dispatched'] is not True
