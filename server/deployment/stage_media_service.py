"""Inspect and explicitly stage the media service deployment bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE_FILES = (
    Path("server/media_library_server.py"),
    Path("server/requirements-media.txt"),
)
DEPLOYMENT_DIR = ROOT / "server" / "deployment"
FILES = CORE_FILES + tuple(sorted(
    (Path("server/deployment") / path.name for path in DEPLOYMENT_DIR.iterdir()
     if path.is_file() and path.suffix in {".py", ".service", ".example"}),
    key=lambda path: path.as_posix(),
))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage(destination: Path, reviewed: bool):
    missing = [str(path) for path in FILES if not (ROOT / path).is_file() or (ROOT / path).is_symlink()]
    if missing:
        raise FileNotFoundError("Bundle inputs are missing: " + ", ".join(missing))
    destination = destination.absolute()
    if destination.exists():
        raise FileExistsError("Stage destination already exists; refusing to overwrite it.")
    source_hashes = {p.as_posix(): _sha256(ROOT / p) for p in FILES}
    report = {
        "stage_path": str(destination),
        "files": [p.as_posix() for p in FILES],
        "source_sha256": source_hashes,
        "loopback_bind": "127.0.0.1:8765",
        "durable_data_path_template": "/var/lib/companion-media-%i",
        "secret_source": "/etc/companion-media/%i.env (root-owned, mode 0600)",
        "reviewed_apply": reviewed,
        "host_changes_performed": False,
    }
    if not reviewed:
        return report
    destination.mkdir(parents=True)
    try:
        staged_hashes = {}
        for relative in FILES:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
            staged_hashes[relative.as_posix()] = _sha256(target)
        if staged_hashes != source_hashes:
            raise ValueError("Staged copy does not match the reviewed source hashes")
        report["staged_sha256"] = staged_hashes
        (destination / "STAGE-REVIEW.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return report


def main():
    parser = argparse.ArgumentParser(description="Preflight or explicitly stage the Linux media service files.")
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--apply-reviewed", action="store_true", help="Confirm you reviewed the emitted file list and target")
    args = parser.parse_args()
    try:
        print(json.dumps(stage(args.destination, args.apply_reviewed), indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"error_type": type(exc).__name__, "host_changes_performed": False}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
