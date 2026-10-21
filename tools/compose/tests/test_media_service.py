import io
import sys
from pathlib import Path
from unittest.mock import Mock
import pytest
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from media_store import MediaStore
from media_service import MediaService
from media_providers import ProviderFailure


def png(colour='blue'):
    stream=io.BytesIO();Image.new('RGB',(24,24),colour).save(stream,'PNG');return stream.getvalue()


def service(tmp_path,**config):
    store=MediaStore(tmp_path)
    provider=Mock()
    provider.generate.return_value={'data':png(),'source':{'provider':'fixture','model':'test'}}
    sync=Mock()
    return MediaService(store,{'IMAGE_GENERATION_ENABLED':'1','IMAGE_ESTIMATE_AUD_CENTS':'100',**config},sync,provider=provider)


def test_preparation_is_durable_but_never_dispatches_or_reserves(tmp_path):
    app=service(tmp_path)
    job=app.prepare_generation('Make a synthetic water cycle','Water cycle')
    assert MediaStore(tmp_path).get_job(job['job_id'])['phase']=='awaiting_user'
    app.provider.generate.assert_not_called();app.sync.reserve_budget.assert_not_called()


def test_paid_result_previews_and_never_canonicalises_or_inserts(tmp_path):
    app=service(tmp_path)
    job=app.prepare_generation('A synthetic image','Fixture')
    version=app.generate(job['job_id'])
    assert app.store.get_job(job['job_id'])['phase']=='preview_ready'
    assert version['origin']=='generated'
    assert app.store.get_asset(version['asset_id'])['canonical_version_id'] is None
    app.sync.reserve_budget.assert_called_once_with(job['job_id'],100)
    app.sync.commit_budget.assert_called_once_with(job['job_id'],100)
    assert 'A synthetic image' not in str(app.store.pending_events())
    with pytest.raises(ValueError):app.generate(job['job_id'])
    assert app.provider.generate.call_count==1
    assert app.store.get_job(job['job_id'])['phase']=='preview_ready'


def test_refinement_keeps_canonical_and_parent_bytes(tmp_path):
    app=service(tmp_path)
    original=app.store.import_bytes(png('red'),'Water cycle')
    app.store.set_canonical(original['asset_id'],original['version_id'])
    job=app.prepare_generation('Make the arrows blue','Water cycle revision',original['version_id'])
    result=app.generate(job['job_id'])
    assert result['parent_version_id']==original['version_id']
    assert app.store.get_asset(original['asset_id'])['canonical_version_id']==original['version_id']
    assert app.store.blob_path(original['sha256']).read_bytes()==png('red')


def test_ambiguous_paid_timeout_retains_allocation_and_never_retries(tmp_path):
    app=service(tmp_path)
    app.provider.generate.side_effect=TimeoutError('sensitive provider error')
    job=app.prepare_generation('Fixture prompt')
    with pytest.raises(ProviderFailure):app.generate(job['job_id'])
    assert app.store.get_job(job['job_id'])['phase']=='needs_recovery'
    app.sync.release_budget.assert_not_called()
    with pytest.raises(ValueError):app.generate(job['job_id'])
    assert app.provider.generate.call_count==1
    assert app.store.get_job(job['job_id'])['phase']=='needs_recovery'


def test_accounting_ack_failure_keeps_durable_image(tmp_path):
    app=service(tmp_path)
    app.sync.commit_budget.side_effect=TimeoutError()
    job=app.prepare_generation('Fixture')
    result=app.generate(job['job_id'])
    stored=app.store.get_job(job['job_id'])
    assert stored['phase']=='preview_ready'
    assert stored['accounting']=='reservation_held_pending_reconciliation'
    assert app.store.get_version(result['version_id'])
    app.sync.release_budget.assert_not_called()


@pytest.mark.parametrize('config',[{'LOCAL_ONLY':'1'},{'IMAGE_GENERATION_ENABLED':'0'},{'IMAGE_ESTIMATE_AUD_CENTS':'0'}])
def test_policy_blocks_before_dispatch(tmp_path,config):
    app=service(tmp_path,**config)
    job=app.prepare_generation('Fixture')
    with pytest.raises(ValueError):app.generate(job['job_id'])
    app.provider.generate.assert_not_called();app.sync.reserve_budget.assert_not_called()


def test_budget_unreachable_does_not_call_paid_provider(tmp_path):
    app=service(tmp_path);app.sync.reserve_budget.side_effect=TimeoutError()
    job=app.prepare_generation('Fixture')
    with pytest.raises(ValueError):app.generate(job['job_id'])
    app.provider.generate.assert_not_called()


def test_restart_flags_interrupted_dispatch_without_replay(tmp_path):
    app=service(tmp_path)
    job=app.prepare_generation('Fixture')
    app.store.update_job(job['job_id'],'acquiring')
    app.recover_interrupted_jobs()
    assert app.store.get_job(job['job_id'])['phase']=='needs_recovery'
    app.provider.generate.assert_not_called()
