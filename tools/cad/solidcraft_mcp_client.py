"""Run a JSON list of MCP tool calls for connection checks and reproducible CAD work.

Usage: python tools/cad/solidcraft_mcp_client.py requests.json
Each request is {"name": "inspect_design", "arguments": {}}.
The launcher and CLI use the actual MCP STDIO protocol; image payloads are saved
inside the dedicated design folder rather than printed to the terminal.
"""

import base64
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / "docs" / "dimensions" / "solidcraft"


def main():
    requests = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    if not isinstance(requests, list) or any(not isinstance(item, dict) or not isinstance(item.get("name"), str) for item in requests):
        raise ValueError("Requests must be a JSON list of tool calls with names")
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).with_name("solidcraft_mcp_launcher.py"))],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", bufsize=1,
    )
    responses = queue.Queue()

    def read_stdout():
        for line in process.stdout:
            responses.put(line)
        responses.put(None)

    def read_stderr():
        for line in process.stderr:
            print(line.rstrip(), file=sys.stderr)

    threading.Thread(target=read_stdout, daemon=True).start()
    threading.Thread(target=read_stderr, daemon=True).start()

    def rpc(identifier, method, params):
        request = {"jsonrpc": "2.0", "method": method, "params": params}
        if identifier is not None:
            request["id"] = identifier
        process.stdin.write(json.dumps(request) + "\n")
        process.stdin.flush()
        if identifier is None:
            return None
        while True:
            line = responses.get(timeout=90)
            if line is None:
                raise RuntimeError("MCP process closed before replying")
            response = json.loads(line)
            if response.get("id") == identifier:
                if "error" in response:
                    raise RuntimeError(response["error"])
                return response["result"]

    try:
        initial = rpc(1, "initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "esp32-enclosure-check", "version": "1.0"},
        })
        print(json.dumps({"initialised": initial.get("serverInfo")}))
        rpc(None, "notifications/initialized", {})
        for identifier, request in enumerate(requests, 2):
            result = rpc(identifier, "tools/call", {key: value for key, value in request.items() if not key.startswith("_")})
            if request.get("_assert_empty"):
                state = json.loads(result["content"][0]["text"])
                if state.get("dirty") or any(state.get(key) for key in ("bodies", "timeline", "sketches", "params")):
                    raise RuntimeError("The visible design contains work; refusing to replace or build over it")
            for index, content in enumerate(result.get("content", [])):
                if content.get("type") == "image":
                    path = WORKSPACE / f"mcp-preview-{identifier}-{index}.png"
                    path.write_bytes(base64.b64decode(content.pop("data")))
                    content["saved_path"] = str(path)
            print(json.dumps({"tool": request["name"], "result": result}))
            if result.get("isError"):
                raise RuntimeError(f"MCP tool {request['name']} failed; later calls were not sent")
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()


if __name__ == "__main__":
    main()
