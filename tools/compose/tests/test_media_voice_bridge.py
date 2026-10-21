import sys,uuid
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from media_store import MediaStore
from media_voice_bridge import VoiceBridge,forward_transcript


def test_handheld_transcript_is_durable_idempotent_and_local_only(tmp_path):
    store=MediaStore(tmp_path)
    bridge=VoiceBridge(store)
    identity=str(uuid.uuid4())
    try:
        assert forward_transcript(bridge.url,bridge.token,'Find our water cycle image',identity)==identity
        forward_transcript(bridge.url,bridge.token,'Find our water cycle image',identity)
        assert len(store.list_jobs())==1
        assert store.get_job(identity)['phase']=='queued'
        assert store.pending_events()==[]
        with pytest.raises(Exception):forward_transcript(bridge.url,'wrong','Fixture')
        with pytest.raises(Exception):forward_transcript(bridge.url,bridge.token,'Changed request',identity)
        assert len(store.list_jobs())==1
    finally:bridge.close()


def test_handoff_rejects_remote_endpoint_without_network_io():
    with pytest.raises(ValueError):forward_transcript('http://example.invalid/v1/media-requests','secret','Fixture')
