"""Metadata backfill and acquisition may index the same exact version together."""
from concurrent.futures import ThreadPoolExecutor
import io
from pathlib import Path
import sys
import threading

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_library import BoardResourceLibrary


def concurrent_index(library, version, monkeypatch, *, conflicting_title=False, separate_instances=False):
    """Force both initial reads to miss, then commit metadata before acquisition."""
    missing = threading.Barrier(2)
    metadata_saved = threading.Event()
    acquisition_library = BoardResourceLibrary(library.root) if separate_instances else library

    for catalogue in {library.catalogue, acquisition_library.catalogue}:
        get = catalogue.get_resource_by_version
        save = catalogue.save_resource

        def both_miss(version_id, _get=get):
            record = _get(version_id)
            if record is None:
                missing.wait(timeout=5)
            return record

        def metadata_first(*args, _save=save, **kwargs):
            if kwargs['availability'] == 'offline':
                assert metadata_saved.wait(timeout=5), 'Metadata fixture did not finish'
                return _save(*args, **kwargs)
            try:
                return _save(*args, **kwargs)
            finally:
                metadata_saved.set()

        monkeypatch.setattr(catalogue, 'get_resource_by_version', both_miss)
        monkeypatch.setattr(catalogue, 'save_resource', metadata_first)
    acquired = dict(version)
    if conflicting_title:
        acquired['version_title'] = 'Conflicting immutable title'
    with ThreadPoolExecutor(max_workers=2) as executor:
        metadata = executor.submit(library._index, version, library.media.root, availability='metadata_only')
        acquisition = executor.submit(acquisition_library._index, acquired, library.media.root, availability='offline')
        first = metadata.result(timeout=10)
        if conflicting_title:
            with pytest.raises(ValueError, match='immutable title, tags or provenance'):
                acquisition.result(timeout=10)
            return first, None
        return first, acquisition.result(timeout=10)


@pytest.mark.parametrize('conflicting_title', [False, True])
@pytest.mark.parametrize('separate_instances', [False, True])
def test_simultaneous_backfill_and_acquisition_preserve_exact_version_and_review(tmp_path, monkeypatch, conflicting_title, separate_instances):
    library = BoardResourceLibrary(tmp_path / 'resources')
    stream = io.BytesIO()
    Image.new('RGB', (48, 32), '#bc915f').save(stream, format='PNG')
    version = library.media.import_bytes(stream.getvalue(), 'Dog', origin='generated')
    first, acquired = concurrent_index(library, version, monkeypatch,
        conflicting_title=conflicting_title, separate_instances=separate_instances)
    assert first['availability'] == 'metadata_only'
    assert first['review_state'] == 'draft'
    if acquired is not None:
        assert acquired == first
    current = library.catalogue.get_resource_by_version(version['version_id'])
    assert current['source_title'] == 'Dog'
    assert current['review_state'] == 'draft'
    assert current['image_ref']['sha256'] == version['sha256']
