"""
Speech-to-Text (STT) pipeline with Groq cloud Whisper-large-v3-turbo
and local faster-whisper fallback.
"""

import os
import io
import sys
import time
import logging
import subprocess
import tempfile
from pathlib import Path

import requests

WORKER_PATH = Path(__file__).with_name("whisper_worker.py")
CUBLAS_DLLS = ("cublas64_13.dll", "cublas64_12.dll", "cublas64_11.dll")


def is_cloud_network_failure(exc: Exception) -> bool:
    """True when a cloud call failed because the network blocked or dropped it."""
    return isinstance(exc, (requests.Timeout, requests.ConnectionError))


def cuda_runtime_usable() -> bool:
    """True when CTranslate2 can see a GPU *and* the Windows CUDA BLAS DLL loads."""
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() <= 0:
            return False
    except Exception:
        return False
    if os.name != "nt":
        return True
    import ctypes
    for name in CUBLAS_DLLS:
        try:
            ctypes.WinDLL(name)
            return True
        except OSError:
            continue
    logging.warning("CUDA device is visible but cuBLAS is missing; using CPU Whisper")
    return False


os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"


class SpeechPipeline:
    def __init__(
        self,
        groq_api_key: str | None = None,
        groq_base_url: str = "https://api.groq.com/openai/v1",
        groq_stt_model: str = "whisper-large-v3-turbo",
        local_model_name: str = "base",
        local_device: str = "auto",
        local_only: bool = False,
    ):
        self.groq_api_key = groq_api_key.strip() if groq_api_key else None
        self.groq_base_url = groq_base_url.rstrip("/")
        self.groq_stt_model = groq_stt_model
        self.local_model_name = local_model_name
        self.local_device = local_device
        self.local_only = local_only
        self.cloud_down = False

        self._local_model = None
        self._resolved_device = None
        self._cuda_unusable = False

    def _choose_device(self) -> str:
        requested = self.local_device.lower()
        if requested != "auto":
            return requested
        if self._cuda_unusable:
            return "cpu"
        return "cuda" if cuda_runtime_usable() else "cpu"

    def _get_local_model(self):
        if self._local_model is None:
            import faster_whisper

            device = self._resolved_device or self._choose_device()
            compute_type = "float16" if device == "cuda" else "int8"
            logging.info("Loading local faster-whisper model '%s' on %s (%s)...", self.local_model_name, device, compute_type)
            self._local_model = faster_whisper.WhisperModel(
                self.local_model_name,
                device=device,
                compute_type=compute_type,
            )
            self._resolved_device = device
        return self._local_model

    def _transcribe_subprocess(self, wav_bytes: bytes, device: str) -> tuple[str | None, str | None]:
        """Run Whisper in a child process so a native CUDA abort cannot kill this GUI."""
        compute_type = "float16" if device == "cuda" else "int8"
        wav_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
                handle.write(wav_bytes)
                wav_path = handle.name
            logging.info(
                "Loading local faster-whisper model '%s' on %s (%s) in a child process...",
                self.local_model_name, device, compute_type,
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(WORKER_PATH),
                    "--model", self.local_model_name,
                    "--device", device,
                    "--compute-type", compute_type,
                    "--wav", wav_path,
                ],
                capture_output=True,
                timeout=180,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            return None, "timeout"
        except Exception as exc:
            return None, f"{type(exc).__name__}: {exc}"
        finally:
            if wav_path:
                try:
                    os.unlink(wav_path)
                except OSError:
                    pass
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or f"exit {completed.returncode}").strip()
            return None, detail[:400]
        return completed.stdout.strip(), None

    def _transcribe_groq(self, wav_bytes: bytes) -> str:
        """Uploads WAV bytes to Groq Whisper endpoint."""
        url = f"{self.groq_base_url}/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
        }
        files = {
            "file": ("audio.wav", io.BytesIO(wav_bytes), "audio/wav"),
        }
        data = {
            "model": self.groq_stt_model,
            "response_format": "json",
            "language": "en",
        }

        resp = requests.post(url, headers=headers, files=files, data=data, timeout=12.0)
        resp.raise_for_status()
        res_json = resp.json()
        return res_json.get("text", "").strip()

    def _run_local_model(self, wav_bytes: bytes) -> str:
        model = self._get_local_model()
        segments, _ = model.transcribe(
            io.BytesIO(wav_bytes), beam_size=3, language="en",
            task="transcribe", temperature=0.0,
        )
        # CUDA libraries may not load until this lazy iterator is consumed.
        return " ".join(seg.text.strip() for seg in segments if seg.text.strip()).strip()

    def _transcribe_local(self, wav_bytes: bytes) -> str:
        """Transcribes WAV bytes via local faster-whisper."""
        if self._local_model is None:
            device = self._choose_device()
            if device == "cuda":
                # Never load CUDA Whisper in the GUI process. A missing or
                # broken cuBLAS DLL aborts the interpreter and the window vanishes.
                text, error = self._transcribe_subprocess(wav_bytes, "cuda")
                if text is not None:
                    self._resolved_device = "cuda"
                    return text
                if self.local_device.lower() != "auto":
                    raise RuntimeError(error or "isolated CUDA Whisper failed")
                self._cuda_unusable = True
                logging.warning("GPU Whisper process died (%s); retrying on CPU", error)

        try:
            return self._run_local_model(wav_bytes)
        except Exception as error:
            if self.local_device.lower() != "auto" or self._resolved_device not in (None, "cuda"):
                raise
            logging.warning("Automatic GPU transcription unavailable (%s); retrying on CPU", error)
            import faster_whisper
            self._local_model = faster_whisper.WhisperModel(
                self.local_model_name, device="cpu", compute_type="int8",
            )
            self._resolved_device = "cpu"
            self._cuda_unusable = True
            return self._run_local_model(wav_bytes)

    def transcribe(self, wav_bytes: bytes) -> tuple[str, str, float]:
        """
        Transcribes audio bytes.
        Returns: (transcript, provider_used, latency_seconds)
        """
        t0 = time.time()
        if not wav_bytes or len(wav_bytes) < 100:
            return "", "none", 0.0

        # Try Groq first if available and not forced local
        if self.groq_api_key and not self.local_only and not self.cloud_down:
            try:
                text = self._transcribe_groq(wav_bytes)
                latency = time.time() - t0
                logging.info("Groq STT transcription succeeded in %.2fs: '%s'", latency, text)
                return text, "groq", latency
            except Exception as e:
                if is_cloud_network_failure(e):
                    self.cloud_down = True
                    logging.warning("Groq STT unreachable (%s). Staying on local Whisper for this session.", e)
                else:
                    logging.warning("Groq STT failed: %s. Falling back to local faster-whisper...", e)

        # Fallback to local faster-whisper
        try:
            text = self._transcribe_local(wav_bytes)
            latency = time.time() - t0
            logging.info("Local faster-whisper transcription succeeded in %.2fs: '%s'", latency, text)
            return text, "local_whisper", latency
        except Exception as e:
            logging.error("Local STT also failed: %s", e)
            return "", "failed", time.time() - t0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pipeline = SpeechPipeline(local_model_name="tiny", local_only=True)
    print("[SpeechPipeline] Initialized OK!")
