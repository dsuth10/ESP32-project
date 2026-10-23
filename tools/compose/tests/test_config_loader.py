"""Shared core configuration must preserve feature isolation and protected settings."""
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config_loader import load_env_config


def test_fallback_files_supply_groq_without_enabling_other_services(tmp_path):
    fallback = tmp_path / 'fallback.env'
    fallback.write_text('GROQ_API_KEY=synthetic-fallback\nESP32_START_RECEIVER=1\n'
                        'HERMES_ENABLED=1\nMEDIA_SYNC_ENABLED=1\n'
                        'HERMES_TOKEN=synthetic-plaintext\n', encoding='utf-8')
    compose = tmp_path / 'compose.env'
    compose.write_text('GROQ_API_KEY=\n', encoding='utf-8')
    with patch('config_loader.fallback_env_paths', return_value=[fallback, compose]), \
         patch.dict('os.environ', {}, clear=True):
        cfg = load_env_config(defaults={'ESP32_START_RECEIVER': '0', 'ESP32_ENABLE_HOTKEYS': '0'})
    assert cfg == {'GROQ_API_KEY': 'synthetic-fallback',
                   'ESP32_START_RECEIVER': '0', 'ESP32_ENABLE_HOTKEYS': '0'}


def test_protected_settings_override_files_and_process_overrides_remain_supported(tmp_path):
    compose = tmp_path / 'compose.env'
    compose.write_text('GROQ_API_KEY=synthetic-file\nHERMES_TOKEN=synthetic-plaintext\n'
                       'LOCAL_ONLY=0\n', encoding='utf-8')
    protected = {'GROQ_API_KEY': 'synthetic-protected', 'HERMES_TOKEN': 'synthetic-sealed',
                 'LOCAL_ONLY': '1', 'MEDIA_SERVER_TOKEN': 'synthetic-media'}
    with patch('config_loader.fallback_env_paths', return_value=[compose]), \
         patch.dict('os.environ', {'GROQ_ASSISTANT_MODEL': 'synthetic-model',
                                   'HERMES_TOKEN': 'synthetic-process'}, clear=True):
        cfg = load_env_config(settings_loader=lambda: protected)
    assert cfg['GROQ_API_KEY'] == 'synthetic-protected'
    assert cfg['HERMES_TOKEN'] == 'synthetic-sealed'
    assert cfg['MEDIA_SERVER_TOKEN'] == 'synthetic-media'
    assert cfg['LOCAL_ONLY'] == '1'
    assert cfg['GROQ_ASSISTANT_MODEL'] == 'synthetic-model'


def test_unavailable_protected_storage_keeps_offline_defaults(tmp_path):
    with patch('config_loader.fallback_env_paths', return_value=[tmp_path / 'missing.env']), \
         patch.dict('os.environ', {}, clear=True):
        def unavailable():
            raise OSError('synthetic access failure')
        cfg = load_env_config(settings_loader=unavailable, defaults={'LOCAL_ONLY': '1'})
    assert cfg == {'LOCAL_ONLY': '1'}


def test_environment_overrides_protected_value_without_exposing_hermes_token(tmp_path):
    with patch('config_loader.fallback_env_paths', return_value=[tmp_path / 'missing.env']), \
         patch.dict('os.environ', {'GROQ_API_KEY': 'synthetic-process',
                                   'HERMES_TOKEN': 'synthetic-plaintext'}, clear=True):
        cfg = load_env_config(settings_loader=lambda: {'GROQ_API_KEY': 'synthetic-protected'})
    assert cfg['GROQ_API_KEY'] == 'synthetic-process'
    assert 'HERMES_TOKEN' not in cfg
