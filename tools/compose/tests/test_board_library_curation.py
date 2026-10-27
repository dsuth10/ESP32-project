"""Curation survives source replay and portable lessons without rebinding names."""
import io
from pathlib import Path
import sys

import pytest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_export import export_lesson, import_lesson
from board_library import BoardResourceLibrary
from board_model import BoardModel
from board_resources import ResourceCatalogue
from media_store import MediaStore


def saved_image(library):
    stream = io.BytesIO()
    Image.new('RGB', (48, 32), 'steelblue').save(stream, 'PNG')
    version = library.media.import_bytes(stream.getvalue(), 'Original water diagram', tags=['original'])
    library._index(version, library.media.root, approved=True)
    return version


def test_corrections_and_pinned_name_survive_reindex_retain_and_restart(tmp_path):
    library = BoardResourceLibrary(tmp_path / 'library')
    version = saved_image(library)
    catalogue = library.catalogue
    catalogue.update_metadata(version['version_id'], title='Corrected water cycle',
        description='Labelled diagram for our class', tags=['evaporation'], topics=['Science'], year_levels=['5'])
    catalogue.remember_name('our usual water-cycle diagram', version['version_id'])
    repeated = library._index(version, library.media.root, approved=True)
    assert repeated['title'] == 'Corrected water cycle'
    assert repeated['source_title'] == 'Original water diagram'
    lesson_media = MediaStore(tmp_path / 'lesson-media')
    chosen = library.select(repeated, lesson_media)
    assert chosen['title'] == 'Corrected water cycle'
    reopened = BoardResourceLibrary(library.root)
    reopened.catalogue.rebuild_index()
    assert reopened.automatic_match('OUR USUAL WATER-CYCLE DIAGRAM')['version_id'] == version['version_id']
    assert reopened.search_resources('evaporation', topics=['Science'], year_levels=['5'])[0]['title'] == repeated['title']
    reopened.catalogue.set_review_state(version['asset_id'], version['version_id'], 'rejected')
    assert reopened.automatic_match('our usual water-cycle diagram') is None


def test_portable_corrections_preserve_source_identity_and_local_choices(tmp_path):
    source = BoardResourceLibrary(tmp_path / 'source')
    version = saved_image(source)
    source.catalogue.update_metadata(version['version_id'], title='Teacher corrected diagram',
        description='Science sequence', tags=['condensation'], topics=['Water cycle'], year_levels=['5'])
    source.catalogue.remember_name('our usual diagram', version['version_id'])
    package = export_lesson(BoardModel(), tmp_path / 'lesson.tboard', media_store=source.media,
        catalogue=source.catalogue, catalogue_refs=[version['version_id']])
    imported_root = tmp_path / 'imported'
    import_lesson(package, imported_root)
    imported = ResourceCatalogue(imported_root / 'catalogue', media_store=MediaStore(imported_root / 'media'))
    item = imported.get_resource_by_version(version['version_id'])
    assert item['title'] == 'Teacher corrected diagram'
    assert item['source_title'] == 'Original water diagram'
    assert item['year_levels'] == ['5']
    assert item['remembered_names'] == []
    target = BoardResourceLibrary(tmp_path / 'target')
    target.import_catalogue(imported.path, imported_root / 'media')
    item = target.catalogue.get_resource_by_version(version['version_id'])
    assert item['title'] == 'Teacher corrected diagram'
    # Importing again must retain receiving teacher corrections and decisions.
    target.catalogue.update_metadata(version['version_id'], title='My receiving correction')
    target.catalogue.remember_name('my diagram', version['version_id'])
    target.import_catalogue(imported.path, imported_root / 'media')
    assert target.catalogue.get_resource_by_version(version['version_id'])['title'] == 'My receiving correction'
    assert target.automatic_match('my diagram')['version_id'] == version['version_id']
    # Its original media can be re-indexed after import without metadata conflicts.
    assert target._index(version, source.media.root)['source_tags'] == ['original']


def test_portable_explicit_empty_facets_do_not_restore_source_values(tmp_path):
    media = MediaStore(tmp_path / 'media')
    source = ResourceCatalogue(tmp_path / 'catalogue')
    record = source.save_resource('document', 'Source worksheet',
        metadata={'topics': ['Science'], 'year_levels': ['5']})
    source.update_metadata(record['version_id'], topics=[], year_levels=[])
    package = export_lesson(BoardModel(), tmp_path / 'cleared.tboard', media_store=media,
        catalogue=source, catalogue_refs=[record['version_id']])
    destination = tmp_path / 'restored'
    import_lesson(package, destination)
    restored = ResourceCatalogue(destination / 'catalogue')
    actual = restored.get_resource_by_version(record['version_id'])
    assert actual['topics'] == actual['year_levels'] == []
    assert actual['metadata'] == record['metadata']


def test_export_rejects_private_correction_instead_of_writing_unimportable_package(tmp_path):
    source = ResourceCatalogue(tmp_path / 'catalogue')
    record = source.save_resource('document', 'Worksheet')
    source.update_metadata(record['version_id'], description='C:\\private\\worksheet.docx')
    with pytest.raises(ValueError, match='Teacher resource metadata contains private fields'):
        export_lesson(BoardModel(), tmp_path / 'private.tboard', media_store=MediaStore(tmp_path / 'media'),
            catalogue=source, catalogue_refs=[record['version_id']])


def test_search_exact_version_identity_is_case_insensitive(tmp_path):
    source = ResourceCatalogue(tmp_path / 'catalogue')
    record = source.save_resource('document', 'Identity search')
    found = source.search(record['version_id'].upper())
    assert [item['version_id'] for item in found] == [record['version_id']]
    assert found[0]['match_reasons'][0] == 'Exact resource identity'
