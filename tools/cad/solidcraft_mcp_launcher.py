"""Discover MCP tools quietly; open the visible CAD app on the first real request."""

import json
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / "docs" / "dimensions" / "solidcraft"
INSTALL = Path("C:/Program Files/SolidCraft")
HOST, PORT = "127.0.0.1", 7878
QUIET = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DISCOVERY = {"tools/list", "resources/list", "resources/templates/list"}


def listening():
    try:
        with socket.create_connection((HOST, PORT), timeout=0.5):
            return True
    except OSError:
        return False


def open_window():
    if listening():
        return
    print("Opening SolidCraft for the requested CAD operation.", file=sys.stderr)
    subprocess.Popen(
        [str(INSTALL / "solidcraft.exe"), "--control", str(PORT)],
        cwd=WORKSPACE, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 20
    while not listening():
        if time.monotonic() >= deadline:
            raise RuntimeError("SolidCraft did not open its control listener within 20 s")
        time.sleep(0.2)


def discover(initial):
    """Use a short-lived CLI, never the GUI, to obtain this installation's schemas."""
    requests = [dict(initial, id=0),
                {"jsonrpc": "2.0", "method": "notifications/initialized"}]
    methods = sorted(DISCOVERY)
    requests.extend({"jsonrpc": "2.0", "id": i, "method": method, "params": {}}
                    for i, method in enumerate(methods, 1))
    result = subprocess.run(
        [str(INSTALL / "solidcraft-cli.exe"), "mcp", "--headless",
         "--allow-path", str(WORKSPACE)],
        input="".join(json.dumps(item) + "\n" for item in requests),
        text=True, encoding="utf-8", capture_output=True, timeout=20,
        cwd=WORKSPACE, creationflags=QUIET,
    )
    if result.returncode:
        raise RuntimeError("SolidCraft CLI discovery failed; check the installation")
    replies = {item["id"]: item for line in result.stdout.splitlines()
               if (item := json.loads(line)).get("id") is not None}
    initial_reply = replies[0]
    if "error" in initial_reply:
        return initial_reply, {}
    info = initial_reply["result"]
    info["instructions"] = info.get("instructions", "").replace(
        "Backend: headless in-process SolidCraft session.",
        "Backend: visible SolidCraft window, opened only on the first CAD request.")
    return initial_reply, {method: replies[i] for i, method in enumerate(methods, 1)}


class Bridge:
    def __init__(self):
        self.process = None
        self.initial = None
        self.discovery = {}
        self.output_lock = threading.Lock()

    def send(self, message):
        with self.output_lock:
            print(json.dumps(message), flush=True)

    def activate(self):
        open_window()
        self.process = subprocess.Popen(
            [str(INSTALL / "solidcraft-cli.exe"), "mcp", "--connect",
             f"{HOST}:{PORT}", "--allow-path", str(WORKSPACE)],
            cwd=WORKSPACE, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=None, text=True, encoding="utf-8", bufsize=1,
            creationflags=QUIET,
        )
        replies = queue.Queue()
        stream = self.process.stdout

        def read():
            try:
                for line in stream:
                    replies.put(line)
            finally:
                stream.close()
                replies.put(None)

        threading.Thread(target=read, daemon=True).start()
        self.write(dict(self.initial, id="lazy-initialize"))
        deadline = time.monotonic() + 20
        while True:
            line = replies.get(timeout=max(0.01, deadline - time.monotonic()))
            if line is None:
                raise RuntimeError("SolidCraft bridge closed during initialisation")
            response = json.loads(line)
            if response.get("id") == "lazy-initialize":
                if "error" in response:
                    raise RuntimeError("SolidCraft bridge rejected initialisation")
                break
            self.send(response)
        self.write({"jsonrpc": "2.0", "method": "notifications/initialized"})

        def forward():
            while (line := replies.get()) is not None:
                self.send(json.loads(line))

        threading.Thread(target=forward, daemon=True).start()

    def write(self, message):
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def handle(self, message):
        method = message.get("method", "")
        # A user may close the CAD window between requests in the same chat.
        if self.process is not None and method in {"tools/call", "resources/read"} and not listening():
            self.close()
        if self.process is not None:
            self.write(message)
            return
        if method == "initialize":
            reply, self.discovery = discover(message)
            if "error" not in reply:
                self.initial = message
            self.send(dict(reply, id=message["id"]))
        elif method == "ping":
            if "id" in message:
                self.send({"jsonrpc": "2.0", "id": message["id"], "result": {}})
        elif method in DISCOVERY and self.initial:
            self.send(dict(self.discovery[method], id=message["id"]))
        elif method.startswith("notifications/"):
            pass
        elif method in {"tools/call", "resources/read"} and self.initial:
            try:
                self.activate()
            except Exception:
                self.close()
                raise
            self.write(message)
        elif "id" in message:
            self.send({"jsonrpc": "2.0", "id": message["id"],
                       "error": {"code": -32601, "message": "Method not available"}})

    def close(self):
        if self.process is None:
            return
        try:
            self.process.stdin.close()
        except OSError:
            pass
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=5)
        self.process = None


def main():
    if not all((INSTALL / name).is_file() for name in ("solidcraft.exe", "solidcraft-cli.exe")):
        raise RuntimeError(f"SolidCraft and its CLI must be installed in {INSTALL}")
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    bridge = Bridge()
    try:
        for line in sys.stdin:
            message = None
            try:
                message = json.loads(line)
                bridge.handle(message)
            except Exception as exc:
                print(f"SolidCraft MCP: {exc}", file=sys.stderr)
                if isinstance(message, dict) and "id" in message:
                    bridge.send({"jsonrpc": "2.0", "id": message["id"],
                                 "error": {"code": -32603, "message": str(exc)}})
    finally:
        bridge.close()


if __name__ == "__main__":
    main()
