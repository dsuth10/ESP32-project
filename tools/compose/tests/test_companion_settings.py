import sys,json
from pathlib import Path
from unittest.mock import patch
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import companion_settings as settings


def test_settings_do_not_save_credentials_in_plain_json(tmp_path):
    # Deterministic stand-in verifies separation; a separate Windows smoke check
    # exercises real DPAPI without ever touching the user's configured keys.
    def crypt(data,decrypt=False):return data[7:] if decrypt else b'SEALED:'+data
    with patch.object(settings,'_crypt',side_effect=crypt):
        settings.save_settings({'MEDIA_SERVER_URL':'https://fixture.invalid','MEDIA_SERVER_TOKEN':'synthetic-secret','unrecognised':'discard'},tmp_path)
        public=(tmp_path/'settings.json').read_text()
        assert 'synthetic-secret' not in public
        assert 'unrecognised' not in public
        assert settings.load_settings(tmp_path)['MEDIA_SERVER_TOKEN']=='synthetic-secret'


def test_encryption_failure_does_not_save_plaintext_fallback(tmp_path):
    with patch.object(settings,'_crypt',side_effect=RuntimeError('fixture failure')):
        with pytest.raises(RuntimeError):settings.save_settings({'OPENAI_API_KEY':'synthetic-secret'},tmp_path)
    assert not (tmp_path/'credentials.dpapi').exists()
    assert not (tmp_path/'settings.json').exists()


def test_clearing_credential_removes_encrypted_file(tmp_path):
    def crypt(data,decrypt=False):return data[7:] if decrypt else b'SEALED:'+data
    with patch.object(settings,'_crypt',side_effect=crypt):
        settings.save_settings({'OPENAI_API_KEY':'fixture'},tmp_path)
        settings.save_settings({'OPENAI_API_KEY':''},tmp_path)
    assert not (tmp_path/'credentials.dpapi').exists()
