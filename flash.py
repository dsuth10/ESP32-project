"""Guarded upload entry point. Implicit ports and unverified demo bins are disabled.
Build the selected PlatformIO environment, then pass its board-upload.json.
Use --check-only for read-only device/firmware checks.
"""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
from board_safety import main


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--port", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    return main(["check" if args.check_only else "upload", "--profile", args.profile,
                 "--port", args.port, "--manifest", args.manifest])


if __name__ == "__main__":
    raise SystemExit(run())
