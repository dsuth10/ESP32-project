"""Explicit saved-provider selection, safe reload and pupil preservation."""
from concurrent.futures import Future
import json
from pathlib import Path
import sys
import uuid

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_candidate import BoardCandidate, image_resolver, load_board_settings
from board_model import BoardModel
from board_session import BoardSession
from board_store import BoardStore
from media_store import MediaStore


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def boards(app, tmp_path):
    opened = []
    def create(*, shared=None, selection_path=None):
        root = tmp_path / ('lesson-' + uuid.uuid4().hex[:8])
        store = BoardStore(root); resolver = image_resolver(MediaStore(root / 'media'))
        session = BoardSession(BoardModel(), store=store, image_resolver=resolver)
        board = BoardCandidate(session, store=store, resolver=resolver, resource_root=shared,
                               settings_selection_path=selection_path)
        assert board.agent_panel is not None
        opened.append(board)
        return board
    yield create
    for board in opened:
        board.agent_panel.controller._requests.clear()
        board.agent_panel._audio = board.agent_panel._speech_future = board.agent_panel._recovery_future = None
        if not board.session._closed:
            board.finish_close()
        board.hide(); board.pupil.hide(); board.deleteLater()
    app.processEvents()


def profile(tmp_path, **values):
    root = tmp_path / ('feature-settings-' + uuid.uuid4().hex[:8]); root.mkdir()
    (root / 'settings.json').write_text(json.dumps({'LOCAL_ONLY': '0', 'IMAGE_PROVIDER': 'gemini',
        'HERMES_ENABLED': '0', 'MEDIA_SYNC_ENABLED': '0', **values}), encoding='utf-8')
    return root


def test_default_does_not_discover_voice_settings_and_selection_preserves_frozen_lesson(boards, tmp_path):
    board = boards(); panel = board.agent_panel
    saved = profile(tmp_path)
    panel.companion_settings_root = saved
    assert panel.preparer.local_only
    board.add_object('text'); board.freeze()
    before_teacher, before_pupil = board.session.teacher_view(), board.session.pupil_view()
    assert panel.apply_settings_profile(saved)
    assert not panel.preparer.local_only
    assert panel.settings_root == saved.resolve()
    assert board.session.teacher_view() == before_teacher
    assert board.session.pupil_view() == before_pupil
    assert panel.controller.session is board.session
    selection = json.loads(panel.settings_selection_path.read_text())
    assert selection == {'schema': 1, 'settings_root': str(saved.resolve()), 'service_bindings': {}}
    assert 'GOOGLE_IMAGE' not in panel.settings_selection_path.read_text()


def test_reload_is_explicit_and_remembered_for_same_resource_library(boards, tmp_path):
    shared = tmp_path / 'shared-resources'
    board = boards(shared=shared); panel = board.agent_panel
    saved = profile(tmp_path)
    assert panel.apply_settings_profile(saved)
    values = json.loads((saved / 'settings.json').read_text()); values['LOCAL_ONLY'] = '1'
    (saved / 'settings.json').write_text(json.dumps(values))
    assert not panel.preparer.local_only
    assert panel.apply_settings_profile(saved)
    assert panel.preparer.local_only
    reopened = boards(shared=shared)
    assert reopened.agent_panel.settings_root == saved.resolve()
    assert reopened.agent_panel.preparer.local_only
    assert panel.apply_settings_profile(None)
    again = boards(shared=shared)
    assert again.agent_panel.settings_root is None
    assert again.agent_panel.preparer.local_only


@pytest.mark.parametrize('field', ['_audio', '_speech_future', '_recovery_future'])
def test_reload_refuses_microphone_and_unconsumed_futures(boards, tmp_path, field):
    board = boards(); panel = board.agent_panel
    before = panel.controller
    setattr(panel, field, object())
    assert not panel.apply_settings_profile(profile(tmp_path))
    assert panel.controller is before
    assert not panel.settings_selection_path.exists()


@pytest.mark.parametrize('status,pending', [('working', True), ('awaiting_confirmation', False), ('stale', True), ('cancelled', True)])
def test_reload_checks_superseded_workers_and_pending_preview(boards, tmp_path, status, pending):
    panel = boards().agent_panel
    future = Future()
    if not pending:
        future.set_result(None)
    panel.controller._requests['older-job'] = {'status': status, 'future': future}
    # This older worker is not the UI's currently selected request.
    panel.request_id = None
    assert not panel.apply_settings_profile(profile(tmp_path))
    assert panel.preparer.local_only
    assert not panel.settings_selection_path.exists()


def test_reload_refuses_unresolved_paid_attempt(boards, tmp_path):
    panel = boards().agent_panel
    request = uuid.uuid4().hex
    root = panel.library.root / 'board-attempts'; root.mkdir()
    (root / (request + '.json')).write_text(json.dumps({'schema': 1, 'request_id': request,
        'job_id': 'original-job', 'status': 'uncertain'}))
    assert not panel.apply_settings_profile(profile(tmp_path))
    assert 'reconcile' in panel.settings_error
    assert panel.preparer.local_only


def test_failed_decryption_and_metadata_write_preserve_active_runtime_without_secret_errors(boards, tmp_path, monkeypatch):
    import companion_settings
    panel = boards().agent_panel
    saved = profile(tmp_path)
    before = panel.controller, panel.preparer, dict(panel.config)
    def unavailable(_root):
        raise RuntimeError('synthetic-private-key must never be displayed')
    monkeypatch.setattr(companion_settings, 'load_settings', unavailable)
    assert not panel.apply_settings_profile(saved)
    assert (panel.controller, panel.preparer, panel.config) == before
    assert 'synthetic-private-key' not in panel.settings_error
    monkeypatch.undo()
    def denied(_root):
        raise OSError('synthetic-private-key')
    monkeypatch.setattr(panel, '_remember_settings', denied)
    assert not panel.apply_settings_profile(saved)
    assert (panel.controller, panel.preparer, panel.config) == before
    assert 'synthetic-private-key' not in panel.settings_error


def test_stable_profile_and_linked_credentials_are_rejected(boards, tmp_path):
    panel = boards().agent_panel
    stable = tmp_path / 'ESP32ClassroomCompanion'; stable.mkdir()
    (stable / 'settings.json').write_text('{}')
    assert not panel.apply_settings_profile(stable)
    with pytest.raises(ValueError, match='stable companion'):
        load_board_settings(stable)
    saved = profile(tmp_path)
    source = tmp_path / 'private.bin'; source.write_bytes(b'synthetic')
    try:
        (saved / 'credentials.dpapi').symlink_to(source)
    except OSError:
        pytest.skip('Creating a Windows symlink needs host permission')
    with pytest.raises(ValueError, match='links or junctions'):
        load_board_settings(saved)


def test_damaged_remembered_selection_falls_back_to_local_without_changing_it(boards, tmp_path):
    shared = tmp_path / 'resources'; shared.mkdir()
    path = shared / 'board-settings-selection.json'; path.write_text('{damaged')
    panel = boards(shared=shared).agent_panel
    assert panel.preparer.local_only
    assert panel.settings_root is None
    assert 'local-only' in panel.settings_error
    assert path.read_text() == '{damaged'


def test_session_change_keeps_settings_and_recovery_store_belongs_to_new_lesson(boards, tmp_path):
    board = boards(); panel = board.agent_panel
    saved = profile(tmp_path)
    assert panel.apply_settings_profile(saved)
    original_selection = panel.settings_selection_path
    root = tmp_path / 'next-lesson'; store = BoardStore(root)
    resolver = image_resolver(MediaStore(root / 'media'))
    previous = board.session
    board.session = BoardSession(BoardModel(), store=store, image_resolver=resolver)
    board.store, board.resolver = store, resolver
    panel.session_changed(); previous.close()
    assert panel.settings_selection_path == original_selection
    assert panel.settings_root == saved.resolve()
    assert not panel.preparer.local_only
    assert panel.recovery_store.root == (root / 'board-requests').resolve()
    assert panel.controller.session is board.session


def test_explicit_selection_path_reopens_across_different_lesson_libraries(boards, tmp_path):
    selection = tmp_path / 'voice-profile' / 'board-settings-selection.json'
    saved = profile(tmp_path)
    first = boards(selection_path=selection)
    assert first.agent_panel.apply_settings_profile(saved)
    second = boards(selection_path=selection)
    assert first.agent_panel.library.root != second.agent_panel.library.root
    assert second.agent_panel.settings_root == saved.resolve()
    assert not second.agent_panel.preparer.local_only


def test_readable_but_invalid_remote_profile_keeps_settings_repair_control(boards, tmp_path):
    shared = tmp_path / 'invalid-config-resources'; shared.mkdir()
    saved = profile(tmp_path, HERMES_ENABLED='1', HERMES_URL='http://example.invalid')
    selection = shared / 'board-settings-selection.json'
    selection.write_text(json.dumps({'schema': 1, 'settings_root': str(saved)}))
    panel = boards(shared=shared).agent_panel
    assert panel.preparer.local_only
    assert panel.settings_root == saved.resolve()
    assert panel.settings_button.isEnabled()
    assert 'local-only' in panel.settings_error


def test_restart_restores_original_image_service_for_recovery_without_rebinding(boards, tmp_path, monkeypatch):
    import board_candidate
    shared = tmp_path / 'image-recovery-resources'
    saved = profile(tmp_path)
    config = {'LOCAL_ONLY': '0', 'IMAGE_PROVIDER': 'gemini', 'HERMES_ENABLED': '0',
              'MEDIA_SYNC_ENABLED': '1', 'MEDIA_SERVER_URL': 'https://original.invalid',
              'MEDIA_SERVER_TOKEN': 'synthetic-original-token'}
    monkeypatch.setattr(board_candidate, 'load_board_settings', lambda _: dict(config))
    first = boards(shared=shared).agent_panel
    assert first.apply_settings_profile(saved)
    request = uuid.uuid4().hex
    attempts = shared / 'board-attempts'; attempts.mkdir()
    (attempts / (request + '.json')).write_text(json.dumps({'schema': 1, 'request_id': request,
        'job_id': 'existing-job', 'status': 'uncertain',
        'budget_fingerprint': first._service_bindings(config)['budget']}))
    def unavailable(_):
        raise RuntimeError('Protected storage temporarily unavailable')
    monkeypatch.setattr(board_candidate, 'load_board_settings', unavailable)
    restarted = boards(shared=shared).agent_panel
    assert restarted.preparer.local_only
    assert restarted.settings_root == saved.resolve()
    monkeypatch.setattr(board_candidate, 'load_board_settings', lambda _: dict(config))
    assert restarted.apply_settings_profile(saved)
    assert not restarted.preparer.local_only
    assert json.loads((attempts / (request + '.json')).read_text())['status'] == 'uncertain'
    config['MEDIA_SERVER_TOKEN'] = 'synthetic-different-account'
    previous = restarted.controller
    assert not restarted.apply_settings_profile(saved)
    assert restarted.controller is previous
    assert 'original service and credential' in restarted.settings_error
    metadata = restarted.settings_selection_path.read_text()
    assert 'synthetic-original-token' not in metadata and 'original.invalid' not in metadata


def test_old_hermes_dispatch_fingerprint_allows_original_reconnect_but_rejects_credential_change(boards, tmp_path, monkeypatch):
    import board_candidate
    import hashlib
    shared = tmp_path / 'old-hermes-resources'; shared.mkdir()
    saved = profile(tmp_path)
    config = {'LOCAL_ONLY': '0', 'HERMES_ENABLED': '1', 'HERMES_URL': 'https://original.invalid',
              'HERMES_TOKEN': 'synthetic-original-token', 'MEDIA_SYNC_ENABLED': '0'}
    task = shared / 'agent-runtime' / 'hermes-runs' / uuid.uuid4().hex; task.mkdir(parents=True)
    identity = hashlib.sha256((config['HERMES_URL'] + '\0' + config['HERMES_TOKEN']).encode()).hexdigest()
    (task / 'state.json').write_text(json.dumps({'request_id': task.name, 'status': 'uncertain'}))
    (task / 'dispatch-identity.json').write_text(json.dumps({'fingerprint': identity}))
    panel = boards(shared=shared).agent_panel
    assert panel.preparer.local_only
    monkeypatch.setattr(board_candidate, 'load_board_settings', lambda _: dict(config))
    assert panel.apply_settings_profile(saved)
    assert panel.hermes is not None
    config['HERMES_TOKEN'] = 'synthetic-new-token'
    assert not panel.apply_settings_profile(saved)
    assert 'original service and credential' in panel.settings_error


def test_shared_preference_cannot_rebind_another_librarys_uncertain_budget_attempt(boards, tmp_path, monkeypatch):
    import board_candidate
    selection = tmp_path / 'shared-voice-profile' / 'board-settings-selection.json'
    saved_a, saved_b = profile(tmp_path), profile(tmp_path)
    common = {'LOCAL_ONLY': '0', 'HERMES_ENABLED': '0', 'MEDIA_SYNC_ENABLED': '1'}
    configs = {saved_a: {**common, 'MEDIA_SERVER_URL': 'https://budget-a.invalid', 'MEDIA_SERVER_TOKEN': 'synthetic-token-a'},
               saved_b: {**common, 'MEDIA_SERVER_URL': 'https://budget-b.invalid', 'MEDIA_SERVER_TOKEN': 'synthetic-token-b'}}
    monkeypatch.setattr(board_candidate, 'load_board_settings', lambda root: dict(configs[root]))
    resources_a, resources_b = tmp_path / 'resources-a', tmp_path / 'resources-b'
    first = boards(shared=resources_a, selection_path=selection).agent_panel
    assert first.apply_settings_profile(saved_a)
    request = uuid.uuid4().hex
    attempts = resources_a / 'board-attempts'; attempts.mkdir()
    identity_a = first._service_bindings(configs[saved_a])['budget']
    receipt = attempts / (request + '.json')
    receipt.write_text(json.dumps({'schema': 1, 'request_id': request, 'job_id': 'original-a-job',
                                   'status': 'uncertain', 'budget_fingerprint': identity_a}))
    other = boards(shared=resources_b, selection_path=selection).agent_panel
    assert other.apply_settings_profile(saved_b)
    assert json.loads(selection.read_text())['settings_root'] == str(saved_b.resolve())
    reopened = boards(shared=resources_a, selection_path=selection).agent_panel
    assert reopened.preparer.local_only
    assert not reopened.apply_settings_profile(saved_b)
    assert reopened.apply_settings_profile(saved_a)
    assert reopened._service_bindings(reopened.config)['budget'] == identity_a
    assert json.loads(receipt.read_text())['budget_fingerprint'] == identity_a


def test_legacy_uncertain_budget_receipt_never_uses_mutable_preference_as_identity(boards, tmp_path, monkeypatch):
    import board_candidate
    shared = tmp_path / 'legacy-receipt-library'
    saved = profile(tmp_path)
    config = {'LOCAL_ONLY': '0', 'HERMES_ENABLED': '0', 'MEDIA_SYNC_ENABLED': '1',
              'MEDIA_SERVER_URL': 'https://configured.invalid', 'MEDIA_SERVER_TOKEN': 'synthetic-token'}
    monkeypatch.setattr(board_candidate, 'load_board_settings', lambda _: dict(config))
    panel = boards(shared=shared).agent_panel
    assert panel.apply_settings_profile(saved)
    request = uuid.uuid4().hex
    attempts = shared / 'board-attempts'; attempts.mkdir()
    (attempts / (request + '.json')).write_text(json.dumps({'schema': 1, 'request_id': request,
        'job_id': 'legacy-unknown-job', 'status': 'uncertain'}))
    assert not panel.apply_settings_profile(saved)
    assert 'original service and credential' in panel.settings_error


def test_legacy_local_review_preserves_cancel_then_clears_only_original_barrier(boards, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QInputDialog, QMessageBox
    panel = boards().agent_panel
    assert panel.preparer.media is None and panel.preparer.local_only
    job = panel.library.media.create_job('generate', 'synthetic older dog request')
    panel.library.media.update_job(job['job_id'], 'needs_recovery', provider_dispatched=True,
                                   allocation_cents=24, accounting='reservation_held_pending_reconciliation')
    original_job = panel.library.media.get_job(job['job_id'])
    request = uuid.uuid4().hex
    attempts = panel.library.root / 'board-attempts'; attempts.mkdir()
    receipt = attempts / (request + '.json')
    receipt.write_text(json.dumps({'schema': 1, 'request_id': request, 'job_id': job['job_id'], 'status': 'uncertain'}))
    original_receipt = receipt.read_bytes()
    monkeypatch.setattr(QInputDialog, 'getItem', lambda *args, **kwargs: (args[3][0], True))
    monkeypatch.setattr(QMessageBox, 'question', lambda *args, **kwargs: QMessageBox.StandardButton.Cancel)
    panel.review_attempts()
    assert receipt.read_bytes() == original_receipt
    assert panel.library.media.get_job(job['job_id']) == original_job
    confirmations = []
    def confirm(*args, **kwargs):
        confirmations.append(args[2])
        return QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, 'question', confirm)
    panel.review_attempts()
    reviewed = json.loads(receipt.read_text())
    assert reviewed['status'] == 'reconciled'
    assert reviewed['review_mode'] == 'legacy_local_outcome_review'
    assert 'budget_fingerprint' not in reviewed
    assert job['job_id'] in confirmations[0] and 'original provider/account outcome' in confirmations[0]
    assert panel.library.media.get_job(job['job_id']) == original_job
    assert panel.preparer.media is None and panel.preparer.local_only
    assert panel.apply_settings_profile(profile(tmp_path))
    assert panel.media_service._service is None


def test_legacy_review_waits_for_superseded_worker_to_finish(boards, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    panel = boards().agent_panel
    panel.controller._requests['older-worker'] = {'status': 'cancelled', 'future': Future()}
    monkeypatch.setattr(QInputDialog, 'getItem', lambda *args, **kwargs: pytest.fail('Review opened while worker was unfinished'))
    panel.review_attempts()
    assert 'worker to finish' in panel.progress.text()
