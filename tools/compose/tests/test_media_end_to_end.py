"""One synthetic image through jobs, shared budget, private API and two caches."""
import io,sys,threading
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'server'))
from history_store import HistoryStore
from media_store import MediaStore
from media_service import MediaService
from media_sync import SyncClient
from media_library_server import create_server


def test_image_workflow_two_desktops_and_offline_cache_without_history_sync(tmp_path):
    server=create_server('127.0.0.1',0,'synthetic-integration-token',tmp_path/'server')
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=f'http://127.0.0.1:{server.server_port}'
    a,b=MediaStore(tmp_path/'A'),MediaStore(tmp_path/'B')
    history=HistoryStore(tmp_path/'A'/'companion.sqlite3')
    history.add_entry('ask','Private synthetic History request','Private synthetic History response')
    ca=SyncClient(a,url,'synthetic-integration-token',allow_private_sync=True)
    cb=SyncClient(b,url,'synthetic-integration-token',allow_private_sync=True)
    output=io.BytesIO();Image.new('RGB',(32,24),'blue').save(output,'PNG')
    class SyntheticImageProvider:
        def generate(self,prompt,parent=None):
            # The reservation is frozen before the possibly billable dispatch.
            assert ca.budget_status()['spent_or_uncertain_cents']==100
            return {'data':output.getvalue(),'source':{'provider':'synthetic','model':'fixture'}}
    try:
        app=MediaService(a,{'IMAGE_GENERATION_ENABLED':'1','IMAGE_ESTIMATE_AUD_CENTS':'100'},ca,provider=SyntheticImageProvider())
        job=app.prepare_generation('Private synthetic generation prompt','Water cycle')
        version=app.generate(job['job_id'])
        assert a.get_job(job['job_id'])['phase']=='preview_ready'
        assert a.get_asset(version['asset_id'])['canonical_version_id'] is None
        a.set_canonical(version['asset_id'],version['version_id'],canonical_title='Our water cycle')
        assert not ca.sync_once()['conflicts']
        cb.sync_once()
        found=b.list_assets('our water cycle')
        assert len(found)==1 and found[0]['version_id']==version['version_id']
        assert b.blob_path(found[0]['sha256']).read_bytes()==output.getvalue()
        assert b.list_jobs()==[]
        assert b.pending_events()==[]
        assert not (tmp_path/'B'/'companion.sqlite3').exists()
        server_bytes=b''.join(path.read_bytes() for path in (tmp_path/'server').rglob('*.sqlite3*'))
        assert b'Private synthetic generation prompt' not in server_bytes
        assert b'Private synthetic History request' not in server_bytes
        assert len(history.list_entries())==1
        cb.local_only=True
        assert cb.sync_once()['local_only']
        assert MediaStore(tmp_path/'B').get_version(version['version_id'])
        backup=a.export_backup(tmp_path/'backup')
        restored=MediaStore.restore_backup(backup,tmp_path/'restored')
        assert restored.blob_path(version['sha256']).read_bytes()==output.getvalue()
    finally:
        ca.close();cb.close();server.shutdown();server.server_close();thread.join(2)
