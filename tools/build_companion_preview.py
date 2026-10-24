"""Build an allowlisted source preview without credentials or private reports."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Teacher documentation is deliberate. Development consultation reports can
# contain historical private endpoints and are never distributed by wildcard.
DOCUMENTS = [
    "docs/feature-media-testing.md", "docs/media-sync-server.md",
    "docs/companion-installation.md", "docs/companion-deployment.md",
    "docs/2026-10-21-hermes-integration-checkpoint.md",
    "docs/2026-10-24-home-acceptance.md",
    "docs/2026-10-24-gemini-image-provider-plan.md",
    "docs/2026-10-24-image-provider-g1-g2-implementation.md",
    "docs/2026-10-24-image-provider-g3-g4-implementation.md",
    "docs/2026-10-21-companion-media-agent-master-plan.md",
    "docs/hermes-tailscale-home-work.md",
]


def source_files(root=ROOT):
    root = Path(root).resolve()
    paths = [root/p for p in [
        "start_companion.bat", "start_companion_feature.bat",
        "setup_companion_feature.bat", "server/media_library_server.py",
        "server/hermes_voice_receiver.py", "server/requirements-media.txt",
        "server/tests/test_media_server_portable.py",
        "tools/build_companion_preview.py", "tools/companion_package.py",
    ] + DOCUMENTS]
    for path in (root/"tools/compose").rglob("*"):
        if (path.is_file() and "__pycache__" not in path.parts and
                not any(p.startswith(".") for p in path.relative_to(root).parts)):
            if path.suffix in {".py", ".bat"} or path.name in {"requirements.txt", "compose.env.example"}:
                paths.append(path)
    # Deployment templates and helpers have their own explicit source subtree.
    for path in (root/"server/deployment").rglob("*"):
        if path.is_file() and path.suffix in {".py", ".service", ".example"}:
            paths.append(path)
    return sorted(set(paths))


def build(destination, root=ROOT):
    root = Path(root).resolve()
    destination = Path(destination)
    files = source_files(root)
    manifest = {}
    for path in files:
        current = path
        while current != root:
            if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
                raise ValueError("Linked preview source paths are refused.")
            current = current.parent
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Preview source escapes its root.")
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Missing or linked preview source: {path.relative_to(root)}")
        manifest[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(root))
        archive.writestr("preview-manifest.json", json.dumps(
            {"format": "source-preview", "files": manifest}, indent=2))
    with zipfile.ZipFile(destination) as archive:
        for name, digest in manifest.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError("Preview verification failed")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = build(args.output)
    print(json.dumps({"source_files": len(manifest), "sha256_verified": True,
                      "credentials_or_data_included": False}))
