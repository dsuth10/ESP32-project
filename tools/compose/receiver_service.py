"""Runs the Hermes voice receiver as a child of the desktop companion."""

import os
import socket
import subprocess
import sys
from pathlib import Path


PORT = 8787


class VoiceReceiver:
    def __init__(self, project_root: Path | None = None, port: int | None = None, extra_env: dict | None = None):
        self.project_root = project_root or Path(__file__).resolve().parents[2]
        self.process: subprocess.Popen | None = None
        self._log_file = None
        self.port = int(port if port is not None else PORT)
        self.extra_env = dict(extra_env or {})

    @property
    def owns_process(self) -> bool:
        return self.process is not None

    def python_executable(self) -> Path:
        server = self.project_root / "server"
        candidates = [
            server / ".venv" / "Scripts" / "python.exe",
            Path(r"C:\Python312\python.exe"),
            Path(r"C:\Python313\python.exe"),
            Path(sys.executable),
        ]
        return next(path for path in candidates if path.exists())

    def is_listening(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            return sock.connect_ex(("127.0.0.1", self.port)) == 0

    def start(self) -> str:
        if self.process is not None and self.process.poll() is None:
            return "Voice receiver is already being started by this window"
        if self.is_listening():
            return f"Voice receiver already running on port {self.port}"
        script = self.project_root / "server" / "hermes_voice_receiver.py"
        if not script.exists():
            raise FileNotFoundError(script)
        env = os.environ.copy()
        env.update(self.extra_env)
        env["RECEIVER_PORT"] = str(self.port)
        env.setdefault("RECEIVER_ENV", "work")
        env.setdefault("OLLAMA_KEEP_ALIVE", "8h")
        env.setdefault("OLLAMA_NO_CLOUD", "1")
        log_path = Path(__file__).with_name("receiver.log")
        self._log_file = log_path.open("a", encoding="utf-8", errors="replace")
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self.process = subprocess.Popen(
            [str(self.python_executable()), "-u", str(script)],
            cwd=str(script.parent),
            env=env,
            stdout=self._log_file,
            stderr=subprocess.STDOUT,
            creationflags=flags,
        )
        return f"Starting voice receiver on port {self.port}"

    def exited(self) -> bool:
        return self.process is not None and self.process.poll() is not None

    def stop(self) -> None:
        process = self.process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        self.process = None
        if self._log_file is not None:
            self._log_file.close()
            self._log_file = None
