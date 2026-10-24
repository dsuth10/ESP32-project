"""Single-candidate S3 application trial and recovery; stable registration never changes.

Only application bytes are written. Bootloader, partitions, OTA selection, NVS
and filesystems are preserved. Receipts and complete flash backups are private.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from board_safety import (EspConnection, SafetyError, check_port, load_manifest, load_registry,
                          registry_path, require, sha, validate_identity, validate_partition_table)

PROFILE = 'es3c28p-s3'

def save_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())

class TrialConnection(EspConnection):
    def read(self, offset, size):
        self.table()  # Establish the tested RAM stub; does not change flash.
        self.esp.change_baud(460800)
        return self.api.read_flash(self.esp, offset, size, no_progress=True)

def checked_device(device, registry):
    entry = validate_identity(device.identity, PROFILE, registry)
    require(entry.get('role','stable') == 'stable', 'Trial requires the original stable S3 registration.')
    table = device.table()
    validate_partition_table(table, PROFILE)
    require(sha(table) == entry['partition_sha256'], 'Partition fingerprint changed; trial refused.')
    return entry

def backup(port, destination, registry_file, connect=TrialConnection):
    check_port(port)
    registry = load_registry(Path(registry_file))
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    with connect(port) as device:
        entry = checked_device(device, registry)
        size = device.identity['flash']
        print('Reading the complete 16 MiB recovery image; no flash write.', flush=True)
        first = device.read(0, size)
        require(len(first) == size, 'Incomplete recovery read.')
        with (destination / 'flash.bin').open('xb') as stream:
            stream.write(first); stream.flush(); os.fsync(stream.fileno())
        print('Verifying against a second complete device read.', flush=True)
        second = device.read(0, size)
        require(len(second) == size and sha(first) == sha(second), 'Recovery reads differ; no trial authorised.')
        require(sha((destination/'flash.bin').read_bytes()) == sha(first), 'Saved recovery image failed verification.')
        require(sha(first[0x8000:0x9000]) == entry['partition_sha256'], 'Recovery partition mismatch.')
        save_new(destination/'recovery.json', {'schema':1,'kind':'s3-complete-recovery',
            'identity':device.identity,'partition_sha256':entry['partition_sha256'],
            'flash_sha256':sha(first),'flash_size':size,'two_matching_device_reads':True,
            'created_utc':datetime.now(timezone.utc).isoformat()})
    print('Complete recovery image saved and independently read-back verified.', flush=True)

def recovery_data(recovery, registry):
    recovery = Path(recovery)
    value = json.loads(recovery.read_text(encoding='utf-8'))
    require(value.get('schema') == 1 and value.get('kind') == 's3-complete-recovery'
            and value.get('two_matching_device_reads') is True, 'Unverified recovery metadata.')
    entry = validate_identity(value['identity'], PROFILE, registry)
    data = (recovery.parent/'flash.bin').read_bytes()
    require(len(data) == value['flash_size'] == value['identity']['flash'] == 16*1024*1024,
            'Recovery must contain the complete original S3 flash.')
    require(sha(data) == value['flash_sha256'], 'Recovery image changed.')
    require(sha(data[0x8000:0x9000]) == value['partition_sha256'] == entry['partition_sha256'],
            'Recovery partition fingerprint mismatch.')
    sequences=[int.from_bytes(data[offset:offset+4],'little') for offset in (0xe000,0xf000)]
    require(all(sequence in (0,1,0xffffffff) for sequence in sequences) and any(sequences),
            'This scoped route supports default app0 boot selection only; review OTA recovery separately.')
    return value, data

def candidate_data(manifest, partition_sha):
    payload, images = load_manifest(Path(manifest), PROFILE)
    table = next(data for offset,data in images if offset==0x8000)
    require(sha(table.ljust(4096,b'\xff')) == partition_sha, 'Candidate would change the partition layout.')
    image = next(data for offset,data in images if offset==0x10000)
    # Include the last erased sector in recovery; keep all other regions untouched.
    span = (len(image)+4095)//4096*4096
    require(span <= 0x700000, 'Application span exceeds its partition.')
    return image, span

def prepare(manifest, recovery, destination, approval, registry_file):
    require(isinstance(approval,str) and 20 <= len(approval) <= 2000, 'Record the explicit human trial authorisation.')
    manifest, recovery = Path(manifest).resolve(), Path(recovery).resolve()
    registry = load_registry(Path(registry_file))
    original, data = recovery_data(recovery,registry)
    image, span = candidate_data(manifest,original['partition_sha256'])
    save_new(destination, {'schema':1,'kind':'s3-application-trial','profile':PROFILE,
        'identity':original['identity'],'partition_sha256':original['partition_sha256'],
        'manifest':str(manifest),'manifest_sha256':sha(manifest.read_bytes()),
        'application_sha256':sha(image),'application_size':len(image),'offset':0x10000,
        'recovery':str(recovery),'recovery_metadata_sha256':sha(recovery.read_bytes()),
        'rollback_span':span,'rollback_sha256':sha(data[0x10000:0x10000+span]),
        'write_role':'single-application-trial','stable_registration_unchanged':True,
        'approval':approval,'created_utc':datetime.now(timezone.utc).isoformat()})
    print('Prepared one application-only write and a verified bounded recovery procedure. Stable role unchanged.')

def execute(port, authorisation, registry_file, *, restore=False, check_only=False, connect=TrialConnection):
    check_port(port)
    path = Path(authorisation)
    auth = json.loads(path.read_text(encoding='utf-8'))
    require(auth.get('schema') == 1 and auth.get('kind') == 's3-application-trial'
            and auth.get('write_role') == 'single-application-trial'
            and auth.get('stable_registration_unchanged') is True, 'Unsupported trial authorisation.')
    require(auth.get('offset') == 0x10000 and 0 < auth.get('rollback_span',0) <= 0x700000
            and auth['rollback_span'] % 4096 == 0, 'Invalid recovery write scope.')
    registry = load_registry(Path(registry_file))
    recovery = Path(auth['recovery'])
    require(sha(recovery.read_bytes()) == auth['recovery_metadata_sha256'], 'Recovery metadata changed.')
    original, flash = recovery_data(recovery, registry)
    require(auth['identity'] == original['identity'] and auth['partition_sha256'] == original['partition_sha256'],
            'Trial/recovery identity mismatch.')
    rollback = flash[0x10000:0x10000+auth['rollback_span']]
    require(sha(rollback) == auth['rollback_sha256'], 'Recovery range changed.')
    dispatch = path.with_suffix(path.suffix + ('.restore-dispatch.json' if restore else '.dispatch.json'))
    if restore:
        require(path.with_suffix(path.suffix+'.dispatch.json').is_file(), 'No trial dispatch to recover.')
        image = rollback
    else:
        manifest = Path(auth['manifest'])
        require(sha(manifest.read_bytes()) == auth['manifest_sha256'], 'Candidate manifest changed.')
        image, span = candidate_data(manifest, auth['partition_sha256'])
        require(sha(image) == auth['application_sha256'] and len(image) == auth['application_size']
                and span == auth['rollback_span'], 'Candidate differs from reviewed trial.')
    require(not dispatch.exists(), 'This write was already dispatched; inspect its receipt before any new action.')
    with connect(port) as device:
        checked_device(device,registry)
        require(device.identity == auth['identity'], 'Wrong registered S3 for this trial.')
        if not restore:
            require(device.read(0x10000,len(rollback)) == rollback,
                    'Installed application differs from its verified recovery snapshot; investigate before trial.')
            require(device.read(0,0x9000)==flash[:0x9000] and device.read(0xe000,0x2000)==flash[0xe000:0x10000],
                    'Bootloader, partitions or OTA selection changed since recovery backup.')
        if check_only:
            print('Trial/recovery scope and physical identity verified; no flash write.')
            return
        # Exclusive durable claim BEFORE I/O. A failed/uncertain write is never replayed.
        save_new(dispatch, {'authorisation_sha256':sha(path.read_bytes()),'restore':restore,
                           'offset':0x10000,'size':len(image),'utc':datetime.now(timezone.utc).isoformat()})
        settings_before=device.read(0,0x10000)
        device.write([(0x10000,image)])
        require(device.read(0x10000,len(image)) == image, 'Independent application read-back failed; recovery required.')
        require(device.table() == flash[0x8000:0x9000], 'Partition table changed unexpectedly.')
        require(device.read(0,0x10000)==settings_before, 'Boot/settings regions changed during application write.')
        save_new(dispatch.with_suffix('.verified.json'), {'verified':True,'restore':restore,
                 'application_sha256':sha(image),'stable_registration_unchanged':True,
                 'utc':datetime.now(timezone.utc).isoformat()})
    print('Recovery verified; stable lock retained.' if restore else 'Trial application flashed and read-back verified; stable lock retained.')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    sub=commands.add_parser('backup');sub.add_argument('--port',required=True);sub.add_argument('--destination',type=Path,required=True)
    sub=commands.add_parser('prepare');sub.add_argument('--manifest',type=Path,required=True);sub.add_argument('--recovery',type=Path,required=True);sub.add_argument('--destination',type=Path,required=True);sub.add_argument('--approval',required=True)
    for name in ('upload','restore','check','check-restore'):
        sub=commands.add_parser(name);sub.add_argument('--port',required=True);sub.add_argument('--authorisation',type=Path,required=True)
    args=parser.parse_args()
    registry=registry_path(Path(__file__).resolve().parents[1])
    try:
        if args.command=='backup':backup(args.port,args.destination,registry)
        elif args.command=='prepare':prepare(args.manifest,args.recovery,args.destination,args.approval,registry)
        else:execute(args.port,args.authorisation,registry,restore=args.command in ('restore','check-restore'),check_only=args.command.startswith('check'))
    except Exception as error:
        print(f'TRIAL REFUSED: {error}',file=sys.stderr);return 2
    return 0

if __name__=='__main__':raise SystemExit(main())
