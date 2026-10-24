import io,queue,sys
from pathlib import Path
from unittest.mock import Mock,patch
import pytest
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from compose_gui import ComposeApp
from media_store import MediaStore


def fixture_app(tmp_path):
    app=ComposeApp.__new__(ComposeApp)
    app._busy=False;app.is_recording=False;app._stop_poller=False
    app._ui_events=queue.Queue();app.pending_ready_payload=None
    app.pending_media=app.pending_media_job=None
    app.media_store=MediaStore(tmp_path)
    app.media_panel=Mock();app.log=Mock();app.set_status=Mock()
    data=io.BytesIO();Image.new('RGB',(8,8),'blue').save(data,'PNG')
    version=app.media_store.import_bytes(data.getvalue(),'Fixture image')
    return app,version


def test_live_retrieved_image_inserts_only_at_original_word_target(tmp_path):
    app,version=fixture_app(tmp_path)
    target={'hwnd':3,'pid':4,'executable':'WINWORD.EXE','document':'Synthetic.docx','start':2,'end':2}
    receipt={'message':'Synthetic picture returned','verification':'fixture'}
    with patch('media_targets.capture_target',return_value=dict(target)),patch('media_targets.insert_image',return_value=receipt) as insert:
        app._queue_media(version,target=target)
    insert.assert_called_once()
    assert app.pending_media is None
    assert app.media_store.list_jobs()[0]['phase']=='completed'


def test_changed_live_caret_retains_image_without_insertion(tmp_path):
    app,version=fixture_app(tmp_path)
    target={'hwnd':3,'pid':4,'executable':'WINWORD.EXE','document':'Synthetic.docx','start':2,'end':2}
    with patch('media_targets.capture_target',return_value={**target,'start':7,'end':7}),patch('media_targets.insert_image') as insert:
        app._queue_media(version,target=target)
    insert.assert_not_called()
    assert app.pending_media['version_id']==version['version_id']
    assert app.media_store.get_job(app.pending_media_job)['phase']=='insert_queued'


def test_uncertain_insertion_cannot_repeat_through_paste_ready(tmp_path):
    app,version=fixture_app(tmp_path)
    app._queue_media(version)
    target={'hwnd':3,'pid':4,'executable':'WINWORD.EXE'}
    with patch('media_targets.capture_target',return_value=target),patch('media_targets.insert_image',side_effect=RuntimeError('fixture uncertain')) as insert:
        app.inject_paste_ui();app.inject_paste_ui()
    assert insert.call_count==1
    assert app.pending_media is None
    assert app.media_store.list_jobs()[0]['phase']=='needs_recovery'


def test_queue_does_not_discard_existing_text(tmp_path):
    app,version=fixture_app(tmp_path);app.pending_ready_payload='Retain fixture text'
    with pytest.raises(ValueError):app._queue_media(version)
    assert app.pending_ready_payload=='Retain fixture text'
    assert app.media_store.list_jobs()==[]


def test_media_microphone_routes_transcript_to_media_not_text_paste(tmp_path):
    app,_=fixture_app(tmp_path)
    app.speech_pipeline=Mock();app.speech_pipeline.transcribe.return_value=('Find our image','fixture',0)
    app.llm_pipeline=Mock();app.local_only=True
    app._media_request_target={'hwnd':3,'pid':4,'executable':'WINWORD.EXE'}
    app._process_pipeline_worker('media',b'synthetic-audio',None,'')
    while not app._ui_events.empty():
        callback,args=app._ui_events.get();callback(*args)
    app.media_panel.ask.assert_called_once_with('Find our image',target=app._media_request_target)
    app.llm_pipeline.generate.assert_not_called()
    assert app.pending_ready_payload is None


def test_blocked_onenote_image_shows_feedback_on_visible_media_panel(tmp_path):
    app,version=fixture_app(tmp_path)
    app._queue_media(version)
    message='OneNote selection could not be verified. Use Copy image and paste manually.'
    with patch('media_targets.capture_target',side_effect=ValueError(message)),patch('media_targets.insert_image') as insert:
        app.inject_paste_ui()
    while not app._ui_events.empty():
        callback,args=app._ui_events.get();callback(*args)
    insert.assert_not_called()
    assert app.pending_media['version_id']==version['version_id']
    assert app.media_store.get_job(app.pending_media_job)['phase']=='insert_queued'
    app.media_panel.tell.assert_called_with(message)


def test_uncertain_image_attempt_reports_recovery_on_media_panel(tmp_path):
    app,version=fixture_app(tmp_path)
    app._queue_media(version)
    target={'hwnd':3,'pid':4,'executable':'ONENOTE.EXE','selection_checked':True}
    with patch('media_targets.capture_target',return_value=target),patch('media_targets.insert_image',side_effect=RuntimeError('fixture uncertain')):
        app.inject_paste_ui()
    while not app._ui_events.empty():
        callback,args=app._ui_events.get();callback(*args)
    app.media_panel.tell.assert_called_with('Check the target document before retrying; image attempt needs recovery.')
    assert app.pending_media is None
    assert app.media_store.list_jobs()[0]['phase']=='needs_recovery'


def test_shared_status_updates_independently_of_selected_tab():
    app=ComposeApp.__new__(ComposeApp)
    app.status_lbl=Mock();app.status_dot=Mock()
    app.global_status_lbl=Mock();app.global_status_dot=Mock()
    app._update_status('OneNote selection could not be verified.', '#F59E0B')
    app.global_status_lbl.configure.assert_called_once_with(text='OneNote selection could not be verified.')
    app.global_status_dot.configure.assert_called_once_with(fg='#F59E0B')


def test_keyboard_permission_is_only_granted_for_explicit_paste_ready(tmp_path):
    app,version=fixture_app(tmp_path)
    app._queue_media(version)
    target={'hwnd':3,'pid':4,'executable':'ONENOTE.EXE','explicit_keyboard_paste':True}
    receipt={'verification':'paste_requested','message':'Synthetic paste requested'}
    with patch('media_targets.capture_target',return_value=target) as capture,patch('media_targets.insert_image',return_value=receipt) as insert:
        app.inject_paste_ui()
        app.inject_paste_ui()
    capture.assert_called_once_with(allow_onenote_keyboard_paste=True)
    insert.assert_called_once()
    assert app.pending_media is None


def test_automatic_word_target_does_not_grant_onenote_keyboard_permission(tmp_path):
    app,version=fixture_app(tmp_path)
    target={'hwnd':3,'pid':4,'executable':'WINWORD.EXE','document':'Synthetic.docx','start':2,'end':2}
    with patch('media_targets.capture_target',return_value=target) as capture,patch('media_targets.insert_image',return_value={'message':'Fixture inserted'}):
        app._queue_media(version,target=target)
    capture.assert_called_once_with()
