import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_safety as safety


def partition_table(app_size=0x140000):
    rows = b""
    for name, kind, subtype, offset, size in [
        (b"nvs", 1, 2, 0x9000, 0x5000), (b"otadata", 1, 0, 0xe000, 0x2000),
        (b"app0", 0, 16, 0x10000, app_size),
    ]:
        rows += struct.pack("<HBBII16sI", 0x50aa, kind, subtype, offset, size, name, 0)
    rows += b"\xeb\xeb" + b"\xff"*14 + hashlib.md5(rows).digest()
    return rows.ljust(4096, b"\xff")


class FakeConnection:
    identity = {"chip": "ESP32", "flash": 4194304, "mac": "11:22:33:44:55:66"}
    writes = []
    tables = []
    table_bytes = partition_table()

    def __init__(self, port): self.port = port
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def table(self):
        self.tables.append(True)
        return self.table_bytes
    def write(self, images): self.writes.append(images)


class GuardTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[2] / '.local/board-safety-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        FakeConnection.writes = []
        FakeConnection.tables = []
        FakeConnection.identity = {"chip": "ESP32", "flash": 4194304, "mac": "11:22:33:44:55:66"}
        FakeConnection.table_bytes = partition_table()
        self.registry = self.root/'registry.json'
        self.record = {"schema": 1, "devices": {"11:22:33:44:55:66": {
            "profile": "cyd-2432s028", "chip": "ESP32", "flash": 4194304,
            "label": "test-cyd", "role": "test", "partition_sha256": safety.sha(partition_table())}}}
        self.save_registry()
        firmware = bytearray(256);firmware[0]=0xe9;firmware[3]=0x20
        (self.root/'firmware.bin').write_bytes(firmware)
        (self.root/'platformio.ini').write_text('test build inputs')
        self.manifest = self.root/'board-upload.json'
        self.payload = {"schema": 1, "profile": "cyd-2432s028", "environment": "cyd-identify",
                        "images": [{"role": "application", "offset": 0x10000, "path": "firmware.bin",
                                    "size": 256, "sha256": safety.sha(firmware)}],
                        "inputs": [{"path": "platformio.ini", "sha256": safety.sha((self.root/'platformio.ini').read_bytes())}]}
        self.save_manifest()

    def save_registry(self): self.registry.write_text(json.dumps(self.record))
    def save_manifest(self): self.manifest.write_text(json.dumps(self.payload))
    def upload(self, **kwargs):
        safety.guarded_upload("cyd-2432s028", "COM6", self.manifest, self.registry, connect=FakeConnection, **kwargs)
    def refused(self):
        with self.assertRaises(safety.SafetyError): self.upload()
        self.assertEqual(FakeConnection.writes, [])

    def test_matching_board_writes_exact_loaded_bytes(self):
        self.upload()
        self.assertEqual(FakeConnection.writes, [[(0x10000, (self.root/'firmware.bin').read_bytes())]])

    def test_check_only_never_writes(self):
        self.upload(check_only=True)
        self.assertTrue(FakeConnection.tables)
        self.assertEqual(FakeConnection.writes, [])

    def test_same_processor_different_physical_board_refused(self):
        FakeConnection.identity['mac'] = '22:22:33:44:55:66';self.refused()

    def test_other_processor_refused(self):
        FakeConnection.identity['chip'] = 'ESP32-S3';self.refused()

    def test_other_flash_capacity_refused(self):
        FakeConnection.identity['flash'] = 16777216;self.refused()

    def test_changed_registered_partition_refused(self):
        FakeConnection.table_bytes = partition_table().replace(b'nvs', b'NVs', 1);self.refused()

    def test_valid_but_different_partition_fingerprint_refused(self):
        FakeConnection.table_bytes = partition_table()[:-1]+b'\x00';self.refused()

    def test_unreadable_device_never_writes(self):
        class Unreadable(FakeConnection):
            def table(self): raise OSError('Disconnected')
        with self.assertRaises(OSError):
            safety.guarded_upload('cyd-2432s028','COM6',self.manifest,self.registry,connect=Unreadable)
        self.assertEqual(FakeConnection.writes, [])

    def test_stable_device_write_locked_but_checks_allowed(self):
        self.record['devices']['11:22:33:44:55:66']['role']='stable';self.save_registry();self.refused()
        self.upload(check_only=True)

    def test_legacy_registration_defaults_stable(self):
        del self.record['devices']['11:22:33:44:55:66']['role'];self.save_registry();self.refused()

    def test_unmatched_profile_refused(self):
        self.payload['profile']='es3c28p-s3';self.save_manifest();self.refused()

    def test_wrong_image_processor_refused(self):
        data=bytearray((self.root/'firmware.bin').read_bytes());data[12]=9
        (self.root/'firmware.bin').write_bytes(data);self.payload['images'][0]['sha256']=safety.sha(data)
        self.save_manifest();self.refused()

    def test_modified_firmware_refused(self):
        (self.root/'firmware.bin').write_bytes(b'x'*256);self.refused()

    def test_wrong_image_flash_header_refused(self):
        data=bytearray((self.root/'firmware.bin').read_bytes());data[3]=0x40
        (self.root/'firmware.bin').write_bytes(data);self.payload['images'][0]['sha256']=safety.sha(data)
        self.save_manifest();self.refused()

    def test_modified_build_settings_refused(self):
        (self.root/'platformio.ini').write_text('different build');self.refused()

    def test_missing_registry_refused(self):
        self.registry.unlink();self.refused()

    def test_malformed_registry_refused(self):
        self.registry.write_text('{}');self.refused()

    def test_missing_manifest_refused(self):
        self.manifest.unlink();self.refused()

    def test_wrong_offset_refused(self):
        self.payload['images'][0]['offset']=0;self.save_manifest();self.refused()

    def test_missing_or_duplicate_images_refused(self):
        original=copy.deepcopy(self.payload)
        for images in [[], self.payload['images']*2]:
            self.payload=copy.deepcopy(original);self.payload['images']=images;self.save_manifest();self.refused()

    def test_overlarge_image_refused(self):
        data=b'\xe9'+b'\x00'*0x140000;(self.root/'firmware.bin').write_bytes(data)
        self.payload['images'][0].update(size=len(data),sha256=safety.sha(data));self.save_manifest();self.refused()

    def test_no_automatic_or_network_ports(self):
        for port in ['',None,'auto','socket://localhost:1234','COM0','COM6 COM5']:
            with self.subTest(port=port),self.assertRaises(safety.SafetyError):safety.check_port(port)

    def test_explicit_ports(self):
        for port in ['COM5','COM6','/dev/ttyUSB0','/dev/cu.usbserial-1']:safety.check_port(port)

    def test_cannot_register_wrong_hardware(self):
        with self.assertRaises(safety.SafetyError):
            safety.register('es3c28p-s3','COM6','bad',self.registry,connect=FakeConnection)
        self.assertEqual(safety.load_registry(self.registry),self.record)

    def test_registration_cannot_unlock_stable(self):
        self.record['devices']['11:22:33:44:55:66']['role']='stable';self.save_registry()
        with self.assertRaises(safety.SafetyError):
            safety.register('cyd-2432s028','COM6','test',self.registry,connect=FakeConnection,role='test')
        self.assertEqual(safety.load_registry(self.registry),self.record)

    def test_guard_uses_single_connection_and_preloaded_bytes(self):
        calls=[]
        class Mutating(FakeConnection):
            def __enter__(inner):
                calls.append(inner.port)
                (self.root/'firmware.bin').write_bytes(b'changed after load')
                return inner
        safety.guarded_upload('cyd-2432s028','COM6',self.manifest,self.registry,connect=Mutating)
        self.assertEqual(calls,['COM6'])
        self.assertEqual(len(FakeConnection.writes[0][0][1]),256)


if __name__=='__main__':unittest.main()
