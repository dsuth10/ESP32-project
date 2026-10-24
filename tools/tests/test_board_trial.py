"""Exercise real scoped trial/recovery logic without a physical write."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_safety as safety
import board_trial as trial

def table():
    data=b''
    for name,kind,sub,offset,size in [(b'nvs',1,2,0x9000,0x5000),(b'otadata',1,0,0xe000,0x2000),(b'app0',0,16,0x10000,0x700000)]:
        data+=struct.pack('<HBBII16sI',0x50aa,kind,sub,offset,size,name,0)
    return (data+b'\xeb\xeb'+b'\xff'*14+hashlib.md5(data).digest()).ljust(4096,b'\xff')

class Device:
    identity={'chip':'ESP32-S3','flash':16*1024*1024,'mac':'11:22:33:44:55:66'}
    def __init__(self,port):self.port=port
    def __enter__(self):return self
    def __exit__(self,*_):pass
    def table(self):return bytes(self.flash[0x8000:0x9000])
    def read(self,offset,size):return bytes(self.flash[offset:offset+size])
    def write(self,images):
        self.writes.extend(images)
        for offset,data in images:
            span=(len(data)+4095)//4096*4096
            self.flash[offset:offset+span]=b'\xff'*span
            self.flash[offset:offset+len(data)]=data

class TrialTests(unittest.TestCase):
    def setUp(self):
        parent=Path(__file__).resolve().parents[2]/'.local/board-trial-tests';parent.mkdir(exist_ok=True)
        temp=tempfile.TemporaryDirectory(dir=parent);self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        Device.identity={'chip':'ESP32-S3','flash':16*1024*1024,'mac':'11:22:33:44:55:66'}
        Device.flash=bytearray(b'\xff'*(16*1024*1024));Device.flash[0x8000:0x9000]=table();Device.flash[0x10000:0x11000]=b'o'*4096;Device.writes=[]
        self.registry=self.root/'registry.json'
        self.registry.write_text(json.dumps({'schema':1,'devices':{Device.identity['mac']:{**Device.identity,
            'profile':trial.PROFILE,'label':'original-s3','role':'stable','partition_sha256':safety.sha(table())}}}))
        self.original_registry=self.registry.read_bytes()
        header=bytearray(512);header[0]=0xe9;header[3]=0x40;header[12]=9
        images=[]
        for role,offset,data in [('bootloader',0,header),('partitions',0x8000,table()),('ota_boot',0xe000,b'\xff'*8192),('application',0x10000,header+b'new')]:
            file=self.root/(role+'.bin');file.write_bytes(data)
            images.append({'role':role,'offset':offset,'path':file.name,'size':len(data),'sha256':safety.sha(data)})
        (self.root/'build.ini').write_text('synthetic-build')
        self.manifest=self.root/'candidate.json'
        self.manifest.write_text(json.dumps({'schema':1,'profile':trial.PROFILE,'environment':'esp32-s3-portrait','images':images,
            'inputs':[{'path':'build.ini','sha256':safety.sha((self.root/'build.ini').read_bytes())}]}))
        self.recovery=self.root/'recovery';self.auth=self.root/'authorisation.json'

    def prepare(self):
        trial.backup('COM5',self.recovery,self.registry,connect=Device)
        trial.prepare(self.manifest,self.recovery/'recovery.json',self.auth,'Explicit synthetic human approval for this exact layout trial',self.registry)

    def execute(self,**kw):trial.execute('COM5',self.auth,self.registry,connect=Device,**kw)

    def test_full_backup_application_only_trial_and_executable_restore(self):
        original=bytes(Device.flash);self.prepare();self.execute()
        self.assertEqual(len(Device.writes),1);self.assertEqual(Device.writes[0][0],0x10000)
        self.assertEqual(bytes(Device.flash[:0x10000]),original[:0x10000])
        self.execute(restore=True,check_only=True);self.execute(restore=True)
        self.assertEqual(bytes(Device.flash),original)
        self.assertEqual(self.registry.read_bytes(),self.original_registry)

    def test_normal_guard_still_refuses_stable_after_trial_preparation(self):
        self.prepare()
        with self.assertRaises(safety.SafetyError):safety.guarded_upload(trial.PROFILE,'COM5',self.manifest,self.registry,connect=Device)
        self.assertEqual(Device.writes,[])

    def test_check_never_claims_or_writes(self):
        self.prepare();self.execute(check_only=True)
        self.assertFalse(Path(str(self.auth)+'.dispatch.json').exists());self.assertEqual(Device.writes,[])

    def test_replay_refused_for_trial_and_restore(self):
        self.prepare();self.execute()
        with self.assertRaises(safety.SafetyError):self.execute()
        self.execute(restore=True)
        with self.assertRaises(safety.SafetyError):self.execute(restore=True)
        self.assertEqual(len(Device.writes),2)

    def test_different_physical_s3_refused(self):
        self.prepare();Device.identity={**Device.identity,'mac':'11:22:33:44:55:67'}
        with self.assertRaises(safety.SafetyError):self.execute()
        self.assertEqual(Device.writes,[])

    def test_corrupted_complete_backup_refused(self):
        self.prepare();file=self.recovery/'flash.bin'
        with file.open('r+b') as stream:stream.write(b'x')
        with self.assertRaises(safety.SafetyError):self.execute()
        self.assertEqual(Device.writes,[])

    def test_modified_candidate_refused(self):
        self.prepare();(self.root/'application.bin').write_bytes(b'changed')
        with self.assertRaises(safety.SafetyError):self.execute()
        self.assertEqual(Device.writes,[])

    def test_changed_installed_state_requires_new_recovery(self):
        self.prepare();Device.flash[0x10000]=0
        with self.assertRaises(safety.SafetyError):self.execute()
        self.assertEqual(Device.writes,[])

    def test_runtime_nvs_change_is_preserved_not_replaced_with_old_snapshot(self):
        self.prepare();Device.flash[0x9000]=42
        self.execute();self.execute(restore=True)
        self.assertEqual(Device.flash[0x9000],42)

    def test_missing_trial_cannot_be_restored(self):
        self.prepare()
        with self.assertRaises(safety.SafetyError):self.execute(restore=True)

    def test_recovery_is_available_even_if_candidate_source_lost(self):
        self.prepare();self.execute();(self.root/'application.bin').unlink();self.manifest.unlink()
        self.execute(restore=True)
        self.assertEqual(bytes(Device.flash[0x10000:0x11000]),b'o'*4096)

    def test_failed_write_consumes_permission_before_io(self):
        self.prepare()
        class Failing(Device):
            def write(self,images):raise OSError('synthetic disconnected write')
        with self.assertRaises(OSError):trial.execute('COM5',self.auth,self.registry,connect=Failing)
        with self.assertRaises(safety.SafetyError):self.execute()
        self.execute(restore=True)

    def test_two_different_backup_reads_never_authorise(self):
        class Changing(Device):
            count=0
            def read(self,offset,size):
                self.count+=1
                return super().read(offset,size) if self.count==1 else b'x'*size
        with self.assertRaises(safety.SafetyError):trial.backup('COM5',self.recovery,self.registry,connect=Changing)
        self.assertFalse((self.recovery/'recovery.json').exists())

if __name__=='__main__':unittest.main()
