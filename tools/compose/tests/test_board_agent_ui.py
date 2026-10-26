"""Native Qt assistant integration; fake models/audio and no external dispatch."""
from concurrent.futures import Future
import copy
import io
import json
import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (QApplication, QDialog, QSpinBox, QTextEdit, QCheckBox,
                              QGraphicsView, QDialogButtonBox, QFileDialog, QInputDialog, QMessageBox)
import board_agent_ui as ui
import board_candidate as gui
from board_agent import TeachingProfile, result_envelope, load_profile, save_profile
from board_model import new_object
from board_session import BoardSession
from board_store import BoardStore
from media_store import MediaStore


class FakePreparer:
    remote = False
    def __init__(self, library, lesson_media, config, **kwargs):
        self.library, self.lesson_media, self.config = library, lesson_media, config
        self.media = kwargs.get('media_service')
        self.calls, self.choices = [], {}
        self.resources = []
        self.dataset, self.chart_spec = None, None
        self.reconcile_calls = []

    def choose_for_request(self, request_id, record):
        self.choices[request_id] = copy.deepcopy(record)

    def __call__(self, prepared, report, cancelled):
        self.calls.append(copy.deepcopy(prepared))
        report('searching', 'Checking local saved resources.')
        return copy.deepcopy(self.resources)

    def reconcile_google_attempt(self, request_id, job_id, *, outcome):
        self.reconcile_calls.append((request_id, job_id, outcome))


class FakeComposer:
    remote = False
    def __init__(self):
        self.calls, self.handler = [], None
        self.block = None

    def __call__(self, prepared, report, cancelled):
        self.calls.append(copy.deepcopy(prepared))
        report('composing', 'Composing a complete teaching page.')
        if self.block:
            self.block.wait(3)
        if self.handler:
            return self.handler(prepared)
        page = json.loads(prepared['context'])['page']
        title = next(obj for obj in page['objects'] if obj['type'] == 'text')
        return result_envelope(prepared, commands=[{'op': 'update_object', 'page_id': page['id'],
            'object_id': title['id'], 'changes': {'text': 'Water cycle'}}])


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def editor(app, tmp_path, monkeypatch):
    monkeypatch.setattr(gui, 'CANDIDATE_ROOT', tmp_path)
    monkeypatch.setattr(ui, 'BoardResourcePreparer', FakePreparer)
    monkeypatch.setattr(ui, 'create_resource_service', lambda *args, **kwargs: None)
    media = MediaStore(tmp_path / 'lesson' / 'media')
    store = BoardStore(tmp_path / 'lesson')
    resolver = gui.image_resolver(media)
    session = BoardSession(gui.demo_model(media), store=store, image_resolver=resolver)
    composer = FakeComposer()
    window = gui.BoardCandidate(session, store=store, resolver=resolver,
        agent_config={'LOCAL_ONLY': True}, resource_root=tmp_path / 'resources', composer=composer)
    window.test_composer = composer
    window.show(); app.processEvents()
    window.agent_panel.timer.stop(); window.agent_panel.index_timer.stop()
    yield window
    if composer.block:
        composer.block.set()
    window.agent_panel.close_runtime()
    window.save_timer.stop(); window.property_timer.stop(); window.group_timer.stop()
    window.session.close(); window.pupil.hide(); window.hide(); window.deleteLater()
    app.processEvents()


def wait_done(panel, statuses=('applied', 'failed', 'stale', 'cancelled', 'awaiting_confirmation')):
    for _ in range(150):
        panel.tick()
        state = panel.controller.snapshot(panel.request_id)
        if state['status'] in statuses:
            return state
        QTest.qWait(10)
        # Native qWait can retain the GIL; let durable worker file I/O finish.
        time.sleep(.002)
    raise AssertionError('Fake composition did not finish: ' + str(panel.controller.snapshot(panel.request_id)))


def send(editor, text='Explain the water cycle'):
    panel = editor.agent_panel
    panel.instruction.setPlainText(text)
    panel.send_button.click()
    assert panel.request_id, panel.progress.text()
    return wait_done(panel)


def png_bytes(colour='#A0D5EC'):
    buffer = io.BytesIO(); Image.new('RGB', (200, 100), colour).save(buffer, format='PNG')
    return buffer.getvalue()


def generated_image(panel):
    version = panel.lesson_media.import_bytes(png_bytes(), 'Generated class diagram', origin='generated')
    record = panel.library._index(version, panel.lesson_media.root, approved=False)
    item = {key: version[key] for key in ('asset_id', 'version_id', 'sha256')}
    return record, {'image_ref': item, 'title': version['title'], 'width': version['width'],
        'height': version['height'], 'required': True, 'generated_unreviewed': True}


def test_real_candidate_exposes_teacher_controls_without_automatic_model_or_audio(editor):
    panel = editor.agent_panel
    assert panel.send_button.text() == 'Send Board request'
    assert panel.mic_button.text() == 'PC microphone'
    assert panel._audio is None and panel._speech_future is None
    assert editor.test_composer.calls == [] and panel.preparer.calls == []
    assert not panel.preview_button.isEnabled()
    assert panel.instruction.toPlainText() == ''


def test_catalogue_construction_failure_preserves_manual_editing_and_durable_save(app, tmp_path, monkeypatch):
    from board_resources import ResourceCatalogue
    import sqlite3
    def broken_catalogue(_self):
        raise sqlite3.OperationalError('Simulated unavailable catalogue/FTS5')
    monkeypatch.setattr(ResourceCatalogue, '_initialise', broken_catalogue)
    monkeypatch.setattr(gui, 'CANDIDATE_ROOT', tmp_path)
    root = tmp_path / 'manual-lesson'
    media = MediaStore(root / 'media'); store = BoardStore(root)
    resolver = gui.image_resolver(media)
    session = BoardSession(gui.demo_model(media), store=store, image_resolver=resolver)
    composer = FakeComposer()
    window = gui.BoardCandidate(session, store=store, resolver=resolver,
        agent_config={'LOCAL_ONLY': True}, composer=composer)
    try:
        assert window.agent_panel is None
        assert 'Manual editing and lesson saving remain available' in window.catalogue_error
        first = gui.page_from(session.teacher_view())['objects'][0]
        window.select(first['id']); window.text.setPlainText('Manual editing still works')
        assert window.flush_pending_edits() and window.save_now()
        saved = BoardStore(root).load().snapshot()
        assert saved['pages'][0]['objects'][0]['text'] == 'Manual editing still works'
        assert saved == session.teacher_view()['document']
        assert not composer.calls
    finally:
        window.save_timer.stop(); window.property_timer.stop(); window.group_timer.stop()
        session.close(); window.pupil.hide(); window.hide(); window.deleteLater(); app.processEvents()


def test_imported_dataset_and_chart_catalogue_absorbs_exact_ids_metadata_and_relations(editor):
    from board_resources import ResourceCatalogue
    from board_model import canonical_json
    import hashlib
    source = ResourceCatalogue(editor.store.root / 'catalogue')
    dataset = {'schema': 1, 'title': 'Imported rainfall', 'x': {'label': 'Month', 'unit': 'month'},
        'y': {'label': 'Rainfall', 'unit': 'mm'}, 'points': [{'label': 'January', 'value': 50}],
        'provenance': {'kind': 'teacher_supplied', 'publisher': 'Teacher', 'date': '2026-10-25',
                       'coverage': 'Exact imported measurements'}, 'illustrative': False}
    data_record = source.save_resource('dataset', dataset['title'], metadata=dataset,
        content_hash=hashlib.sha256(canonical_json(dataset)).hexdigest(), state='approved', availability='offline')
    spec = {'kind': 'bar', 'title': 'Imported rainfall chart', 'colour': '#336699', 'width': 960, 'height': 720}
    chart_record = source.save_resource('chart', spec['title'], metadata=spec,
        content_hash=hashlib.sha256(canonical_json(spec)).hexdigest(), state='approved', availability='offline')
    source.add_relationship(chart_record['version_id'], 'derived_from', data_record['version_id'])
    panel = editor.agent_panel
    panel._import_saved_catalogue()
    assert not panel.library_error
    panel._import_saved_catalogue()  # Reopen/repeated absorption is idempotent.
    for original in (data_record, chart_record):
        imported = panel.library.catalogue.get_resource_by_version(original['version_id'])
        assert imported['resource_id'] == original['resource_id']
        assert imported['version_id'] == original['version_id']
        assert imported['metadata'] == original['metadata']
        assert imported['content_hash'] == original['content_hash']
    relationships = panel.library.catalogue.relationships(chart_record['resource_id'], chart_record['version_id'])
    assert any(item['relation'] == 'derived_from' and item['target_version_id'] == data_record['version_id'] for item in relationships)
    panel.resource_type.setCurrentText('Charts'); panel.query.setText(spec['title']); panel.search()
    assert panel.results.count() == 1
    panel.choose(panel.results.item(0))
    assert panel.preparer.dataset['points'] == dataset['points']
    assert panel.preparer.chart_spec == {key: spec[key] for key in ('kind', 'title', 'colour')}
    assert not editor.test_composer.calls


@pytest.mark.parametrize('action', ['chooser_cancel', 'confirm_cancel', 'confirmed', 'still_running'])
def test_review_image_attempts_requires_exact_choice_and_explicit_outcome_review(editor, monkeypatch, action):
    from board_resource_policy import BoardRequestAcquisition
    panel = editor.agent_panel
    pending = [{'request_id': 'request-original-A', 'job_id': 'job-original-A', 'status': 'uncertain'},
               {'request_id': 'request-original-B', 'job_id': 'job-original-B', 'status': 'claimed'}]
    monkeypatch.setattr(BoardRequestAcquisition, 'unresolved', staticmethod(lambda root: copy.deepcopy(pending)))
    reads, questions = [], []
    def get_job(job_id):
        reads.append(job_id)
        return {'job_id': job_id, 'phase': 'running' if action == 'still_running' else 'needs_recovery'}
    panel.preparer.media = SimpleNamespace(store=SimpleNamespace(get_job=get_job))
    monkeypatch.setattr(QInputDialog, 'getItem', lambda *args, **kwargs:
        ('job-original-B · claimed', action != 'chooser_cancel'))
    def question(*args, **kwargs):
        questions.append(args[2])
        return QMessageBox.StandardButton.Yes if action == 'confirmed' else QMessageBox.StandardButton.Cancel
    monkeypatch.setattr(QMessageBox, 'question', question)
    panel.review_attempts()
    if action == 'chooser_cancel':
        assert reads == [] and questions == [] and panel.preparer.reconcile_calls == []
    elif action == 'still_running':
        assert reads == ['job-original-B'] and questions == [] and panel.preparer.reconcile_calls == []
        assert 'still unresolved' in panel.progress.text()
    elif action == 'confirm_cancel':
        assert reads == ['job-original-B'] and len(questions) == 1 and panel.preparer.reconcile_calls == []
    else:
        assert reads == ['job-original-B']
        assert panel.preparer.reconcile_calls == [('request-original-B', 'job-original-B', 'provider_account_reviewed')]
        assert len(questions) == 1 and 'allocations stay held' in questions[0]
        assert 'original receipt and allocation are retained' in panel.progress.text()
    assert not editor.test_composer.calls


def test_send_flushes_pending_edits_sends_effective_profile_exact_page_image_then_autosaves(editor):
    panel = editor.agent_panel
    first = gui.page_from(editor.session.teacher_view())['objects'][0]
    editor.select(first['id']); editor.text.setPlainText('Teacher wording before request')
    before = editor.session.teacher_view()['revision']
    state = send(editor)
    assert state['status'] == 'applied', state
    context = json.loads(editor.test_composer.calls[-1]['context'])
    assert context['revision'] > before
    assert context['selected_object_ids'] == [first['id']]
    assert context['page']['objects'][0]['text'] == 'Teacher wording before request'
    assert context['effective_context']['year_level'] == 5
    exact = next(obj['image_ref'] for obj in context['page']['objects'] if obj['type'] == 'image')
    assert context['selected_images'][0]['image_ref'] == exact
    assert len(context['page']['objects']) == 5
    assert editor.save_timer.isActive()
    editor.autosave()
    reopened = BoardStore(editor.store.root).load().snapshot()
    assert reopened == editor.session.teacher_view()['document']
    saved_pages = panel.library.catalogue.search('Water cycle', resource_types=['page'])
    assert len(saved_pages) == 1 and saved_pages[0]['metadata']['page']['id'] == context['page']['id']
    editor.undo()
    assert gui.page_from(editor.session.teacher_view())['objects'][0]['text'] == 'Teacher wording before request'


def test_targeted_followup_uses_new_revision_and_not_other_pages(editor):
    assert send(editor)['status'] == 'applied'
    previous = json.loads(editor.test_composer.calls[-1]['context'])
    assert send(editor, 'Make the title shorter')['status'] == 'applied'
    current = json.loads(editor.test_composer.calls[-1]['context'])
    assert current['revision'] == previous['revision'] + 1
    assert current['session_token'] != previous['session_token']
    assert current['page']['objects'][0]['text'] == 'Water cycle'
    assert 'Condensation' not in editor.test_composer.calls[-1]['context']
    assert 'Precipitation' not in editor.test_composer.calls[-1]['context']


def test_profile_edit_reset_and_effective_defaults_are_saved_locally(editor, monkeypatch):
    panel = editor.agent_panel
    def accept(dialog):
        dialog.findChild(QSpinBox).setValue(4)
        dialog.findChild(QTextEdit).setPlainText('Use local habitats and metric units.')
        dialog.findChild(QCheckBox).setChecked(True)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QDialog, 'exec', accept)
    panel.edit_profile()
    saved = load_profile(panel.profile_path)
    assert saved.year_level == 4 and saved.revision == 1 and saved.allow_illustrative_data
    assert send(editor)['effective_context']['profile_revision'] == 1
    assert editor.test_composer.calls[-1]['effective_context']['profile_instructions'] == saved.instructions
    def reset(dialog):
        buttons = dialog.findChild(QDialogButtonBox)
        buttons.button(QDialogButtonBox.StandardButton.Reset).click()
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QDialog, 'exec', reset)
    panel.edit_profile()
    assert panel.profile.year_level == 5 and not panel.profile.allow_illustrative_data


def test_corrupt_profile_blocks_request_until_teacher_saves_repaired_defaults(editor, monkeypatch):
    panel = editor.agent_panel
    panel.profile_error = 'Saved teaching profile needs repair.'
    panel.instruction.setPlainText('Explain')
    panel.send()
    assert panel.request_id is None and editor.test_composer.calls == []
    monkeypatch.setattr(QDialog, 'exec', lambda dialog: QDialog.DialogCode.Accepted)
    panel.edit_profile()
    assert not panel.profile_error
    assert send(editor)['status'] == 'applied'


def test_cancel_late_worker_result_keeps_pupil_page_and_no_autosave_change(editor):
    panel = editor.agent_panel
    editor.test_composer.block = threading.Event()
    original = editor.session.pupil_view()
    panel.instruction.setPlainText('Compose slowly'); panel.send()
    for _ in range(100):
        if editor.test_composer.calls:
            break
        QTest.qWait(5)
    panel.cancel_button.click()
    editor.test_composer.block.set()
    assert wait_done(panel)['status'] == 'cancelled'
    assert editor.session.pupil_view() == original
    assert not panel.preview_button.isEnabled()


@pytest.mark.parametrize('change', ['edit', 'navigate', 'freeze'])
def test_ui_tick_reports_stale_after_teacher_changes_in_flight(editor, change):
    panel = editor.agent_panel
    editor.test_composer.block = threading.Event()
    panel.instruction.setPlainText('Compose slowly'); panel.send()
    if change == 'edit':
        editor.add_object('text')
    elif change == 'navigate':
        editor.navigate(1)
    else:
        editor.freeze()
    unchanged = editor.session.pupil_view()
    editor.test_composer.block.set()
    assert wait_done(panel)['status'] == 'stale'
    assert editor.session.pupil_view() == unchanged
    assert 'older result' in panel.progress.text()


def test_freeze_before_request_holds_pupil_view_until_resume(editor):
    editor.freeze(); frozen = editor.session.pupil_view()
    assert send(editor)['status'] == 'applied'
    assert editor.session.pupil_view() == frozen
    editor.resume()
    assert editor.session.pupil_view()['document'] == editor.session.teacher_view()['document']


def test_complete_destructive_preview_renders_on_native_canvas_then_exact_confirm(editor, monkeypatch):
    panel = editor.agent_panel
    editor.test_composer.handler = lambda prepared: result_envelope(prepared, template={
        'name': 'title_body', 'title': 'Water changes state', 'body': 'Heat causes evaporation.', 'image_ref': None})
    before = editor.session.pupil_view()
    state = send(editor)
    assert state['status'] == 'awaiting_confirmation'
    assert editor.session.pupil_view() == before
    assert panel.preview_button.isEnabled()
    inspected = []
    def accept(dialog):
        canvas = dialog.findChild(QGraphicsView)
        inspected.append(canvas)
        assert canvas.page_item is not None
        assert canvas.view['document']['pages'][0]['title'] == 'Water changes state'
        assert not canvas.isInteractive()
        context = dialog.findChild(QTextEdit)
        assert context.isReadOnly() and 'year_level' in context.toPlainText()
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QDialog, 'exec', accept)
    panel.show_preview()
    assert inspected
    assert panel.controller.snapshot(panel.request_id)['status'] == 'applied'
    assert gui.page_from(editor.session.pupil_view())['title'] == 'Water changes state'
    assert not panel.preview_button.isEnabled()


def test_preview_rejection_keeps_pupil_view_and_can_still_cancel(editor, monkeypatch):
    panel = editor.agent_panel
    editor.test_composer.handler = lambda prepared: result_envelope(prepared, template={
        'name': 'title_body', 'title': 'New title', 'body': 'New explanation.', 'image_ref': None})
    before = editor.session.pupil_view()
    assert send(editor)['status'] == 'awaiting_confirmation'
    monkeypatch.setattr(QDialog, 'exec', lambda dialog: QDialog.DialogCode.Rejected)
    panel.show_preview()
    assert panel.controller.snapshot(panel.request_id)['status'] == 'awaiting_confirmation'
    assert editor.session.pupil_view() == before
    panel.cancel()
    assert panel.controller.snapshot(panel.request_id)['status'] == 'cancelled'


def test_first_generated_preview_approves_only_used_exact_version_then_reuses_normally(editor, monkeypatch):
    panel = editor.agent_panel
    record, image = generated_image(panel)
    unrelated = panel.library.media.import_bytes(png_bytes('#ECA040'), 'Unrelated draft', origin='generated')
    other = panel.library._index(unrelated, panel.library.media.root, approved=False)
    # This draft is actually used elsewhere in the same lesson. Reviewing the
    # active page must not approve the other page's unrelated generated image.
    panel.library.select(other, panel.lesson_media)
    other_ref = {key: unrelated[key] for key in ('asset_id', 'version_id', 'sha256')}
    other_page = editor.session.teacher_view()['document']['pages'][1]['id']
    editor.apply([{'op': 'add_object', 'page_id': other_page,
        'object': new_object('image', image_ref=other_ref, x=800, y=600, width=200, height=100)}])
    panel.preparer.resources = [image]
    editor.test_composer.handler = lambda prepared: result_envelope(prepared, commands=[{
        'op': 'add_object', 'page_id': json.loads(prepared['context'])['page']['id'],
        'object': new_object('image', image_ref=image['image_ref'], x=800, y=600, width=200, height=100)}])
    assert send(editor, 'Add a new illustration')['status'] == 'awaiting_confirmation'
    assert panel.library.catalogue.get_resource_by_version(record['version_id'])['review_state'] == 'draft'
    monkeypatch.setattr(QDialog, 'exec', lambda dialog: QDialog.DialogCode.Accepted)
    panel.show_preview()
    assert panel.controller.snapshot(panel.request_id)['status'] == 'applied'
    assert panel.library.catalogue.get_resource_by_version(record['version_id'])['review_state'] == 'approved'
    assert panel.library.catalogue.get_resource_by_version(other['version_id'])['review_state'] == 'draft'
    panel.preparer.resources = []
    editor.test_composer.handler = None
    assert send(editor, 'Shorten the title')['status'] == 'applied'


def test_ordinary_edit_does_not_approve_unrelated_page_drafts(editor):
    panel = editor.agent_panel
    record, image = generated_image(panel)
    view = editor.session.teacher_view()
    other_page = view['document']['pages'][1]['id']
    editor.apply([{'op': 'add_object', 'page_id': other_page,
        'object': new_object('image', image_ref=image['image_ref'], x=800, y=600, width=200, height=100)}])
    assert send(editor)['status'] == 'applied'
    assert panel.library.catalogue.get_resource_by_version(record['version_id'])['review_state'] == 'draft'


def test_local_search_thumbnail_choice_pins_exact_version_for_next_request(editor):
    panel = editor.agent_panel
    record, image = generated_image(panel)
    panel.query.setText('Generated class diagram'); panel.search()
    assert panel.results.count() == 1
    item = panel.results.item(0)
    assert not item.icon().isNull()
    panel.choose(item)
    assert panel.selected_resource['version_id'] == record['version_id']
    assert send(editor, 'Use the selected saved resource')['status'] == 'applied'
    assert panel.preparer.choices[panel.request_id]['version_id'] == record['version_id']
    panel.clear_choice()
    assert panel.selected_resource is None


def test_dataset_dialog_retains_validated_local_units_then_preserves_it_on_invalid_data(editor, tmp_path, monkeypatch):
    panel = editor.agent_panel
    dataset = {'schema': 1, 'title': 'Rainfall', 'x': {'label': 'Month', 'unit': 'month'},
        'y': {'label': 'Rainfall', 'unit': 'mm'}, 'points': [{'label': 'January', 'value': 50}],
        'provenance': {'kind': 'teacher_supplied', 'publisher': 'Teacher', 'date': '2026-10-25',
                       'coverage': 'Class example measurements'}, 'illustrative': False}
    path = tmp_path / 'dataset.json'; path.write_text(json.dumps(dataset), encoding='utf-8')
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(path), 'JSON data (*.json)'))
    panel.load_dataset()
    assert panel.preparer.dataset['y']['unit'] == 'mm'
    preserved = copy.deepcopy(panel.preparer.dataset)
    path.write_text('{"execute":"SQL"}', encoding='utf-8')
    panel.load_dataset()
    assert panel.preparer.dataset == preserved
    assert 'Previous data was preserved' in panel.progress.text()


def test_saved_page_search_reuse_is_offline_atomic_undoable_and_normal_followup_resets_composer(editor, monkeypatch):
    import uuid
    panel = editor.agent_panel
    original = gui.page_from(editor.session.teacher_view())
    record = panel.library.retain_page(original, str(uuid.uuid4()), media_store=panel.lesson_media)
    # Change the live lesson so reuse must restore a distinguishable exact page.
    first = original['objects'][0]
    editor.apply([{'op': 'update_object', 'page_id': original['id'], 'object_id': first['id'],
                   'changes': {'text': 'New teacher title'}}])
    before = editor.session.pupil_view()
    panel.resource_type.setCurrentText('Saved pages'); panel.query.setText(original['title']); panel.search()
    assert panel.results.count() == 1
    panel.choose(panel.results.item(0))
    assert panel.selected_resource['version_id'] == record['version_id']
    calls = len(editor.test_composer.calls)
    panel.reuse_page()
    assert panel.request_id is not None, panel.progress.text()
    state = wait_done(panel)
    assert state['status'] == 'awaiting_confirmation', state
    assert len(editor.test_composer.calls) == calls  # Local deterministic reuse, no model.
    assert editor.session.pupil_view() == before
    monkeypatch.setattr(QDialog, 'exec', lambda dialog: QDialog.DialogCode.Accepted)
    panel.show_preview()
    assert panel.controller.snapshot(panel.request_id)['status'] == 'applied'
    restored = gui.page_from(editor.session.teacher_view())
    assert restored['title'] == original['title']
    assert restored['objects'][0]['text'] == original['objects'][0]['text']
    assert {obj['id'] for obj in restored['objects']}.isdisjoint({obj['id'] for obj in original['objects']})
    assert next(obj['image_ref'] for obj in restored['objects'] if obj['type'] == 'image') == next(
        obj['image_ref'] for obj in original['objects'] if obj['type'] == 'image')
    editor.undo()
    assert gui.page_from(editor.session.teacher_view()) == gui.page_from(before)
    # Reuse must release its temporary local composer and selection so an ordinary
    # teacher follow-up goes to the configured adapter without another gesture.
    result = send(editor, 'Shorten the title after undoing reuse')
    assert result['status'] == 'applied', panel.progress.text()
    assert len(editor.test_composer.calls) == calls+1
    assert panel.controller.composer is editor.test_composer


def test_dataset_and_chart_type_chooser_restore_exact_saved_data_and_specification(editor):
    from board_runtime import BoardResourcePreparer
    from board_resource_policy import validate_dataset
    panel = editor.agent_panel
    dataset = {'schema': 1, 'title': 'Saved rainfall', 'x': {'label': 'Month', 'unit': 'month'},
        'y': {'label': 'Rainfall', 'unit': 'mm'}, 'points': [{'label': 'January', 'value': 50}],
        'provenance': {'kind': 'teacher_supplied', 'publisher': 'Teacher', 'date': '2026-10-25',
                       'coverage': 'Exact saved measurements'}, 'illustrative': False}
    runtime = BoardResourcePreparer(panel.library, panel.lesson_media, {'LOCAL_ONLY': True},
                                   planner=lambda *_: (_ for _ in ()).throw(AssertionError('No model')))
    spec = {'kind': 'bar', 'title': 'Saved rainfall chart', 'colour': '#336699'}
    runtime._chart(dataset, spec, {'effective_context': {'allow_illustrative_data': False}})
    panel.resource_type.setCurrentText('Datasets'); panel.query.setText('Saved rainfall'); panel.search()
    assert panel.results.count() == 1
    panel.choose(panel.results.item(0))
    assert panel.selected_resource['resource_type'] == 'dataset'
    assert panel.preparer.dataset == validate_dataset(dataset) and panel.preparer.chart_spec is None
    panel.preparer.dataset = None
    panel.resource_type.setCurrentText('Charts'); panel.query.setText('Saved rainfall chart'); panel.search()
    assert panel.results.count() == 1
    panel.choose(panel.results.item(0))
    assert panel.selected_resource['resource_type'] == 'chart'
    assert panel.preparer.dataset == validate_dataset(dataset)
    assert panel.preparer.chart_spec == {**spec, 'colour': '#336699'}
    assert not editor.test_composer.calls and panel.request_id is None


def test_native_text_fit_validation_rejects_complete_page_before_any_publication(editor):
    def overflowing(prepared):
        context = json.loads(prepared['context'])
        obj = next(obj for obj in context['page']['objects'] if obj['type'] == 'text')
        return result_envelope(prepared, commands=[{'op': 'update_object', 'page_id': context['page']['id'],
            'object_id': obj['id'], 'changes': {'text': 'A very long explanation. '*100, 'height': 30}}])
    editor.test_composer.handler = overflowing
    before = editor.session.pupil_view()
    state = send(editor)
    assert state['status'] == 'failed'
    assert 'text needs more room' in state['message']
    assert editor.session.pupil_view() == before


def test_native_image_decode_failure_blocks_complete_publication(editor, monkeypatch):
    before = editor.session.pupil_view()
    def unsupported_native_image(_data):
        raise ValueError('Native image codec unavailable in this packaged runtime')
    monkeypatch.setattr(gui, 'decode_image', unsupported_native_image)
    state = send(editor)
    assert state['status'] == 'failed'
    assert editor.session.pupil_view() == before


def test_exact_wording_control_requires_preservation_then_accepts_matching_result(editor):
    panel = editor.agent_panel
    panel.exact_wording.setText('Preserve these exact teacher words.')
    before = editor.session.pupil_view()
    state = send(editor)
    assert state['status'] == 'failed' and 'Required exact wording' in state['message']
    assert editor.session.pupil_view() == before
    assert panel.exact_wording.text() == 'Preserve these exact teacher words.'
    panel.exact_wording.setText('Water cycle')
    assert send(editor)['status'] == 'applied'
    context = json.loads(editor.test_composer.calls[-1]['context'])
    assert context['required_wording'] == ['Water cycle']


def test_rotated_object_that_crosses_page_edge_is_rejected_before_publication(editor):
    def clipped(prepared):
        context = json.loads(prepared['context'])
        title = context['page']['objects'][0]
        return result_envelope(prepared, commands=[{'op': 'update_object', 'page_id': context['page']['id'],
            'object_id': title['id'], 'changes': {'x': 0, 'y': 0, 'rotation': 45}}])
    editor.test_composer.handler = clipped
    before = editor.session.pupil_view()
    state = send(editor)
    assert state['status'] == 'failed' and 'clipped at the page edge' in state['message']
    assert editor.session.pupil_view() == before


def test_real_local_chart_uses_full_readable_template_and_followup_keeps_chart_scale_guard(editor, monkeypatch):
    from board_runtime import BoardResourcePreparer
    panel = editor.agent_panel
    dataset = {'schema': 1, 'title': 'Rainfall', 'x': {'label': 'Month', 'unit': 'month'},
        'y': {'label': 'Rainfall', 'unit': 'mm'},
        'points': [{'label': 'January', 'value': 50}, {'label': 'February', 'value': 80}],
        'provenance': {'kind': 'teacher_supplied', 'publisher': 'Teacher', 'date': '2026-10-25',
                       'coverage': 'Class supplied measurements'}, 'illustrative': False}
    preparer = BoardResourcePreparer(panel.library, panel.lesson_media, {'LOCAL_ONLY': True},
                                    planner=lambda *_: (_ for _ in ()).throw(AssertionError('No model planner for supplied chart')))
    image = preparer._chart(dataset, None, {'effective_context': {'allow_illustrative_data': False}})
    assert image['visual_kind'] == 'chart'
    panel.preparer.resources = [image]
    editor.test_composer.handler = lambda prepared: result_envelope(prepared, template={
        'name': 'title_image', 'title': 'Rainfall in millimetres', 'body': 'Compare the supplied measurements.',
        'image_ref': image['image_ref']})
    state = send(editor, 'Create the supplied rainfall chart')
    assert state['status'] == 'awaiting_confirmation', state
    objects = gui.page_from({'document': panel.controller.preview(panel.request_id),
                             'page_id': editor.session.teacher_view()['page_id']})['objects']
    displayed = next(obj for obj in objects if obj['type'] == 'image')
    assert displayed['height']/image['height'] >= .75
    assert displayed['y'] >= 280
    monkeypatch.setattr(QDialog, 'exec', lambda dialog: QDialog.DialogCode.Accepted)
    panel.show_preview()
    assert panel.controller.snapshot(panel.request_id)['status'] == 'applied'
    panel.preparer.resources = []
    def shrink(prepared):
        context = json.loads(prepared['context'])
        chart = next(obj for obj in context['page']['objects'] if obj['type'] == 'image')
        return result_envelope(prepared, commands=[{'op': 'update_object', 'page_id': context['page']['id'],
            'object_id': chart['id'], 'changes': {'width': 400, 'height': 300}}])
    editor.test_composer.handler = shrink
    before = editor.session.pupil_view()
    state = send(editor, 'Make the chart smaller')
    assert state['status'] == 'failed'
    assert 'chart would be too small' in state['message']
    assert editor.session.pupil_view() == before


def test_fake_microphone_transcribes_only_after_explicit_gesture_and_requires_send(editor, monkeypatch, tmp_path):
    panel = editor.agent_panel
    model = tmp_path / 'fake-existing-whisper-model'; model.mkdir(); (model / 'model.bin').write_bytes(b'test marker')
    panel.config['LOCAL_WHISPER_MODEL'] = str(model)
    calls = []
    class Audio:
        def __init__(self, **kwargs):
            calls.append(('create', kwargs)); self.is_recording = False
        def start_recording(self):
            calls.append('start'); self.is_recording = True; return True
        def stop_recording(self):
            calls.append('stop'); self.is_recording = False; return b'wav-bytes', 1.0, .2
    class Speech:
        def __init__(self, **kwargs):
            calls.append(('pipeline', kwargs))
        def transcribe(self, wav):
            calls.append(('transcribe', wav)); return 'Explain condensation in Australian English.'
    monkeypatch.setitem(sys.modules, 'audio_capture', SimpleNamespace(AudioCapture=Audio))
    monkeypatch.setitem(sys.modules, 'speech_pipeline', SimpleNamespace(SpeechPipeline=Speech))
    assert calls == []
    panel.mic_button.click()
    assert panel._audio.is_recording and panel.mic_button.text() == 'Stop microphone'
    assert not editor.test_composer.calls
    panel.mic_button.click()
    for _ in range(100):
        panel.tick()
        if panel._speech_future is None:
            break
        QTest.qWait(10)
    assert panel.instruction.toPlainText() == 'Explain condensation in Australian English.'
    assert not editor.test_composer.calls and panel.request_id is None
    assert ('transcribe', b'wav-bytes') in calls
    assert panel.mic_button.isEnabled()


def test_local_only_missing_speech_model_never_constructs_pipeline_or_downloads(editor, monkeypatch):
    panel = editor.agent_panel
    calls = []
    class Audio:
        is_recording = True
        def stop_recording(self):
            calls.append('stop'); return b'fake-audio', 1.0, .2
    class Speech:
        def __init__(self, **kwargs):
            calls.append('pipeline must not be constructed')
            raise AssertionError('A missing local model cannot trigger a download')
    monkeypatch.setitem(sys.modules, 'speech_pipeline', SimpleNamespace(SpeechPipeline=Speech))
    panel.config['LOCAL_WHISPER_MODEL'] = 'base'
    panel.instruction.setPlainText('Existing typed request')
    panel._audio = Audio()
    panel._finish_recording()
    for _ in range(100):
        panel.tick()
        if panel._speech_future is None:
            break
        QTest.qWait(10)
    assert calls == ['stop']
    assert panel.instruction.toPlainText() == 'Existing typed request'
    assert 'transcription failed' in panel.progress.text()
    assert editor.test_composer.calls == []


def test_fake_transcription_failure_retains_typed_request_and_model_never_runs(editor, monkeypatch):
    panel = editor.agent_panel
    panel.instruction.setPlainText('Typed request survives')
    future = Future(); future.set_exception(ValueError('Private microphone details'))
    panel._speech_future = future
    panel.tick()
    assert panel.instruction.toPlainText() == 'Typed request survives'
    assert panel.progress.text() == 'Microphone transcription failed. Type the Board request instead.'
    assert not editor.test_composer.calls


def test_reopen_rebinds_agent_to_new_session_and_invalidates_in_flight_request(editor):
    panel = editor.agent_panel
    editor.test_composer.block = threading.Event()
    panel.instruction.setPlainText('Request before reopen'); panel.send()
    old_controller, old_id, old_session = panel.controller, panel.request_id, editor.session
    editor.reopen()
    assert editor.session is not old_session
    assert panel.controller is not old_controller
    assert panel.controller.session is editor.session
    assert panel.request_id is None
    assert old_controller.snapshot(old_id)['status'] == 'cancelled'
    editor.test_composer.block.set()
    editor.test_composer.block = None
    reopened_state = send(editor, 'Request after reopening')
    assert reopened_state['status'] == 'applied', panel.controller._requests[panel.request_id]['future'].exception()


def saved_recovery_result(editor):
    panel = editor.agent_panel
    prepared = panel.controller.prepare('Saved interrupted request', local_only=True)
    view = editor.session.teacher_view()
    baseline = {key: copy.deepcopy(view[key]) for key in ('document', 'page_id', 'revision')}
    panel.recovery_store.create(prepared, baseline)
    result = editor.test_composer(prepared, lambda *_: None, lambda: False)
    return panel.recovery_store.update(prepared['request_id'], status='completed', result=json.dumps(result))


def test_saved_request_list_reopens_locally_and_review_requires_preview(editor, monkeypatch):
    from board_recovery import BoardRecoveryStore
    panel = editor.agent_panel
    record = saved_recovery_result(editor)
    panel.recovery_store = BoardRecoveryStore(panel.recovery_store.root)
    panel.controller.recovery_store = panel.recovery_store
    before = editor.session.teacher_view()['document']
    panel.reload_saved_requests()
    assert panel.recovery_requests.currentData() == record['request_id']
    assert 'completed' in panel.recovery_requests.currentText()
    previews = []
    monkeypatch.setattr(panel, 'show_preview', lambda: previews.append(panel.controller.snapshot(panel.request_id)))
    panel.recover_request_button.click()
    assert previews[0]['status'] == 'awaiting_confirmation'
    assert 'recovered_request' in previews[0]['confirmation_reasons']
    assert editor.session.teacher_view()['document'] == before


def test_refresh_existing_request_runs_off_ui_thread_without_new_composition(editor, monkeypatch):
    panel = editor.agent_panel
    record = saved_recovery_result(editor)
    panel.reload_saved_requests()
    panel.config['LOCAL_ONLY'] = False
    panel.hermes = SimpleNamespace(list_requests=lambda: [])
    gate, entered = threading.Event(), threading.Event()
    owner = threading.get_ident()
    calls = []
    def refresh(request_id, service, *, local_only):
        calls.append((request_id, threading.get_ident(), local_only))
        entered.set(); gate.wait(2)
        return record
    monkeypatch.setattr(panel.recovery_store, 'refresh', refresh)
    count = len(editor.test_composer.calls)
    panel.refresh_request_button.click()
    assert entered.wait(1)
    assert calls == [(record['request_id'], calls[0][1], False)]
    assert calls[0][1] != owner
    assert panel._recovery_future is not None and not panel._recovery_future.done()
    assert len(editor.test_composer.calls) == count
    gate.set()
    for _ in range(100):
        panel.tick(); time.sleep(.002)
        if panel._recovery_future is None:
            break
    assert panel._recovery_future is None


def test_cancel_saved_request_prevents_local_review_in_local_only_mode(editor):
    panel = editor.agent_panel
    record = saved_recovery_result(editor)
    panel.reload_saved_requests()
    panel.stop_request_button.click()
    assert panel.recovery_store.get(record['request_id'])['publication_status'] == 'cancelled'
    panel.recover_request_button.click()
    assert 'cannot be presented again' in panel.recovery_note.text()
    assert panel._recovery_future is None
