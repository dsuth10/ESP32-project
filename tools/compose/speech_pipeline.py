"""
Speech-to-Text (STT) pipeline with Groq cloud Whisper-large-v3-turbo
and local faster-whisper fallback.
"""

import os
import io
import time
import logging
import requests

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

        self._local_model = None
        self._resolved_device = None

    def _get_local_model(self):
        if self._local_model is None:
            import faster_whisper
            import ctranslate2

            device = self.local_device.lower()
            if device == "auto":
                device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"

            compute_type = "float16" if device == "cuda" else "int8"
            logging.info("Loading local faster-whisper model '%s' on %s (%s)...", self.local_model_name, device, compute_type)
            self._local_model = faster_whisper.WhisperModel(
                self.local_model_name,
                device=device,
                compute_type=compute_type,
            )
            self._resolved_device = device
        return self._local_model

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

    def _transcribe_local(self, wav_bytes: bytes) -> str:
        """Transcribes WAV bytes via local faster-whisper."""
        def run():
            model = self._get_local_model()
            segments, _ = model.transcribe(
                io.BytesIO(wav_bytes), beam_size=3, language="en",
                task="transcribe", temperature=0.0,
            )
            # CUDA libraries may not load until this lazy iterator is consumed.
            return " ".join(seg.text.strip() for seg in segments if seg.text.strip()).strip()

        try:
            return run()
        except Exception as error:
            if self.local_device.lower() != "auto" or self._resolved_device not in (None, "cuda"):
                raise
            logging.warning("Automatic GPU transcription unavailable (%s); retrying on CPU", error)
            import faster_whisper
            self._local_model = faster_whisper.WhisperModel(
                self.local_model_name, device="cpu", compute_type="int8",
            )
            self._resolved_device = "cpu"
            return run()

    def transcribe(self, wav_bytes: bytes) -> tuple[str, str, float]:
        """
        Transcribes audio bytes.
        Returns: (transcript, provider_used, latency_seconds)
        """
        t0 = time.time()
        if not wav_bytes or len(wav_bytes) < 100:
            return "", "none", 0.0

        # Try Groq first if available and not forced local
        if self.groq_api_key and not self.local_only:
            try:
                text = self._transcribe_groq(wav_bytes)
                latency = time.time() - t0
                logging.info("Groq STT transcription succeeded in %.2fs: '%s'", latency, text)
                return text, "groq", latency
            except Exception as e:
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
