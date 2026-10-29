"""Saved protected settings through a real Board request and first-use preview.

Only the image provider, ledger and credential cipher are fixtures; unexpected
text-model calls fail the test. Board UI/session, settings, acquisition,
composition, validation, preview and persistence are real.
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
import board_agent_ui as ui
import board_candidate as gui
from board_model import BoardModel, new_object
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


class FixtureImageProvider:
    def __init__(self, producer='gemini'):
        self.calls = []
        self.producer = producer

    def generate(self, prompt, **options):
        self.calls.append((prompt, options))
        image = io.BytesIO()
        Image.new('RGB', (200, 160), '#bc915f').save(image, format='PNG')
        return {'data': image.getvalue(), 'mime': 'image/png',
                'source': {'provider': self.producer, 'model': 'fixture'},
                'usage': {}, 'request_id': 'fixture-dog',
                'receipt': {'provider': self.producer, 'outcome': 'image_received'}}

    def close(self):
        pass


@pytest.mark.parametrize('producer,size', [('gemini', '1K'), ('gemini', '2K'), ('gemini', '4K'), ('openai', '1024x1024')])
@pytest.mark.parametrize('uncapped', [False, True])
@pytest.mark.parametrize(('instruction', 'occupied'), [
    ('Can you put an image of a horse up on the board?', False),
    ('I need you to generate an image of a horse and put it up on the board', False),
    ('I need you to generate an image of a horse and put it up on the board', True),
], ids=['put', 'generate', 'generate-existing-page'])
def test_saved_voice_profile_enables_horse_preview_and_survives_board_reopen(tmp_path, monkeypatch, uncapped, producer, size, instruction, occupied):
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
    settings.update(IMAGE_PROVIDER=producer, GOOGLE_IMAGE_SIZE=size if producer == 'gemini' else '1K',
                    GOOGLE_IMAGE_ASPECT_RATIO='4:3', GOOGLE_IMAGE_THINKING='high',
                    OPENAI_API_KEY='fixture-openai-secret', IMAGE_ESTIMATE_AUD_CENTS='125')
    if producer == 'gemini':
        settings[f'GOOGLE_IMAGE_ESTIMATE_{size}_AUD_CENTS'] = '125'
    if uncapped:
        settings.update(IMAGE_SPENDING_UNCAPPED='1', MEDIA_SYNC_ENABLED='0',
                        MEDIA_SERVER_URL='', MEDIA_SERVER_TOKEN='', GOOGLE_IMAGE_ESTIMATE_1K_AUD_CENTS='')
    companion_settings.save_settings(settings, profile)
    assert 'fixture-google-secret' not in (profile / 'settings.json').read_text()
    provider, ledger = FixtureImageProvider(producer), FixtureLedger()
    monkeypatch.setattr(ui, 'create_resource_service', lambda library, config:
                        None if truthy(config.get('LOCAL_ONLY')) else
                        MediaService(library.media, config, None if uncapped else ledger, provider=provider))
    monkeypatch.setattr(PrimaryBoardComposer, 'complete', lambda *_:
                        (_ for _ in ()).throw(AssertionError('A plain image request must not need model classification')))

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
        if occupied:
            old_bytes = io.BytesIO()
            Image.new('RGB', (160, 120), '#335577').save(old_bytes, 'PNG')
            old = panel.lesson_media.import_bytes(old_bytes.getvalue(), 'Previous image',
                source={'attribution': 'Required previous-image attribution'})
            view = board.session.teacher_view()
            board.session.teacher_apply([
                {'op': 'add_object', 'page_id': view['page_id'], 'object': new_object('image',
                    image_ref={key: old[key] for key in ('asset_id', 'version_id', 'sha256')})},
                {'op': 'add_object', 'page_id': view['page_id'], 'object': new_object('text', text='Existing teaching work')},
            ], expected_revision=view['revision'], expected_token=view['token'])
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
        panel.instruction.setPlainText(instruction)
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
        if occupied:
            assert 'whole_page_replacement' in state['confirmation_reasons']
        assert board.session.pupil_view()['document'] == before
        assert len(provider.calls) == 1
        assert provider.calls[0][0] == 'horse'
        options = provider.calls[0][1]['options']
        assert options['size'] == size
        assert options['aspect_ratio'] == ('4:3' if producer == 'gemini' else '1:1')
        assert options.get('thinking', options.get('quality')) == 'high'
        if uncapped:
            assert ledger.reserved == ledger.committed == []
        else:
            assert ledger.reserved == ledger.committed and len(ledger.reserved) == 1
            assert ledger.reserved[0][1] == 125
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
