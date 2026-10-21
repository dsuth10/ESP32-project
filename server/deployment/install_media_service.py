"""Install or stop one reviewed Linux companion-media systemd instance.

The installer deliberately requires an owner-provisioned venv and account. It
does not install packages, change network policy, or remove installed data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

INSTANCE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,31}$")
CORE_PACKAGE_FILES = (
    Path("server/media_library_server.py"),
    Path("server/requirements-media.txt"),
)
DEPLOYMENT_DIR = Path(__file__).resolve().parent
STAGE_REQUIRED_FILES = CORE_PACKAGE_FILES + tuple(sorted(
    (Path("server/deployment") / path.name for path in DEPLOYMENT_DIR.iterdir()
     if path.is_file() and path.suffix in {".py", ".service", ".example"}),
    key=lambda path: path.as_posix(),
))
PACKAGE_FILES = (
    Path("server/media_library_server.py"),
    Path("server/requirements-media.txt"),
    Path("server/deployment/companion-media-library@.service"),
    Path("server/deployment/companion-media.env.example"),
    Path("server/deployment/media_backup.py"),
)
STAGE_MANIFEST = "STAGE-REVIEW.json"
UNIT_NAME = "companion-media-library@.service"
APP_ROOT = Path("/opt/companion-media")
ENV_ROOT = Path("/etc/companion-media")
STATE_ROOT = Path("/var/lib")
RECEIPT_ROOT = Path("/var/lib/companion-media-install")
ACCOUNT = "companion-media"


@dataclass(frozen=True)
class Layout:
    app_root: Path = APP_ROOT
    env_root: Path = ENV_ROOT
    state_root: Path = STATE_ROOT
    receipt_root: Path = RECEIPT_ROOT
    unit_path: Path = Path("/etc/systemd/system") / UNIT_NAME

    def env_path(self, instance: str) -> Path:
        return self.env_root / f"{instance}.env"

    def data_path(self, instance: str) -> Path:
        return self.state_root / f"companion-media-{instance}"

    def receipt_path(self, instance: str) -> Path:
        return self.receipt_root / f"{instance}.json"


def _check_instance(instance: str) -> None:
    if not INSTANCE_RE.fullmatch(instance):
        raise ValueError("Invalid instance name")


def _has_symlink_component(path: Path) -> bool:
    cursor = path.absolute()
    while cursor != cursor.parent:
        if cursor.is_symlink():
            return True
        cursor = cursor.parent
    return False


def package_hash(stage: Path) -> tuple[str, dict[str, str]]:
    hashes: dict[str, str] = {}
    for relative in PACKAGE_FILES:
        source = stage / relative
        if _has_symlink_component(source) or not source.is_file():
            raise ValueError("Stage bundle is incomplete or contains a linked source")
        hashes[relative.as_posix()] = hashlib.sha256(source.read_bytes()).hexdigest()
    _verify_stage_manifest(stage)
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return digest, hashes


def _verify_stage_manifest(stage: Path) -> None:
    manifest_path = stage / STAGE_MANIFEST
    if _has_symlink_component(manifest_path) or not manifest_path.is_file():
        raise ValueError("Stage review manifest is missing or linked")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("Stage review manifest is invalid") from exc
    files = manifest.get("files")
    source_hashes = manifest.get("source_sha256")
    staged_hashes = manifest.get("staged_sha256")
    required = {p.as_posix() for p in STAGE_REQUIRED_FILES}
    if not isinstance(files, list) or set(files) != required or len(files) != len(required):
        raise ValueError("Stage review manifest does not list the expected bundle")
    if not isinstance(source_hashes, dict) or source_hashes != staged_hashes or set(source_hashes) != required:
        raise ValueError("Stage review manifest source and staged hashes differ")
    for name in files:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or not name.startswith("server/"):
            raise ValueError("Stage review manifest contains an unsafe path")
        path = stage / relative
        if _has_symlink_component(path) or not path.is_file() or _sha256_file(path) != source_hashes[name]:
            raise ValueError("Staged file does not match its reviewed manifest hash")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=check, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)


def _is_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


def _require_root() -> None:
    if not _is_root():
        raise PermissionError("Apply and rollback require Linux root")
    if sys.platform != "linux":
        raise RuntimeError("Apply and rollback are supported only on Linux")


def _require_account() -> None:
    user = _run(["getent", "passwd", ACCOUNT], check=False)
    group = _run(["getent", "group", ACCOUNT], check=False)
    if user.returncode or group.returncode:
        raise RuntimeError("Provision the dedicated companion-media user and group first")


def _safe_existing_app(app_root: Path) -> None:
    if not app_root.exists():
        raise FileNotFoundError("Provision /opt/companion-media/venv before install")
    if app_root.is_symlink() or not app_root.is_dir():
        raise FileExistsError("Application path exists and is not a trusted directory")
    children = {p.name for p in app_root.iterdir()}
    if children - {"venv"}:
        raise FileExistsError("Application path contains existing files; refusing to overwrite them")
    venv = app_root / "venv"
    if venv.is_symlink() or not venv.is_dir():
        raise FileExistsError("Application path must contain only an owner-provisioned venv")
    python = venv / "bin" / "python"
    if python.is_symlink() or not python.is_file() or not os.access(python, os.X_OK):
        raise FileNotFoundError("Provision venv/bin/python as a copied executable (python3 -m venv --copies) with Pillow installed")
    _check_venv_security(app_root, venv, python)
    result = _run(["runuser", "-u", ACCOUNT, "--", str(python), "-c", "import PIL"], check=False)
    if result.returncode:
        raise RuntimeError("The pre-provisioned venv must be able to import Pillow as companion-media")


def _check_venv_security(app_root: Path, venv: Path, python: Path) -> None:
    for path in (app_root, venv, python):
        info = path.stat()
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise PermissionError("Application root, venv and interpreter must be root-owned and not group/world writable")


def preflight(stage: Path, instance: str, layout: Layout = Layout()) -> dict:
    _check_instance(instance)
    stage = stage.resolve(strict=True)
    digest, hashes = package_hash(stage)
    report = {
        "instance": instance,
        "package_sha256": digest,
        "source_sha256": hashes,
        "app_path": str(layout.app_root),
        "env_path": str(layout.env_path(instance)),
        "data_path": str(layout.data_path(instance)),
        "receipt_path": str(layout.receipt_path(instance)),
        "unit_path": str(layout.unit_path),
        "unit_name": f"companion-media-library@{instance}.service",
        "bind": "127.0.0.1:8765",
        "account_prerequisite": ACCOUNT,
        "venv_prerequisite": str(layout.app_root / "venv") + " (root-owned python3 -m venv --copies; Pillow importable as companion-media)",
        "host_checks_performed": ["staged bundle paths and source hashes only"],
        "host_checks_pending": ["Linux root", "dedicated account/group", "root-owned --copies venv with Pillow", "target collisions", "systemd availability", "port/listener inventory"],
        "writes_performed": False,
    }
    return report


def _reject_preexisting(layout: Layout, instance: str) -> None:
    for path in (layout.app_root, layout.env_root, layout.data_path(instance), layout.receipt_path(instance), layout.unit_path):
        if _has_symlink_component(path):
            raise ValueError(f"Install target traverses a linked path: {path}")
    for path in (layout.unit_path, layout.env_path(instance), layout.data_path(instance), layout.receipt_path(instance)):
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Install target already exists: {path}")
    _safe_existing_app(layout.app_root)


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp_name = tempfile.mkstemp(prefix=".receipt-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _write_private_env(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    token = secrets.token_urlsafe(32)
    content = f"MEDIA_SERVER_TOKEN={token}\nMEDIA_SERVER_BUDGET_LIMIT_CENTS=3000\n".encode("ascii")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def _read_private_token(path: Path) -> str:
    for line in path.read_text(encoding="ascii").splitlines():
        if line.startswith("MEDIA_SERVER_TOKEN="):
            token = line.partition("=")[2]
            if token:
                return token
    raise RuntimeError("Generated environment file has no token")


def _verify_readiness(token: str) -> None:
    base = "http://127.0.0.1:8765"

    class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirectHandler)

    def request(path: str, auth: bool = False) -> dict:
        headers = {"Authorization": f"Bearer {token}"} if auth else {}
        req = urllib.request.Request(base + path, headers=headers)
        try:
            with opener.open(req, timeout=5) as response:
                if response.geturl() != base + path or response.status != 200:
                    raise RuntimeError("Media service readiness response was unexpected")
                return json.loads(response.read(65536).decode("utf-8"))
        except (OSError, urllib.error.URLError, ValueError) as exc:
            raise RuntimeError("Media service did not pass local authenticated readiness") from exc

    health = request("/health")
    if not isinstance(health, dict) or health.get("status") != "ok":
        raise RuntimeError("Media service health response was not ready")
    capabilities = request("/v1/capabilities", auth=True)
    if not isinstance(capabilities, dict):
        raise RuntimeError("Media service capabilities did not match the expected contract")
    kinds = capabilities.get("event_kinds")
    if (capabilities.get("service") != "media-library" or capabilities.get("version") != 1
            or not isinstance(kinds, list) or not {"version", "canonical"}.issubset(kinds)
            or capabilities.get("budget") is not True or not isinstance(capabilities.get("max_blob_bytes"), int)):
        raise RuntimeError("Media service capabilities did not match the expected contract")


def _copy_sources(stage: Path, layout: Layout, expected_hashes: dict[str, str]) -> dict[str, str]:
    target_server = layout.app_root / "server"
    target_server.mkdir(parents=True, exist_ok=False)
    copied: dict[str, str] = {}
    for rel in PACKAGE_FILES:
        if rel.parts[0] != "server":
            raise ValueError("Unexpected package path")
        target = layout.app_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            raise FileExistsError("Refusing to overwrite application source")
        source = stage / rel
        if _has_symlink_component(source):
            raise ValueError("Stage source became a linked path during copy")
        content = source.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != expected_hashes.get(rel.as_posix()):
            raise ValueError("Stage source changed after its reviewed hash was calculated")
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(target, 0o644)
        copied[rel.as_posix()] = digest
    return copied


def apply_install(stage: Path, instance: str, expected_hash: str, *, apply: bool = False, layout: Layout = Layout(), run: Callable = _run) -> dict:
    if not apply:
        return preflight(stage, instance, layout)
    _require_root()
    _check_instance(instance)
    stage = stage.resolve(strict=True)
    report = preflight(stage, instance, layout)
    if not secrets.compare_digest(expected_hash, report["package_sha256"]):
        raise ValueError("Reviewed package hash does not match current staged sources")
    _require_account()
    _reject_preexisting(layout, instance)
    # Recheck all collision paths immediately before any mutation.
    _reject_preexisting(layout, instance)

    receipt_path = layout.receipt_path(instance)
    receipt = {
        "schema": 1,
        "instance": instance,
        "unit_name": report["unit_name"],
        "unit_path": str(layout.unit_path),
        "package_sha256": report["package_sha256"],
        "source_sha256": report["source_sha256"],
        "installed_sha256": {},
        "status": "preparing",
        "created_unit": False,
        "activation_attempted": False,
        "created_env": False,
        "created_app_sources": False,
    }
    _atomic_json(receipt_path, receipt)
    try:
        app_created = not layout.app_root.exists()
        layout.app_root.mkdir(parents=True, exist_ok=True, mode=0o755)
        installed = _copy_sources(stage, layout, report["source_sha256"])
        receipt["installed_sha256"] = installed
        receipt["created_app_sources"] = True
        _write_private_env(layout.env_path(instance))
        receipt["created_env"] = True
        unit_bytes = (layout.app_root / Path("server/deployment/companion-media-library@.service")).read_bytes()
        fd = os.open(layout.unit_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "wb") as stream:
            stream.write(unit_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        receipt["created_unit"] = True
        receipt["unit_sha256"] = hashlib.sha256(unit_bytes).hexdigest()
        receipt["app_root_created"] = app_created
        receipt["status"] = "prepared"
        _atomic_json(receipt_path, receipt)
        run(["systemd-analyze", "verify", str(layout.unit_path)])
        run(["systemctl", "daemon-reload"])
        receipt["activation_attempted"] = True
        _atomic_json(receipt_path, receipt)
        run(["systemctl", "enable", "--now", report["unit_name"]])
        run(["systemctl", "is-active", "--quiet", report["unit_name"]])
        token = _read_private_token(layout.env_path(instance))
        _verify_readiness(token)
        receipt["status"] = "active"
        _atomic_json(receipt_path, receipt)
        return {
            **report,
            "status": "active",
            "receipt_path": str(receipt_path),
            "host_checks_performed": report["host_checks_performed"] + [
                "Linux root", "dedicated account/group", "root-owned --copies venv and Pillow import",
                "target collision checks", "systemd-analyze verify", "authenticated local readiness",
            ],
            "host_checks_pending": ["operator port/listener inventory", "remote tailnet reachability and access acceptance"],
            "writes_performed": True,
        }
    except BaseException:
        if receipt.get("created_unit") and receipt.get("activation_attempted"):
            run(["systemctl", "stop", report["unit_name"]], check=False)
            run(["systemctl", "disable", report["unit_name"]], check=False)
        receipt["status"] = "failed-preserved"
        _atomic_json(receipt_path, receipt)
        raise


def rollback(receipt_path: Path, *, apply: bool = False, layout: Layout | None = None, run: Callable = _run) -> dict:
    receipt_path = receipt_path.absolute()
    if _has_symlink_component(receipt_path):
        raise ValueError("Receipt path traverses a linked path")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("Cannot read a valid install receipt") from exc
    instance = receipt.get("instance")
    _check_instance(instance)
    unit_name = f"companion-media-library@{instance}.service"
    if receipt.get("schema") != 1 or receipt.get("unit_name") != unit_name or not receipt.get("created_unit"):
        raise ValueError("Receipt does not prove ownership of this unit")
    unit_path = Path(receipt.get("unit_path", ""))
    expected_unit_path = layout.unit_path if layout is not None else Layout().unit_path
    expected_receipt_path = layout.receipt_path(instance) if layout is not None else Layout().receipt_path(instance)
    if unit_path != expected_unit_path or receipt_path != expected_receipt_path.absolute():
        raise ValueError("Receipt unit path does not match the reviewed layout")
    if not unit_path.is_file() or unit_path.is_symlink():
        raise FileNotFoundError("Recorded unit file is missing or linked")
    if hashlib.sha256(unit_path.read_bytes()).hexdigest() != receipt.get("unit_sha256"):
        raise ValueError("Installed unit changed since receipt; refusing rollback")
    plan = {"instance": instance, "unit_name": unit_name, "unit_path": str(unit_path), "preserves_app_env_data_and_token": True, "writes_performed": False}
    if not apply:
        return plan
    _require_root()
    # Re-read and revalidate immediately before issuing scoped systemd commands.
    current = json.loads(receipt_path.read_text(encoding="utf-8"))
    if current != receipt:
        raise ValueError("Receipt changed during rollback preflight")
    stopped = run(["systemctl", "stop", unit_name], check=False)
    disabled = run(["systemctl", "disable", unit_name], check=False)
    complete = getattr(stopped, "returncode", 0) == 0 and getattr(disabled, "returncode", 0) == 0
    receipt["status"] = "rolled-back-stopped" if complete else "rollback-incomplete"
    _atomic_json(receipt_path, receipt)
    return {**plan, "writes_performed": True, "status": receipt["status"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight, install, or stop-rollback one isolated media systemd instance.")
    sub = parser.add_subparsers(dest="command", required=True)
    install = sub.add_parser("install")
    install.add_argument("--stage", type=Path, required=True)
    install.add_argument("--instance", required=True)
    install.add_argument("--expected-package-sha256")
    install.add_argument("--apply", action="store_true", help="Apply the reviewed plan")
    stop = sub.add_parser("rollback")
    stop.add_argument("--receipt", type=Path, required=True)
    stop.add_argument("--apply", action="store_true", help="Stop and disable only the receipt-owned instance")
    args = parser.parse_args()
    try:
        if args.command == "install":
            result = apply_install(args.stage, args.instance, args.expected_package_sha256 or "", apply=args.apply)
        else:
            result = rollback(args.receipt, apply=args.apply)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"error_type": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
