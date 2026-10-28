"""Saved protected settings through a real Board request and first-use preview.

Only the composer, image provider, ledger and credential cipher are fixtures.
The Board UI/session, profile selection, acquisition and persistence are real.
"""
import io
import json
import os
from pathlib import Path
import sys
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication, QDialog
from board_agent import result_envelope
import board_agent_ui as ui
import board_candidate as gui
from board_model import BoardModel
from board_session import BoardSession
from board_store import BoardStore
from board_runtime import PrimaryBoardComposer, truthy
from media_store import MediaStore
from media_service import MediaService
import companion_settings
import config_loader


class FixtureLedger:
    def __init__(self):
        self.reserved, self.committed = [], []

    def reserve_budget(self, job_id, cents):
        self.reserved.append((job_id, cents))

    def mark_budget_uncertain(self, job_id):
        pass

    def commit_budget(self, job_id, cents):
        self.committed.append((job_id, cents))


class FixtureDogProvider:
    def __init__(self):
        self.calls = []

    def generate(self, prompt, **options):
        self.calls.append((prompt, options))
        image = io.BytesIO()
        Image.new('RGB', (200, 160), '#bc915f').save(image, format='PNG')
        return {'data': image.getvalue(), 'mime': 'image/png',
                'source': {'provider': 'gemini', 'model': 'gemini-nano-banana-2.1'},
                'usage': {}, 'request_id': 'fixture-dog',
                'receipt': {'provider': 'gemini', 'outcome': 'image_received'}}

    def close(self):
        pass


@pytest.mark.parametrize('uncapped', [False, True])
def test_saved_voice_profile_enables_dog_preview_and_survives_board_reopen(tmp_path, monkeypatch, uncapped):
    app = QApplication.instance() or QApplication([])
    for key in config_loader.ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(config_loader, 'fallback_env_paths', lambda *_: [tmp_path / 'absent.env'])
    monkeypatch.setattr(gui, 'CANDIDATE_ROOT', tmp_path)
    monkeypatch.setattr(companion_settings, '_crypt',
                        lambda data, decrypt=False: data[7:] if decrypt else b'SEALED:' + data)
    profile, lesson, resources = tmp_path / 'voice-feature', tmp_path / 'lesson', tmp_path / 'resources'
    settings = {'LOCAL_ONLY': '0', 'IMAGE_PROVIDER': 'gemini',
                'GOOGLE_IMAGE_MODEL': 'gemini-nano-banana-2.1', 'GOOGLE_IMAGE_SIZE': '1K',
                'GOOGLE_IMAGE_ESTIMATE_1K_AUD_CENTS': '24', 'IMAGE_GENERATION_ENABLED': '1',
                'GOOGLE_IMAGE_API_KEY': 'fixture-google-secret', 'GROQ_API_KEY': 'fixture-groq-secret',
                'MEDIA_SYNC_ENABLED': '1', 'MEDIA_SERVER_URL': 'https://fixture.invalid',
                'MEDIA_SERVER_TOKEN': 'fixture-budget-secret', 'HERMES_ENABLED': '0'}
    if uncapped:
        settings.update(IMAGE_SPENDING_UNCAPPED='1', MEDIA_SYNC_ENABLED='0',
                        MEDIA_SERVER_URL='', MEDIA_SERVER_TOKEN='', GOOGLE_IMAGE_ESTIMATE_1K_AUD_CENTS='')
    companion_settings.save_settings(settings, profile)
    assert 'fixture-google-secret' not in (profile / 'settings.json').read_text()
    provider, ledger = FixtureDogProvider(), FixtureLedger()
    monkeypatch.setattr(ui, 'create_resource_service', lambda library, config:
                        None if truthy(config.get('LOCAL_ONLY')) else
                        MediaService(library.media, config, None if uncapped else ledger, provider=provider))
    monkeypatch.setattr(PrimaryBoardComposer, 'complete', lambda *_:
                        json.dumps({'kind': 'illustration', 'source': None, 'query': 'dog'}))

    def compose(self, prepared, report, cancelled):
        image = json.loads(prepared['context'])['selected_images'][0]
        return result_envelope(prepared, template={'name': 'title_image', 'title': 'A dog',
            'body': 'Dogs are mammals.', 'image_ref': image['image_ref']})

    monkeypatch.setattr(PrimaryBoardComposer, '__call__', compose)

    def open_board():
        store = BoardStore(lesson)
        resolver = gui.image_resolver(MediaStore(lesson / 'media'))
        session = (BoardSession.open(store, image_resolver=resolver) if (lesson / 'lesson.json').exists()
                   else BoardSession(BoardModel(), store=store, image_resolver=resolver))
        return gui.BoardCandidate(session, store=store, resolver=resolver, resource_root=resources)

    board = open_board()
    reopened = None
    try:
        panel = board.agent_panel
        assert panel is not None and truthy(panel.config.get('LOCAL_ONLY'))
        before = board.session.pupil_view()['document']
        panel.companion_settings_root = profile
        assert panel.apply_settings_profile(profile), panel.settings_error
        assert not truthy(panel.config.get('LOCAL_ONLY'))
        assert not provider.calls and not ledger.reserved
        assert board.session.pupil_view()['document'] == before
        selection = json.loads(panel.settings_selection_path.read_text())
        assert selection['schema'] == 1 and selection['settings_root'] == str(profile.resolve())
        assert set(selection['service_bindings']) == {'budget'}
        assert all(secret not in json.dumps(selection) for secret in
                   ('fixture-google-secret', 'fixture-budget-secret', 'https://fixture.invalid'))
        panel.instruction.setPlainText('Draw a dog and add it to the teaching board.')
        panel.send()
        assert panel.request_id, panel.progress.text()
        for _ in range(250):
            panel.tick()
            state = panel.controller.snapshot(panel.request_id)
            if state['status'] != 'working':
                break
            app.processEvents()
            time.sleep(.01)
        assert state['status'] == 'awaiting_confirmation', state
        assert 'first_generated_image_use' in state['confirmation_reasons']
        assert board.session.pupil_view()['document'] == before
        assert len(provider.calls) == 1
        if uncapped:
            assert ledger.reserved == ledger.committed == []
        else:
            assert ledger.reserved == ledger.committed and len(ledger.reserved) == 1
            assert ledger.reserved[0][1] == 24
        monkeypatch.setattr(QDialog, 'exec', lambda _dialog: QDialog.DialogCode.Accepted)
        panel.show_preview()
        panel.tick()
        assert panel.controller.snapshot(panel.request_id)['status'] == 'applied'
        published = board.session.pupil_view()['document']
        assert any(obj['type'] == 'image' for obj in published['pages'][0]['objects'])
        board.undo()
        assert board.session.pupil_view()['document']['pages'] == before['pages']
        board.redo()
        assert board.save_now()
        board.finish_close()
        reopened = open_board()
        assert reopened.session.pupil_view()['document']['pages'] == published['pages']
        assert reopened.agent_panel.settings_root == profile.resolve()
        assert not truthy(reopened.agent_panel.config.get('LOCAL_ONLY'))
        assert len(provider.calls) == 1, 'Reopening must not replay the image request'
    finally:
        if not board.session._closed:
            board.finish_close()
        if reopened is not None:
            reopened.finish_close()
