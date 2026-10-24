"""Safe feedback, explicit hotkeys and preservation of pending work."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from device_feedback import DeviceFeedback, display_text, frame, snapshot
from hotkey_state import HotkeyState

def test_feedback_frame_is_bounded_ascii_and_excludes_control_syntax():
    encoded=frame('a'*24,1,{'state':'image_ready','title':'Water cycle |\nCP1? wrong','detail':'é'*100})
    fields=encoded.decode().strip().split('|')
    assert len(fields)==6 and len(fields[4])<=27 and len(fields[5])<=33
    assert encoded.count(b'\n')==1 and encoded.isascii()

@pytest.mark.parametrize('nonce,seq,state',[('bad',1,'idle'),('a'*24,0,'idle'),('a'*24,1,'erase'),('a'*24,10**9,'idle')])
def test_invalid_frames_never_reach_serial(nonce,seq,state):
    with pytest.raises(ValueError):frame(nonce,seq,{'state':state})

def test_pending_text_is_only_described_generically():
    result=snapshot(SimpleNamespace(pending_ready_payload='PRIVATE STUDENT WRITING',pending_media=None))
    assert result['state']=='text_ready'
    assert 'PRIVATE' not in str(result)

def test_ready_images_use_explicit_queued_version_and_never_selected_draft():
    app=SimpleNamespace(pending_media={'title':'Reviewed cycle'},pending_ready_payload=None,
                        media_panel=SimpleNamespace(selected={'title':'Unreviewed draft'},prepared_job=None))
    assert snapshot(app)['detail']=='Reviewed cycle'
    app.pending_media=None
    # A selection is edit context, not a pending operation. After Paste Ready
    # clears the queue, the handheld must allow another recording immediately.
    assert snapshot(app)['state']=='idle'

def test_busy_generation_is_not_advertised_as_ready():
    app=SimpleNamespace(media_panel=SimpleNamespace(_busy=True,_generation_job_id='synthetic',_generation_started=0),pending_ready_payload=None)
    assert snapshot(app)['state']=='working'

def test_prepared_image_brief_still_requires_review_before_another_recording():
    app=SimpleNamespace(pending_media=None,pending_ready_payload=None,
                        media_panel=SimpleNamespace(_busy=False,prepared_job='prepared',selected={'title':'Selected image'}))
    assert snapshot(app)['state']=='review'

def test_recording_uses_explicit_image_mode_without_transcript():
    assert snapshot(SimpleNamespace(is_recording=True,recording_mode='media'))['state']=='record_media'

@pytest.mark.parametrize('port,identity',[('auto','a'*12),('COM0','a'*12),('COM5','secret'),('socket://host:23','a'*12)])
def test_no_device_scanning_or_network_port(port,identity):
    with pytest.raises(ValueError):DeviceFeedback(port,identity,start=False)

def test_expected_nonce_and_registered_identity_are_required():
    link=DeviceFeedback('COM5','a'*12,start=False)
    connection=Mock()
    connection.readline.return_value=b'CP1! '+b'b'*24+b' '+b'a'*12+b' page7-v1\n'
    link._handshake(connection,'b'*24)
    connection.readline.return_value=b'CP1! '+b'b'*24+b' '+b'c'*12+b' page7-v1\n'
    with pytest.raises(ValueError):link._handshake(connection,'b'*24)

def test_serial_opens_with_reset_lines_disabled():
    connection=Mock();factory=Mock(return_value=connection)
    link=DeviceFeedback('COM5','a'*12,start=False,serial_factory=factory)
    assert link._open() is connection
    assert connection.dtr is False and connection.rts is False and connection.port=='COM5'
    connection.open.assert_called_once()

@pytest.mark.parametrize('mode,extended,standard',[('media',0x7f,0x77),('library',0x80,0x76)])
def test_new_keys_coalesce_extended_and_fallback_chords(mode,extended,standard):
    state=HotkeyState();keys={0x11,0x10,0x12,extended,standard}
    assert state.update(keys.__contains__)==[(mode,'down')]
    keys.remove(extended)
    assert state.update(keys.__contains__)==[]
    keys.clear()
    assert state.update(keys.__contains__)==[(mode,'up')]

def test_compose_refuses_to_replace_pending_text_before_opening_microphone():
    from compose_gui import ComposeApp
    app=SimpleNamespace(is_recording=False,_busy=False,_settings_saving=lambda:False,
                        pending_ready_payload='Preserved writing',pending_media=None,set_status=Mock(),audio_capture=Mock())
    ComposeApp.start_recording_flow(app,'compose')
    app.audio_capture.start_recording.assert_not_called()
    assert app.pending_ready_payload=='Preserved writing'

def test_image_hotkey_has_its_own_recording_mode_and_library_is_one_shot():
    from compose_gui import ComposeApp
    app=SimpleNamespace(_settings_saving=lambda:False,log=Mock(),is_recording=False,start_recording_flow=Mock(),
                        media_tab=object(),tabs=Mock(),root=Mock(),media_panel=Mock())
    ComposeApp._handle_hardware_event(app,'media','down')
    app.start_recording_flow.assert_called_once_with('media')
    ComposeApp._handle_hardware_event(app,'library','down')
    ComposeApp._handle_hardware_event(app,'library','up')
    app.media_panel.refresh.assert_called_once()


def test_real_worker_handshake_feedback_ack_and_private_audit(tmp_path):
    import json
    import queue
    import time
    class Serial:
        def __init__(self):self.lines=queue.Queue();self.writes=[];self.closed=False
        def open(self):pass
        def close(self):self.closed=True
        def write(self,data):
            self.writes.append(data)
            if data.startswith(b'CP1? '):
                nonce=data.strip().split()[1]
                self.lines.put(b'CP1! '+nonce+b' '+b'a'*12+b' page7-v1\n')
            elif data.startswith(b'CP1|'):
                parts=data.strip().split(b'|')
                self.lines.put(b'CP1+ '+parts[1]+b' '+parts[2]+b' 7\n')
        def readline(self,size):
            try:return self.lines.get(timeout=.05)
            except queue.Empty:return b''
    serial=Serial();audit=tmp_path/'feedback.jsonl'
    link=DeviceFeedback('COM5','a'*12,serial_factory=lambda **_:serial,audit_path=audit)
    try:
        link.submit({'state':'image_ready','title':'Image ready','detail':'Water cycle','ignored':'PRIVATE EXTRA'})
        deadline=time.monotonic()+2
        while link.status()!='USB feedback linked' and time.monotonic()<deadline:time.sleep(.01)
        assert link.status()=='USB feedback linked'
    finally:link.close()
    assert serial.closed and b'page 7\n' in serial.writes
    events=[json.loads(line) for line in audit.read_text().splitlines()]
    assert any(e['event']=='device_page_acknowledged' and e['page']==7 for e in events)
    assert 'a'*12 not in audit.read_text() and 'PRIVATE EXTRA' not in audit.read_text()


def test_restart_restores_only_one_explicit_undispatched_image_queue(tmp_path):
    import base64
    from compose_gui import ComposeApp
    from media_store import MediaStore
    from gemini_fixtures import PNG_BASE64
    store=MediaStore(tmp_path)
    version=store.import_bytes(base64.b64decode(PNG_BASE64),title='Reviewed queued image')
    job=store.create_job('insert','Explicit image queue')
    store.update_job(job['job_id'],'insert_queued',version_id=version['version_id'])
    app=SimpleNamespace(_stop_poller=False,pending_media=None,pending_ready_payload=None,media_store=store,
                        media_panel=Mock(),_report_image_status=Mock())
    ComposeApp._restore_queued_image(app)
    assert app.pending_media['version_id']==version['version_id'] and app.pending_media_job==job['job_id']
    app.media_panel.show_version.assert_called_once()
    assert store.get_job(job['job_id'])['phase']=='insert_queued'
    app.pending_media=None;store.update_job(job['job_id'],'needs_recovery')
    ComposeApp._restore_queued_image(app)
    assert app.pending_media is None
