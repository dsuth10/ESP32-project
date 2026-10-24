"""Start the local SolidCraft window when needed, then serve its STDIO MCP bridge."""

from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / "docs" / "dimensions" / "solidcraft"
INSTALL = Path("C:/Program Files/SolidCraft")
HOST, PORT = "127.0.0.1", 7878


def listening():
    try:
        with socket.create_connection((HOST, PORT), timeout=0.5):
            return True
    except OSError:
        return False


def main():
    cli = INSTALL / "solidcraft-cli.exe"
    app = INSTALL / "solidcraft.exe"
    if not cli.is_file() or not app.is_file():
        raise RuntimeError(f"SolidCraft and its CLI must be installed in {INSTALL}")
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    if not listening():
        print("Opening a local SolidCraft window for MCP on port 7878.", file=sys.stderr)
        subprocess.Popen(
            [str(app), "--control", str(PORT)],
            cwd=WORKSPACE,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 20
        while not listening():
            if time.monotonic() >= deadline:
                raise RuntimeError("SolidCraft did not open its local control listener within 20 s")
            time.sleep(0.2)
    return subprocess.call(
        [str(cli), "mcp", "--connect", f"{HOST}:{PORT}", "--allow-path", str(WORKSPACE)],
        cwd=WORKSPACE,
    )


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"SolidCraft MCP: {exc}", file=sys.stderr)
        sys.exit(1)
