"""Fail-closed, device-bound uploads. Requires esptool==5.4.0.

Never select a port automatically. Probe and write through the same serial handle.
The local registry is shared by Git worktrees and contains private device IDs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys


class SafetyError(RuntimeError):
    pass


PROFILES = {
    "es3c28p-s3": {
        "chip": "ESP32-S3", "chip_id": 9, "flash": 16 * 1024 * 1024,
        "environments": ["esp32-s3-portrait", "esp32-s3-devkitc-1"],
        "regions": {"bootloader": (0, 0x8000), "partitions": (0x8000, 0x1000),
                    "ota_boot": (0xe000, 0x2000), "application": (0x10000, 0x700000)},
    },
    "cyd-2432s028": {
        "chip": "ESP32", "chip_id": 0, "flash": 4 * 1024 * 1024,
        "environments": ["cyd-identify"],
        # Only the proven diagnostic app is currently supported on the CYD.
        "regions": {"application": (0x10000, 0x140000)},
    },
}


def require(condition, message):
    if not condition:
        raise SafetyError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def profile_for(name):
    require(name in PROFILES, "Unknown board profile.")
    return PROFILES[name]


def registry_path(root):
    p = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        capture_output=True, text=True, check=False,
    )
    require(p.returncode == 0, "Cannot locate the shared Git board registry.")
    common = Path(p.stdout.strip()).resolve()
    require(common.name == ".git" and common.is_dir(), "Unsupported Git layout; no registry fallback.")
    return common.parent / ".local" / "boards" / "registry.json"


def load_registry(path):
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        require(result["schema"] == 1 and isinstance(result["devices"], dict), "Invalid board registry.")
        for mac, entry in result["devices"].items():
            require(re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", mac), "Invalid registry identity.")
            p = profile_for(entry["profile"])
            require(entry["chip"] == p["chip"] and entry["flash"] == p["flash"], "Invalid registry hardware.")
            require(entry.get("role", "stable") in ("stable", "test"), "Invalid registered device role.")
            require(re.fullmatch(r"[0-9a-f]{64}", entry["partition_sha256"]), "Missing registered partition fingerprint.")
        return result
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise SafetyError("Board registry missing or unreadable. Register the physical board first.") from exc


def validate_identity(observed, profile, registry):
    p = profile_for(profile)
    require(observed["chip"] == p["chip"], "WRONG PROCESSOR: upload refused.")
    require(observed["flash"] == p["flash"], "WRONG FLASH CAPACITY: upload refused.")
    entry = registry["devices"].get(observed["mac"])
    require(entry is not None, "UNREGISTERED BOARD: upload refused.")
    require(entry["profile"] == profile, "WRONG PHYSICAL BOARD: upload refused.")
    require(entry["chip"] == observed["chip"] and entry["flash"] == observed["flash"], "Registered hardware has changed.")
    return entry


def validate_partition_table(data, profile):
    require(len(data) >= 0xc00, "Partition table is truncated.")
    p = profile_for(profile)
    entries = []
    end = None
    for at in range(0, 0xc00, 32):
        row = data[at:at+32]
        if row[:2] == b"\xeb\xeb":
            require(row[16:32] == hashlib.md5(data[:at]).digest(), "Partition checksum mismatch.")
            end = at
            break
        if row == b"\xff" * 32:
            end = at
            break
        require(row[:2] == b"\xaa\x50", "Invalid partition table entry.")
        _, kind, subtype, offset, size, _, flags = struct.unpack("<HBBII16sI", row)
        require(flags == 0 and offset >= 0x9000 and size > 0 and offset + size <= p["flash"], "Unsupported partition layout.")
        require(offset % 4096 == 0 and size % 4096 == 0, "Unaligned partition layout.")
        require(not any(offset < old[2]+old[3] and old[2] < offset+size for old in entries), "Overlapping partitions.")
        entries.append((kind, subtype, offset, size))
    require(end is not None and entries, "Partition table missing terminator.")
    expected_size = p["regions"]["application"][1]
    require((0, 0x10, 0x10000, expected_size) in entries, "Unexpected application partition.")
    require((1, 2, 0x9000, 0x5000) in entries and (1, 0, 0xe000, 0x2000) in entries, "Unexpected settings/OTA layout.")


def load_manifest(path, profile):
    """Load immutable image bytes before opening the port; never reread at write time."""
    p = profile_for(profile)
    try:
        m = json.loads(path.read_text(encoding="utf-8"))
        require(m["schema"] == 1 and m["profile"] == profile, "Firmware belongs to a different board profile.")
        require(m["environment"] in p["environments"], "Unapproved firmware environment.")
        require(isinstance(m["images"], list), "Missing firmware images.")
        roles, images = set(), []
        for image in m["images"]:
            role = image["role"]
            require(role in p["regions"] and role not in roles, "Invalid or duplicate image role.")
            roles.add(role)
            start, capacity = p["regions"][role]
            require(type(image["offset"]) is int and image["offset"] == start, "Invalid image offset.")
            file = (path.parent / image["path"]).resolve()
            data = file.read_bytes()
            require(0 < len(data) <= capacity and len(data) == image["size"], "Image exceeds its approved region or changed size.")
            require(sha(data) == image["sha256"], "FIRMWARE CHANGED: rebuild before uploading.")
            if role in ("bootloader", "application"):
                require(len(data) >= 24 and data[0] == 0xe9, "Invalid ESP image header.")
                require(struct.unpack_from("<H", data, 12)[0] == p["chip_id"], "Firmware processor does not match profile.")
                require((1 << (20 + (data[3] >> 4))) == p["flash"], "Firmware flash header does not match profile.")
            if role == "partitions":
                validate_partition_table(data, profile)
            images.append((start, data))
        require(roles == set(p["regions"]), "Required firmware images missing.")
        # Build inputs are also fingerprinted; a stale build cannot be relabelled.
        require(isinstance(m["inputs"], list) and m["inputs"], "Missing build provenance.")
        for item in m["inputs"]:
            require(sha((path.parent / item["path"]).read_bytes()) == item["sha256"], "Build configuration changed; rebuild before uploading.")
        return m, images
    except (OSError, ValueError, TypeError, KeyError, struct.error) as exc:
        raise SafetyError("Firmware manifest or files are missing/invalid. Build the selected target first.") from exc


class EspConnection:
    """esptool API adapter. No reconnect between identity checks and writes."""
    def __init__(self, port):
        self.port, self.esp = port, None

    def __enter__(self):
        import esptool
        require(esptool.__version__ == "5.4.0", "Install the tested uploader: python -m pip install esptool==5.4.0")
        self.api = esptool
        self.esp = esptool.detect_chip(port=self.port, baud=115200)
        try:
            require(not self.esp.secure_download_mode, "Secure download mode is unsupported.")
            require(not self.esp.get_secure_boot_enabled() and not self.esp.get_flash_encryption_enabled(), "Secure/encrypted boards need a separate reviewed workflow.")
            esptool.attach_flash(self.esp)
            flash_id = self.esp.flash_id()
            # Standard JEDEC capacity byte; reject unknown formats, never guess.
            size_code = (flash_id >> 16) & 255
            require(flash_id & 255 not in (0, 255, 0x1f) and 20 <= size_code <= 26, "Unrecognised flash capacity encoding.")
            mac = self.esp.read_mac("BASE_MAC")
            require(mac and len(mac) == 6 and any(mac) and not all(v == 255 for v in mac), "Cannot read physical board identity.")
            self.identity = {"chip": self.esp.CHIP_NAME, "flash": 1 << size_code,
                             "mac": ":".join(f"{v:02x}" for v in mac)}
            return self
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise

    def table(self):
        if not self.esp.IS_STUB:
            self.esp = self.api.run_stub(self.esp)
        return self.api.read_flash(self.esp, 0x8000, 0x1000, no_progress=True)

    def write(self, images):
        self.esp.change_baud(460800)
        self.api.write_flash(self.esp, images, flash_mode="keep", flash_freq="keep", flash_size="keep", no_progress=True)

    def __exit__(self, *args):
        if self.esp is not None:
            try:
                self.esp.hard_reset()
            finally:
                self.esp._port.close()


def check_port(port):
    require(isinstance(port, str) and re.fullmatch(r"COM[1-9][0-9]*|/dev/(?:tty|cu\.)[A-Za-z0-9._/-]+", port), "An explicit local serial port is required; automatic/network targets are refused.")


def guarded_upload(profile, port, manifest, registry_file, connect=EspConnection, check_only=False):
    check_port(port)
    _, images = load_manifest(Path(manifest), profile)
    registry = load_registry(Path(registry_file))
    with connect(port) as device:
        entry = validate_identity(device.identity, profile, registry)
        require(check_only or entry.get("role", "stable") == "test", "STABLE BOARD IS WRITE-LOCKED. Release approval is required before changing its local registration.")
        table = device.table()
        validate_partition_table(table, profile)
        require(sha(table) == entry["partition_sha256"], "Partition layout changed since registration; upload refused.")
        print(f"Matched registered board '{entry['label']}' to {profile}; firmware hashes and regions verified.")
        if check_only:
            print("CHECK ONLY: no flash write or erase performed.")
            return
        device.write(images)
        print("Guarded upload completed and esptool verified the written data.")


def register(profile, port, label, registry_file, connect=EspConnection, role="stable"):
    check_port(port)
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,59}", label), "Use a short, plain device label.")
    require(role in ("stable", "test"), "Invalid device role.")
    p = profile_for(profile)
    registry_file = Path(registry_file)
    registry = load_registry(registry_file) if registry_file.exists() else {"schema": 1, "devices": {}}
    with connect(port) as device:
        observed = device.identity
        require(observed["chip"] == p["chip"] and observed["flash"] == p["flash"], "Connected hardware does not match the requested profile.")
        table = device.table()
        validate_partition_table(table, profile)
        entry = {**observed, "profile": profile, "label": label, "role": role,
                 "partition_sha256": sha(table)}
        old = registry["devices"].get(observed["mac"])
        if old is not None:
            require(all(old[k] == entry[k] for k in ("profile", "chip", "flash", "partition_sha256")), "Existing registration conflicts; refusing to reassign this device.")
            require(old.get("role", "stable") == role, "Device role is locked; refusing to reassign it.")
            print(f"Board already registered as '{old['label']}'. No registration changed.")
            return
        require(not any(e["label"] == label for e in registry["devices"].values()), "Device label is already registered.")
        entry["registered_utc"] = datetime.now(timezone.utc).isoformat()
        registry["devices"][observed["mac"]] = entry
    registry_file.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation avoids silently replacing a registration on concurrent runs.
    lock = registry_file.with_suffix(".lock")
    acquired = False
    try:
        with lock.open("x"):
            acquired = True
            latest = load_registry(registry_file) if registry_file.exists() else {"schema": 1, "devices": {}}
            require(observed["mac"] not in latest["devices"] and not any(e["label"] == label for e in latest["devices"].values()), "Registry changed concurrently; retry after inspection.")
            latest["devices"][observed["mac"]] = entry
            tmp = registry_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(latest, indent=2)+"\n", encoding="utf-8")
            tmp.replace(registry_file)
    except FileExistsError as exc:
        raise SafetyError("Registry busy; no registration written.") from exc
    finally:
        if acquired:
            lock.unlink(missing_ok=True)
    print(f"Registered '{label}' as {profile}. No flash write or erase performed.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("register", "upload", "check"):
        sub = commands.add_parser(name)
        sub.add_argument("--profile", required=True, choices=PROFILES)
        sub.add_argument("--port", required=True)
        if name == "register":
            sub.add_argument("--label", required=True)
            sub.add_argument("--role", choices=("stable", "test"), default="stable")
        else:
            sub.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = Path(__file__).resolve().parents[1]
        registry = registry_path(root)
        if args.command == "register":
            register(args.profile, args.port, args.label, registry, role=args.role)
        else:
            guarded_upload(args.profile, args.port, args.manifest, registry, check_only=args.command == "check")
        return 0
    except Exception as exc:
        print(f"UPLOAD REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
