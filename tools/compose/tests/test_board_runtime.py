"""Local-only Board resource/runtime integration with synthetic provider fixtures."""
from __future__ import annotations

from concurrent.futures import Future
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import uuid

import pytest
from PIL import Image

COMPOSE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COMPOSE))

from board_agent import BoardAgentController, result_envelope
from board_library import BoardResourceLibrary
from board_model import new_object
from board_resource_policy import BoardRequestAcquisition
from board_runtime import BoardResourcePreparer, PrimaryBoardComposer, create_resource_service
from board_session import BoardSession
from board_images import SavedImageLibrary
from image_provider_config import image_snapshot
from media_service import MediaService
from media_providers import ProviderFailure


def png_bytes(colour='#78BCE8'):
    stream = io.BytesIO()
    Image.new('RGB', (96, 64), colour).save(stream, 'PNG')
    return stream.getvalue()


def context(instruction, *, request_id=None, allow_illustrative=False, local_only=False):
    return {'request_id': request_id or str(uuid.uuid4()), 'context': json.dumps({
        'instruction': instruction, 'selected_images': [], 'local_only': local_only,
        'effective_context': {'allow_illustrative_data': allow_illustrative}})}


def planned(kind, source=None, query='water cycle'):
    return lambda task, content: json.dumps({'query': query, 'kind': kind, 'source': source})


class ManualExecutor:
    def __init__(self): self.pending = []
    def submit(self, fn, *args):
        future = Future(); self.pending.append((future, fn, args)); return future
    def run(self):
        future, fn, args = self.pending.pop(0)
        if future.set_running_or_notify_cancel():
            try: future.set_result(fn(*args))
            except BaseException as exc: future.set_exception(exc)


class PageResponse:
    def __init__(self, body, status=200): self.body, self.status_code = body, status
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def iter_content(self, chunk_size): yield self.body


class FakeRetriever:
    def __init__(self, candidates, page):
        self.candidates, self.page = candidates, page
        self.download_calls = []
        self.session = self
    def get(self, url, **kwargs):
        assert url.startswith('https://commons.wikimedia.org/wiki/')
        assert kwargs['allow_redirects'] is False
        return PageResponse(self.page)
    def search_web(self, query): return self.candidates
    def download(self, candidate, *, rights_acknowledged=False):
        self.download_calls.append((candidate, rights_acknowledged))
        return png_bytes()


class FakeMediaService:
    def __init__(self, candidates=(), page=b'', config=None):
        self.retriever = FakeRetriever(candidates, page)
        self.config = config or {}
        self.search_calls = []
    def search_web(self, query):
        self.search_calls.append(query)
        return self.retriever.candidates


def commons_candidate():
    def value(text): return {'value': text}
    return {'title': 'File: River cycle.png',
        'download_url': 'https://upload.wikimedia.org/wikipedia/commons/a/a1/river.png',
        'description_url': 'https://commons.wikimedia.org/wiki/File:River_cycle.png',
        'rights_metadata': {'LicenseShortName': value('CC BY 4.0'),
            'LicenseUrl': value('https://creativecommons.org/licenses/by/4.0/'),
            'Artist': value('River Teacher'), 'Attribution': value('River Teacher / Commons'),
            'Credit': value('River Teacher'), 'ObjectName': value('River cycle'),
            'Copyrighted': value('true'), 'Restrictions': value(''),
            'UsageTerms': value('CC BY 4.0')},
        'source': {'url': 'https://commons.wikimedia.org/wiki/File:River_cycle.png',
                   'creator': 'River Teacher', 'licence': 'CC BY 4.0',
                   'licence_url': 'https://creativecommons.org/licenses/by/4.0/',
                   'attribution': 'River Teacher / Commons'}}


def test_runtime_import_and_local_service_factory_do_not_load_http_stack(tmp_path):
    script = r'''
import builtins, sys
class BlockRequests:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "requests" or fullname.startswith("requests."):
            raise RuntimeError("optional requests import attempted")
sys.meta_path.insert(0, BlockRequests())
import board_runtime
assert board_runtime.truthy("yes")
assert board_runtime.create_resource_service(None, {"LOCAL_ONLY": "1"}) is None
assert "assistant_service" not in sys.modules
assert "media_service" not in sys.modules
'''
    result = subprocess.run([sys.executable, '-c', script], cwd=COMPOSE,
        env={**__import__('os').environ, 'PYTHONPATH': str(COMPOSE)},
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert PrimaryBoardComposer({'LOCAL_ONLY': 'true'}).remote is False


def test_index_source_resumes_and_auto_selects_only_exact_approved_verified_bytes(tmp_path):
    source_media = __import__('media_store').MediaStore(tmp_path / 'source')
    first = source_media.import_bytes(png_bytes(), 'Canonical river cycle', tags=['Science'] + [f'tag-{i}' for i in range(45)])
    source_media.set_canonical(first['asset_id'], first['version_id'])
    second = source_media.import_bytes(png_bytes('#35A56D'), 'Draft stream diagram')
    library = BoardResourceLibrary(tmp_path / 'board')
    source = SavedImageLibrary(source_media.root)
    first_batch = library.index_source(source_media.root, batch_size=1)
    assert first_batch == {'indexed': 1, 'more': True}
    assert library.automatic_match('Canonical river cycle')['version_id'] == first['version_id']
    second_batch = library.index_source(source_media.root, batch_size=1)
    assert second_batch == {'indexed': 1, 'more': True}
    assert library.index_source(source_media.root, batch_size=1) == {'indexed': 0, 'more': False}
    record = library.catalogue.get_resource_by_version(first['version_id'])
    assert record['tags'] == first['version_tags']
    assert record['availability'] == 'metadata_only'
    assert str(source.root) not in json.dumps(record)
    library.catalogue.set_review_state(first['asset_id'], first['version_id'], 'rejected', 'Teacher removed it.')
    with __import__('sqlite3').connect(library.registry) as db:
        db.execute('DELETE FROM source_version WHERE version_id=?', (first['version_id'],))
    first_source_record = next(item for item in source.versions(first['asset_id'])
                               if item['version_id'] == first['version_id'])
    library._index(first_source_record, source.root, approved=True)
    assert library.catalogue.get_resource_by_version(first['version_id'])['review_state'] == 'rejected'
    assert library.automatic_match('Canonical river cycle') is None
    assert library.automatic_match('Draft stream diagram') is None


def test_source_metadata_backfill_does_not_open_or_decode_blobs_until_selection(tmp_path, monkeypatch):
    source_media = __import__('media_store').MediaStore(tmp_path / 'source')
    copied = source_media.import_bytes(png_bytes(), 'River source')
    source_media.set_canonical(copied['asset_id'], copied['version_id'])
    original_prepare = SavedImageLibrary.prepare
    monkeypatch.setattr(SavedImageLibrary, 'prepare',
        lambda self, version: (_ for _ in ()).throw(AssertionError('blob opened during indexing')))
    library = BoardResourceLibrary(tmp_path / 'board')
    result = library.index_source(source_media.root)
    record = library.catalogue.get_resource_by_version(copied['version_id'])
    assert result['indexed'] == 1
    assert record['availability'] == 'metadata_only'
    monkeypatch.setattr(SavedImageLibrary, 'prepare', original_prepare)
    assert library.automatic_match('River source')['version_id'] == copied['version_id']


def test_explicit_commons_overrides_library_and_keeps_full_source_credit(tmp_path):
    library = BoardResourceLibrary(tmp_path / 'board')
    candidate = commons_candidate()
    media = FakeMediaService([candidate], b'<html><div class="licensetpl"><span class="licensetpl_link">https://creativecommons.org/licenses/by/4.0/</span></div><footer><a href="https://creativecommons.org/licenses/by-sa/4.0/">community</a></footer></html>')
    preparer = BoardResourcePreparer(library, __import__('media_store').MediaStore(tmp_path / 'lesson'), {},
        media_service=media, planner=planned('photo', 'commons', 'river cycle'))
    prepared = context('Use a photo from Wikimedia Commons for the river cycle.')
    # A saved exact match exists but an explicit source choice takes precedence.
    saved = library.media.import_bytes(png_bytes('#C88A41'), 'river cycle', source={'provider': 'test'})
    library._index(saved, library.media.root, approved=True)
    acquired = preparer(prepared, lambda *args: None, lambda: False)
    assert media.search_calls == ['river cycle']
    assert len(media.retriever.download_calls) == 1
    assert media.retriever.download_calls[0][1] is True
    assert 'CC BY 4.0' in acquired[0]['credit'] and 'creativecommons.org/licenses/by/4.0/' in acquired[0]['credit']
    record = library.catalogue.get_resource_by_version(acquired[0]['image_ref']['version_id'])
    assert record['provenance']['file_url'] == candidate['download_url']
    assert record['provenance']['licence_url'] == 'https://creativecommons.org/licenses/by/4.0/'
    assert record['provenance']['changes'] == 'Scaled to fit; no crop'
    assert record['provenance']['acquired_at'].endswith('Z')
    assert record['title'] == 'River cycle'  # The chosen exact Commons file title is retained.


def test_unsupported_commons_page_blocks_download_and_local_only_blocks_search(tmp_path):
    library = BoardResourceLibrary(tmp_path / 'board')
    candidate = commons_candidate()
    media = FakeMediaService([candidate], b'<html><div class="licensetpl"><span class="licensetpl_link">https://creativecommons.org/licenses/by-nc/4.0/</span></div><footer>CC BY 4.0</footer></html>')
    preparer = BoardResourcePreparer(library, __import__('media_store').MediaStore(tmp_path / 'lesson'), {},
        media_service=media, planner=planned('photo', 'commons'))
    with pytest.raises(Exception, match='No supported reusable photo'):
        preparer(context('Use a photo from Wikimedia Commons'), lambda *args: None, lambda: False)
    assert media.retriever.download_calls == []
    local = BoardResourcePreparer(library, __import__('media_store').MediaStore(tmp_path / 'local-lesson'),
        {'LOCAL_ONLY': '1'}, media_service=media, planner=planned('photo', 'commons'))
    with pytest.raises(Exception, match='local-only'):
        local(context('Use a photo from Wikimedia Commons', local_only=True), lambda *args: None, lambda: False)
    assert media.search_calls == ['water cycle']


def test_ordinary_photo_uses_verified_saved_library_first(tmp_path):
    source = __import__('media_store').MediaStore(tmp_path / 'source')
    image = source.import_bytes(png_bytes(), 'water cycle')
    source.set_canonical(image['asset_id'], image['version_id'])
    library = BoardResourceLibrary(tmp_path / 'board')
    library.index_source(source.root, batch_size=10)
    media = FakeMediaService([commons_candidate()], b'')
    preparer = BoardResourcePreparer(library, __import__('media_store').MediaStore(tmp_path / 'lesson'), {},
        media_service=media, planner=planned('photo', None, 'water cycle'))
    result = preparer(context('Show our water cycle picture.'), lambda *args: None, lambda: False)
    assert result[0]['image_ref']['version_id'] == image['version_id']
    assert media.search_calls == []


def test_chart_creation_saves_related_data_spec_and_rendered_image_idempotently(tmp_path):
    library = BoardResourceLibrary(tmp_path / 'board')
    dataset = {'schema': 1, 'title': 'Monthly rainfall', 'x': {'label': 'Month', 'unit': 'month'},
        'y': {'label': 'Rainfall', 'unit': 'mm'},
        'points': [{'label': 'January', 'value': 80}, {'label': 'February', 'value': None},
                   {'label': 'March', 'value': 120}],
        'provenance': {'kind': 'published', 'publisher': 'Australian Example Bureau',
            'source_url': 'https://example.org/rain', 'date': '2026-10-25', 'licence': 'CC BY 4.0',
            'coverage': 'Monthly, 2025'}, 'illustrative': False}
    preparer = BoardResourcePreparer(library, __import__('media_store').MediaStore(tmp_path / 'lesson'), {},
        planner=planned('chart', None, 'monthly rainfall'))
    preparer.dataset = dataset
    first = preparer(context('Make a monthly rainfall chart.'), lambda *args: None, lambda: False)[0]
    second = preparer(context('Make a monthly rainfall chart.'), lambda *args: None, lambda: False)[0]
    assert first['image_ref'] == second['image_ref']
    chart = library.catalogue.search('Monthly rainfall', resource_types=['dataset'])[0]
    image = library.catalogue.get_resource_by_version(first['image_ref']['version_id'])
    relations = library.catalogue.relationships(image['resource_id'], image['version_id'])
    assert any(value['relation'] == 'rendered_from' for value in relations)
    rendered = next(value for value in relations if value['relation'] == 'rendered_from')
    chart_record = library.catalogue.get_resource_by_version(rendered['target_version_id'])
    derived = library.catalogue.relationships(chart_record['resource_id'], chart_record['version_id'])
    assert any(value['relation'] == 'derived_from' and value['target_version_id'] == chart['version_id'] for value in derived)
    assert chart['metadata']['provenance']['publisher'] == 'Australian Example Bureau'
    assert chart['metadata']['points'][1]['value'] is None


def test_explicit_permission_creates_pupil_labelled_illustrative_chart_only(tmp_path):
    library = BoardResourceLibrary(tmp_path / 'board')
    preparer = BoardResourcePreparer(library, __import__('media_store').MediaStore(tmp_path / 'lesson'), {},
        planner=planned('chart', None, 'water-cycle rainfall'))
    image = preparer(context('Make an illustrative water-cycle rainfall chart.', allow_illustrative=True),
                     lambda *args: None, lambda: False)[0]
    record = library.catalogue.get_resource_by_version(image['image_ref']['version_id'])
    assert record['review_state'] == 'draft'
    assert record['provenance']['illustrative'] is True
    assert record['provenance']['dataset_sha256']
    dataset = library.catalogue.search('water-cycle rainfall', resource_types=['dataset'])[0]
    assert dataset['metadata']['illustrative'] is True


def test_existing_selected_image_does_not_suppress_a_new_chart_request(tmp_path):
    library = BoardResourceLibrary(tmp_path / 'board')
    preparer = BoardResourcePreparer(library, __import__('media_store').MediaStore(tmp_path / 'lesson'), {},
        planner=planned('chart', None, 'water-cycle rainfall'))
    preparer.dataset = {'schema': 1, 'title': 'Rainfall', 'x': {'label': 'Month', 'unit': 'month'},
        'y': {'label': 'Rainfall', 'unit': 'mm'},
        'points': [{'label': 'January', 'value': 80}, {'label': 'February', 'value': 90}],
        'provenance': {'kind': 'published', 'publisher': 'Example Bureau', 'source_url': 'https://example.org/data',
            'date': '2026-10-25', 'licence': 'CC BY 4.0', 'coverage': 'Monthly'}, 'illustrative': False}
    request = context('Add a new monthly rainfall chart.', request_id=str(uuid.uuid4()))
    body = json.loads(request['context'])
    body['selected_images'] = [{'image_ref': {'asset_id': 'existing-asset', 'version_id': 'existing-version',
        'sha256': '0' * 64}, 'title': 'Existing page image'}]
    request['context'] = json.dumps(body)
    selected = preparer(request, lambda *args: None, lambda: False)
    assert len(selected) == 1
    assert selected[0]['visual_kind'] == 'chart'
    assert selected[0]['title'] == 'Rainfall'


def test_generated_image_requires_completed_teacher_preview_before_board_publication(tmp_path):
    library = BoardResourceLibrary(tmp_path / 'board')
    lesson_media = __import__('media_store').MediaStore(tmp_path / 'lesson')
    media = google_service(library.media, FakeImageProvider())
    preparer = BoardResourcePreparer(library, lesson_media, media.config, media_service=media,
        planner=planned('illustration', 'google', 'water cycle'))
    session = BoardSession(image_resolver=lambda ref: lesson_media.blob_path(ref['sha256']).read_bytes())
    def composer(prepared, report, cancelled):
        selected = json.loads(prepared['context'])['selected_images'][0]
        return result_envelope(prepared, template={'name': 'title_image', 'title': 'Water cycle',
            'body': 'Water evaporates, condenses and falls as rain.', 'image_ref': selected['image_ref']})
    composer.remote = False
    executor = ManualExecutor()
    controller = BoardAgentController(session, composer=composer, resource_preparer=preparer, executor=executor)
    prepared = controller.prepare('Use Google to draw a water cycle illustration.')
    request_id = controller.start(prepared)
    executor.run()
    preview = controller.poll(request_id)
    assert preview['status'] == 'awaiting_confirmation'
    assert 'first_generated_image_use' in preview['confirmation_reasons']
    assert 'Water cycle' in json.dumps(controller.preview(request_id))
    assert session.pupil_view()['document']['pages'][0]['objects'] == []
    result = controller.confirm(request_id, preview['proposal_digest'])
    assert result['status'] == 'applied'
    assert session.pupil_view()['document']['pages'][0]['objects']
    controller.close()


class Ledger:
    def __init__(self): self.reservations = []
    def reserve_budget(self, job_id, amount): self.reservations.append((job_id, amount))
    def mark_budget_uncertain(self, job_id): pass
    def commit_budget(self, job_id, amount): pass


class FakeImageProvider:
    def __init__(self, *, failure=None): self.calls = []; self.failure = failure
    def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.failure: raise self.failure
        return {'data': png_bytes(), 'mime': 'image/png', 'source': {'provider': 'gemini', 'model': 'gemini-nano-banana-2.1'},
            'usage': {}, 'request_id': 'synthetic', 'receipt': {'provider': 'gemini', 'outcome': 'image_received'}}
    def close(self): pass


def google_service(media_store, provider):
    config = {'IMAGE_PROVIDER': 'gemini', 'GOOGLE_IMAGE_MODEL': 'gemini-nano-banana-2.1',
        'GOOGLE_IMAGE_SIZE': '1K', 'GOOGLE_IMAGE_ASPECT_RATIO': '1:1', 'GOOGLE_IMAGE_THINKING': 'medium',
        'GOOGLE_IMAGE_ESTIMATE_1K_AUD_CENTS': '50', 'IMAGE_GENERATION_ENABLED': '1', 'LOCAL_ONLY': '0'}
    return MediaService(media_store, config, Ledger(), provider=provider)


@pytest.mark.parametrize(('override', 'with_provider', 'with_ledger', 'message'), [
    ({'IMAGE_PROVIDER': 'openai'}, True, True, 'Select Google Gemini'),
    ({'IMAGE_GENERATION_ENABLED': '0'}, True, True, 'Enable paid image requests'),
    ({}, False, True, 'Google image API key'),
    ({'GOOGLE_IMAGE_MODEL': 'unsupported'}, True, True, 'supported Google model'),
    ({'GOOGLE_IMAGE_SIZE': '2K'}, True, True, 'Choose 1K'),
    ({'GOOGLE_IMAGE_ESTIMATE_1K_AUD_CENTS': '0'}, True, True, '1–50 AUD cents'),
    ({'GOOGLE_IMAGE_ESTIMATE_1K_AUD_CENTS': '51'}, True, True, '1–50 AUD cents'),
    ({}, True, False, 'shared budget service'),
])
def test_board_generation_setup_rejected_before_job_creation(tmp_path, override, with_provider, with_ledger, message):
    library = BoardResourceLibrary(tmp_path / 'board')
    provider = FakeImageProvider()
    media = google_service(library.media, provider)
    media.config.update(override)
    if not with_provider:
        media.provider = None
    if not with_ledger:
        media.sync = None
    preparer = BoardResourcePreparer(library, __import__('media_store').MediaStore(tmp_path / 'lesson'),
        media.config, media_service=media, planner=planned('illustration', None, 'dog'))
    with pytest.raises(Exception, match=message):
        preparer(context('Draw a dog'), lambda *args: None, lambda: False)
    assert media.store.list_jobs() == []
    assert provider.calls == []
    if media.sync is not None:
        assert media.sync.reservations == []


def test_local_dog_image_error_does_not_ask_for_chart_data(tmp_path):
    library = BoardResourceLibrary(tmp_path / 'board')
    preparer = BoardResourcePreparer(library, __import__('media_store').MediaStore(tmp_path / 'lesson'),
        {'LOCAL_ONLY': '1'}, planner=planned('illustration', None, 'dog'))
    with pytest.raises(Exception) as error:
        preparer(context('Add an image of a dog'), lambda *args: None, lambda: False)
    assert 'local-only' in str(error.value)
    assert 'Board settings' in str(error.value)
    assert 'chart' not in str(error.value)
    assert library.media.list_jobs() == []


def test_chart_without_dataset_still_asks_for_units_source_and_date(tmp_path):
    library = BoardResourceLibrary(tmp_path / 'board')
    preparer = BoardResourcePreparer(library, __import__('media_store').MediaStore(tmp_path / 'lesson'),
        {'LOCAL_ONLY': '1'}, planner=planned('chart', None, 'rainfall'))
    with pytest.raises(Exception, match='chart dataset with units, source and date'):
        preparer(context('Add a rainfall chart'), lambda *args: None, lambda: False)


def test_lazy_media_close_never_constructs_service_and_closes_existing_sessions(tmp_path, monkeypatch):
    from unittest.mock import Mock
    library = BoardResourceLibrary(tmp_path / 'board')
    lazy = create_resource_service(library, {'LOCAL_ONLY': '0'})
    monkeypatch.setattr(lazy, '_get', lambda: pytest.fail('Cleanup constructed a service'))
    lazy.close()
    service = Mock()
    lazy._service = service
    lazy.close()
    service.close.assert_called_once_with()
    service.sync.close.assert_called_once_with()
    assert lazy._service is None


def test_one_google_attempt_is_reserved_once_saved_and_marked_for_first_use_preview(tmp_path):
    library = BoardResourceLibrary(tmp_path / 'board')
    lesson_media = __import__('media_store').MediaStore(tmp_path / 'lesson')
    provider, media = FakeImageProvider(), None
    media = google_service(library.media, provider)
    preparer = BoardResourcePreparer(library, lesson_media, media.config, media_service=media,
        planner=planned('illustration', 'google', 'water cycle diagram'))
    prepared = context('Use Google to draw an original water cycle illustration.')
    image = preparer(prepared, lambda *args: None, lambda: False)[0]
    assert image['generated_unreviewed'] is True
    assert len(provider.calls) == len(media.sync.reservations) == 1
    assert media.sync.reservations[0][1] == 50
    # Same durable Board identity cannot allocate a replacement provider job.
    with pytest.raises(ValueError, match='different provider job'):
        preparer(prepared, lambda *args: None, lambda: False)
    assert len(provider.calls) == 1


def test_cancel_before_paid_dispatch_and_uncertain_dispatch_never_retry(tmp_path):
    library = BoardResourceLibrary(tmp_path / 'board')
    media = google_service(library.media, FakeImageProvider())
    preparer = BoardResourcePreparer(library, __import__('media_store').MediaStore(tmp_path / 'lesson'),
        media.config, media_service=media, planner=planned('illustration'))
    calls = iter([False, False, True])
    with pytest.raises(Exception, match='Cancelled before the Google attempt'):
        preparer(context('Draw a water cycle'), lambda *args: None, lambda: next(calls))
    assert not media.sync.reservations
    assert len(media.store.list_jobs()) == 1 and media.store.list_jobs()[0]['phase'] == 'awaiting_user'

    failed_library = BoardResourceLibrary(tmp_path / 'failed')
    provider = FakeImageProvider(failure=TimeoutError('uncertain'))
    failed_media = google_service(failed_library.media, provider)
    failed = BoardResourcePreparer(failed_library, __import__('media_store').MediaStore(tmp_path / 'failed-lesson'),
        failed_media.config, media_service=failed_media, planner=planned('illustration'))
    request = context('Draw a water cycle', request_id=str(uuid.uuid4()))
    with pytest.raises(ProviderFailure): failed(request, lambda *args: None, lambda: False)
    with pytest.raises(ValueError): failed(request, lambda *args: None, lambda: False)
    assert len(provider.calls) == 1
    assert len(failed_media.sync.reservations) == 1


def test_composer_local_only_and_source_override_detection_are_bounded():
    assert PrimaryBoardComposer({'LOCAL_ONLY': 'yes'}).remote is False
    assert BoardResourcePreparer._confirmed_source('Find a photo', 'commons') is None
    assert BoardResourcePreparer._confirmed_source('Use Wikimedia Commons', 'commons') == 'commons'
    assert BoardResourcePreparer._confirmed_source('Make it look like Google imagery', 'google') == 'google'
    assert BoardResourcePreparer._confirmed_source('Find from our saved library', 'library') == 'library'


def test_portable_catalogue_import_preserves_exact_versions_relations_review_and_private_roots(tmp_path):
    source = BoardResourceLibrary(tmp_path / 'package')
    image_version = source.media.import_bytes(png_bytes(), 'Portable approved picture', tags=['Science', 'water cycle'])
    image_record = source._index(image_version, source.media.root, approved=True)
    data = source.catalogue.save_resource('dataset', 'Portable dataset', metadata={'unit': 'mm', 'rows': 3},
        provenance={'publisher': 'Example Bureau'}, content_hash='d' * 64, state='approved')
    chart = source.catalogue.save_resource('chart', 'Portable chart', metadata={'kind': 'bar'},
        provenance={'source': 'Portable dataset'}, content_hash='e' * 64, state='approved')
    source.catalogue.add_relationship(chart['version_id'], 'derived_from', data['version_id'], {'step': 'validated totals'})
    source.catalogue.add_relationship(image_record['version_id'], 'rendered_from', chart['version_id'])

    target = BoardResourceLibrary(tmp_path / 'target')
    result = target.import_catalogue(source.catalogue.path, source.media.root)
    assert result == {'resources': 3, 'relationships': 2}
    imported_image = target.catalogue.get_resource_by_version(image_record['version_id'])
    assert imported_image['image_ref'] == image_record['image_ref']
    assert imported_image['tags'] == image_record['tags']
    assert target.automatic_match('Portable approved picture')['version_id'] == image_record['version_id']
    assert not target.media.blob_path(image_version['sha256']).exists()  # Source bytes stay in read-only package.
    assert str(source.media.root) not in json.dumps(imported_image)
    assert target.catalogue.get_resource_by_version(data['version_id'])['metadata'] == data['metadata']
    assert len(target.catalogue.relationships(chart['resource_id'], chart['version_id'])) == 2
    target.catalogue.set_review_state(image_record['resource_id'], image_record['version_id'], 'rejected')
    assert target.import_catalogue(source.catalogue.path, source.media.root) == result
    assert target.catalogue.get_resource_by_version(image_record['version_id'])['review_state'] == 'rejected'


def test_portable_catalogue_images_require_paired_source_and_paths_are_not_imported(tmp_path):
    source = BoardResourceLibrary(tmp_path / 'package')
    image = source.media.import_bytes(png_bytes(), 'Source picture')
    source._index(image, source.media.root, approved=True)
    target = BoardResourceLibrary(tmp_path / 'target')
    with pytest.raises(ValueError, match='paired media-library folder'):
        target.import_catalogue(source.catalogue.path)
    # A path-bearing manifest is rejected before any resource is copied.
    source.catalogue.save_resource('dataset', 'Private path field', metadata={'source_path': 'C:/private/library'})
    with pytest.raises(ValueError, match='local source paths'):
        target.import_catalogue(source.catalogue.path, source.media.root)
    assert target.catalogue.search('Source picture', resource_types=['image']) == []


def test_retain_applied_page_is_immutable_and_links_exact_image_versions(tmp_path):
    library = BoardResourceLibrary(tmp_path / 'board')
    media = __import__('media_store').MediaStore(tmp_path / 'lesson-media')
    image = media.import_bytes(png_bytes(), 'Page figure')
    page = __import__('board_model').new_page('Saved water cycle page')
    page['objects'] = [new_object('image', x=40, y=50, width=320, height=210,
        image_ref={key: image[key] for key in ('asset_id', 'version_id', 'sha256')})]
    request_id = str(uuid.uuid4())
    record = library.retain_page(page, request_id, media_store=media)
    repeated = library.retain_page(page, request_id, media_store=media)
    assert record['version_id'] == repeated['version_id']
    assert record['metadata']['page'] == page
    relationships = library.catalogue.relationships(record['resource_id'], record['version_id'])
    assert len(relationships) == 1
    assert relationships[0]['relation'] == 'uses'
    assert relationships[0]['target_version_id'] == image['version_id']


def test_retain_page_refuses_oversized_resource_without_partial_page_record(tmp_path):
    library = BoardResourceLibrary(tmp_path / 'board')
    page = __import__('board_model').new_page('Oversized page')
    page['objects'] = [new_object('text', text='x' * 20000, x=1, y=1, width=500, height=50) for _ in range(4)]
    request_id = str(uuid.uuid4())
    with pytest.raises(ValueError, match='64 KiB'):
        library.retain_page(page, request_id)
    assert library.catalogue.search('Oversized page', resource_types=['page']) == []
