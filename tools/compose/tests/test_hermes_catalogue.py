import io
import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hermes_catalogue import MAX_ITEMS, prepare_catalogue, resolve_recommendation
from hermes_service import HermesService
from media_store import MediaStore
from compose_gui import ComposeApp
from hermes_panel import HermesPanel
from media_panel import MediaPanel


@pytest.fixture
def library(tmp_path):
    store = MediaStore(tmp_path / 'media')
    image = io.BytesIO()
    Image.new('RGB', (16, 12), 'blue').save(image, 'PNG')
    row = store.import_bytes(image.getvalue(), 'Our water cycle', tags=['science'],
                             prompt='PRIVATE_PROMPT', source={'url': 'https://private.invalid/source'})
    store.create_job('generate', 'PRIVATE_JOB_REQUEST')
    return store, row, image.getvalue()


def recommendation(row, **extra):
    return json.dumps({'version_id': row['version_id'], 'reason': 'Shows the water cycle.', **extra})


def test_catalogue_is_bounded_allowlisted_and_does_not_dispatch(library):
    store, row, image = library
    for index in range(15):
        store.import_bytes(image, f'Water cycle {index}', tags=['science'])
    selection = prepare_catalogue(store, 'Choose a water-cycle diagram', 'water cycle')
    parsed = json.loads(selection['context'])
    assert selection['count'] == len(parsed['items']) == MAX_ITEMS
    assert len(selection['context']) <= 12000
    assert 'PRIVATE_' not in selection['context']
    assert 'private.invalid' not in selection['context']
    assert str(store.root) not in selection['context']
    assert set(parsed['items'][0]) == {'asset_id', 'version_id', 'sha256', 'revision',
        'canonical_version_id', 'title', 'tags', 'width', 'height'}
    assert len(store.list_jobs()) == 1


def test_saved_version_resolves_only_from_its_selected_catalogue(library):
    store, row, _ = library
    selection = prepare_catalogue(store, 'Choose water cycle')
    resolved, reason = resolve_recommendation(store, selection['context'], recommendation(row))
    assert resolved['version_id'] == row['version_id']
    assert reason == 'Shows the water cycle.'


def test_unknown_version_and_extra_actions_are_rejected(library):
    store, row, image = library
    selection = prepare_catalogue(store, 'Choose water cycle')
    other = store.import_bytes(image, 'An unrelated new image')
    with pytest.raises(ValueError, match='outside the prepared catalogue'):
        resolve_recommendation(store, selection['context'], recommendation(other))
    with pytest.raises(ValueError, match='only a catalogue'):
        resolve_recommendation(store, selection['context'], recommendation(row, url='file:///private.png'))


def test_changed_canonical_choice_requires_fresh_preparation(library):
    store, row, _ = library
    selection = prepare_catalogue(store, 'Choose water cycle')
    store.set_canonical(row['asset_id'], row['version_id'])
    with pytest.raises(ValueError, match='canonical choice changed'):
        resolve_recommendation(store, selection['context'], recommendation(row))


@pytest.mark.parametrize('missing', [False, True])
def test_missing_or_damaged_local_blob_is_not_previewed(library, missing):
    store, row, _ = library
    selection = prepare_catalogue(store, 'Choose water cycle')
    blob = store.blob_path(row['sha256'])
    if missing:
        blob.unlink()
    else:
        blob.write_bytes(b'corrupted synthetic blob')
    with pytest.raises(ValueError, match='unavailable or damaged'):
        resolve_recommendation(store, selection['context'], recommendation(row))


def test_no_match_stays_no_match_without_new_job(library):
    store, _, _ = library
    with pytest.raises(ValueError, match='No saved images'):
        prepare_catalogue(store, 'Choose a diagram', 'does not exist')
    selection = prepare_catalogue(store, 'Choose a diagram')
    assert resolve_recommendation(store, selection['context'],
        json.dumps({'version_id': None, 'reason': 'No suitable diagram.'})) == (None, 'No suitable diagram.')
    assert len(store.list_jobs()) == 1


@pytest.mark.parametrize('result', ['not JSON', '[]', '{"version_id": 42, "reason": "No"}',
                                    '{"version_id": null, "reason": 42}'])
def test_malformed_recommendations_fail_closed(library, result):
    store, _, _ = library
    selection = prepare_catalogue(store, 'Choose a diagram')
    with pytest.raises(ValueError):
        resolve_recommendation(store, selection['context'], result)


def test_durable_library_result_previews_locally_without_queue_or_insert(library, tmp_path):
    store, row, _ = library
    selection = prepare_catalogue(store, 'Choose a diagram')
    service = HermesService({'LOCAL_ONLY': '1'}, tmp_path / 'hermes')
    saved = service.prepare(selection['task'], selection['context'])
    request_id = saved['request_id']
    service._save_state(request_id, 'completed', 'Synthetic completion', text=recommendation(row))
    service.close()
    app = ComposeApp.__new__(ComposeApp)
    app.hermes_service = HermesService({'LOCAL_ONLY': '1'}, tmp_path / 'hermes')
    app.hermes_panel = Mock(_active_request=request_id, _busy=False)
    app.media_store = store
    app.tabs, app.media_tab = Mock(), object()
    app.media_panel = Mock()
    app.media_panel.run.side_effect = lambda work, done: done(work())
    app._queue_media = Mock()
    ComposeApp._review_hermes_library(app)
    app.media_panel.reveal_version.assert_called_once()
    assert app.media_panel.reveal_version.call_args[0][0]['version_id'] == row['version_id']
    app._queue_media.assert_not_called()
    assert len(store.list_jobs()) == 1
    app.hermes_service.close()


def test_library_preparation_loads_visible_preview_and_never_submits():
    panel = HermesPanel.__new__(HermesPanel)
    panel._blocked = lambda: False
    panel._busy = False
    panel._prepared_request = None
    panel.task, panel.context = Mock(), Mock()
    panel.prepare = Mock(return_value=True)
    panel.submit = Mock()
    assert panel.load_library_task('Bounded task', 'Selected catalogue')
    panel.context.insert.assert_called_once_with('1.0', 'Selected catalogue')
    panel.prepare.assert_called_once()
    panel.submit.assert_not_called()
    panel._prepared_request = 'existing-task'
    panel.set_notice = Mock()
    assert not panel.load_library_task('Another task', 'Another catalogue')
    assert panel.prepare.call_count == 1


def test_library_result_button_opens_review_instead_of_queueing_json(library):
    store, row, _ = library
    selection = prepare_catalogue(store, 'Choose a diagram')
    panel = HermesPanel.__new__(HermesPanel)
    panel._result_text = recommendation(row)
    panel._selected_context = selection['context']
    panel._active_request = panel._result_request_id = 'selected-request'
    panel._selected_status = 'completed'
    panel.review_library, panel.queue_text = Mock(), Mock()
    panel.queue_result()
    panel.review_library.assert_called_once_with()
    panel.queue_text.assert_not_called()


def test_changed_active_run_discards_pending_library_preview(library):
    store, row, _ = library
    selection = prepare_catalogue(store, 'Choose a diagram')
    app = ComposeApp.__new__(ComposeApp)
    app.hermes_service = Mock()
    app.hermes_service.preview.return_value = {'status': 'completed',
        'context': selection['context'], 'text': recommendation(row)}
    app.hermes_panel = Mock(_active_request='original-request', _busy=False)
    app.media_store = store
    app.tabs, app.media_tab = Mock(), object()
    app.media_panel = Mock()
    ComposeApp._review_hermes_library(app)
    work, done = app.media_panel.run.call_args[0]
    result = work()
    app.hermes_panel._active_request = 'different-request'
    done(result)
    app.media_panel.reveal_version.assert_not_called()
    assert 'selected Hermes run changed' in app.media_panel.tell.call_args[0][0]


def test_revealed_library_choice_updates_gallery_and_version_dropdown(library):
    store, row, image = library
    older = store.import_bytes(image, 'Earlier asset')
    panel = MediaPanel.__new__(MediaPanel)
    panel.query, panel.gallery, panel.version_box = Mock(), Mock(), Mock()
    panel.gallery.exists.return_value = False
    panel.gallery.selection.return_value = [row['asset_id']]
    panel.rows = {older['asset_id']: older}
    panel.versions = [older]
    panel.refresh = Mock()
    panel.service = Mock(store=store)
    panel.show_version = Mock()
    panel.reveal_version(row)
    panel.query.set.assert_called_once_with('')
    panel.gallery.selection_set.assert_called_once_with(row['asset_id'])
    assert [version['version_id'] for version in panel.versions] == [row['version_id']]
    panel.version_box.current.assert_called_once_with(0)
    panel.show_version.assert_called_once_with(row)
