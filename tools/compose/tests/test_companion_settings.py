import sys,json
import subprocess
from pathlib import Path
import os
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


def test_hermes_token_is_protected_and_url_is_public(tmp_path):
    def crypt(data,decrypt=False):return data[7:] if decrypt else b'SEALED:'+data
    with patch.object(settings,'_crypt',side_effect=crypt):
        settings.save_settings({'HERMES_URL':'https://fixture.invalid','HERMES_TOKEN':'hermes-secret'},tmp_path)
        public=(tmp_path/'settings.json').read_text()
        sealed=(tmp_path/'credentials.dpapi').read_bytes()
        loaded=settings.load_settings(tmp_path)
    assert 'https://fixture.invalid' in public
    assert 'hermes-secret' not in public
    assert sealed.startswith(b'SEALED:')
    assert loaded['HERMES_TOKEN']=='hermes-secret'


def test_second_file_write_failure_restores_previous_public_and_protected_settings(tmp_path):
    def crypt(data, decrypt=False):return data[7:] if decrypt else b'SEALED:'+data
    with patch.object(settings,'_crypt',side_effect=crypt):
        settings.save_settings({'MEDIA_SERVER_URL':'https://old.invalid','MEDIA_SERVER_TOKEN':'old-secret'},tmp_path)
        old_public=(tmp_path/'settings.json').read_bytes()
        old_secret=(tmp_path/'credentials.dpapi').read_bytes()
        atomic_write=settings._atomic_write
        failed=False
        def fail_new_public(path,data):
            nonlocal failed
            if Path(path).name=='settings.json' and b'https://new.invalid' in data and not failed:
                failed=True
                raise OSError('fixture second-file write failure')
            return atomic_write(path,data)
        with patch.object(settings,'_atomic_write',side_effect=fail_new_public):
            with pytest.raises(OSError):
                settings.save_settings({'MEDIA_SERVER_URL':'https://new.invalid','MEDIA_SERVER_TOKEN':'new-secret'},tmp_path)
        assert failed
        assert (tmp_path/'settings.json').read_bytes()==old_public
        assert (tmp_path/'credentials.dpapi').read_bytes()==old_secret
        assert settings.load_settings(tmp_path)['MEDIA_SERVER_TOKEN']=='old-secret'


def test_load_recovers_previous_pair_after_process_dies_during_rollback(tmp_path):
    def crypt(data, decrypt=False):return data[7:] if decrypt else b'SEALED:'+data
    with patch.object(settings,'_crypt',side_effect=crypt):
        settings.save_settings({'MEDIA_SERVER_URL':'https://old.invalid','MEDIA_SERVER_TOKEN':'old-secret'},tmp_path)
        old_public=(tmp_path/'settings.json').read_bytes()
        old_secret=(tmp_path/'credentials.dpapi').read_bytes()
        atomic_write=settings._atomic_write
        def fail_both_public_writes(path,data):
            if Path(path).name=='settings.json':
                raise OSError('simulated process interruption before rollback completes')
            return atomic_write(path,data)
        with patch.object(settings,'_atomic_write',side_effect=fail_both_public_writes):
            with pytest.raises(RuntimeError,match='recovery'):
                settings.save_settings({'MEDIA_SERVER_URL':'https://new.invalid','MEDIA_SERVER_TOKEN':'new-secret'},tmp_path)
        assert (tmp_path/'.settings-transaction.json').exists()
        assert settings.load_settings(tmp_path)['MEDIA_SERVER_TOKEN']=='old-secret'
        assert (tmp_path/'settings.json').read_bytes()==old_public
        assert (tmp_path/'credentials.dpapi').read_bytes()==old_secret
        assert not (tmp_path/'.settings-transaction.json').exists()


def test_process_death_releases_settings_lock(tmp_path):
    module_dir=Path(settings.__file__).resolve().parent
    child=("import os,sys; from pathlib import Path; "
           f"sys.path.insert(0,{str(module_dir)!r}); import companion_settings as s; "
           "lock=s._settings_lock(Path(sys.argv[1])); lock.__enter__(); "
           "print('locked',flush=True); os._exit(0)")
    acquired=subprocess.run([sys.executable,'-c',child,str(tmp_path)],capture_output=True,text=True,timeout=5)
    assert acquired.returncode==0 and acquired.stdout.strip()=='locked'
    reader=("import sys; from pathlib import Path; "
            f"sys.path.insert(0,{str(module_dir)!r}); import companion_settings as s; "
            "assert s.load_settings(Path(sys.argv[1])) == {}")
    completed=subprocess.run([sys.executable,'-c',reader,str(tmp_path)],capture_output=True,text=True,timeout=5)
    assert completed.returncode==0,completed.stderr
