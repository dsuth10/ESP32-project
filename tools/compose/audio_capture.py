"""
Audio capture module using sounddevice and WASAPI for high-fidelity PC microphone input.
Captures audio via Windows Audio Session API (WASAPI) to activate Windows taskbar
privacy indicators and provide ultra-low latency recording. Automatically resamples
to 16kHz 16-bit mono PCM WAV for Whisper STT.
"""

import io
import math
import time
import wave
import threading
import logging
from audio_lease import MicrophoneLease
import numpy as np
import sounddevice as sd
try:
    import scipy.signal
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


def find_default_wasapi_input_device() -> tuple[int | None, int]:
    """Finds the default Windows WASAPI recording device and its native sample rate."""
    try:
        hostapis = sd.query_hostapis()
        for h in hostapis:
            if "wasapi" in h.get("name", "").lower():
                dev_idx = h.get("default_input_device", -1)
                if dev_idx >= 0:
                    info = sd.query_devices(dev_idx)
                    native_sr = int(info.get("default_samplerate", 48000))
                    return dev_idx, native_sr
    except Exception as e:
        logging.warning("Error finding WASAPI input device: %s", e)

    # Fallback to general default input device
    try:
        def_in = sd.default.device[0]
        if def_in >= 0:
            info = sd.query_devices(def_in)
            return def_in, int(info.get("default_samplerate", 44100))
    except Exception:
        pass

    return None, 16000


class AudioCapture:
    def __init__(
        self,
        target_sample_rate: int = 16000,
        sample_rate: int | None = None,
        device: int | str | None = None,
        channels: int = 1,
        max_duration_sec: float = 60.0,
    ):
        self.target_sample_rate = sample_rate if sample_rate is not None else target_sample_rate
        self.channels = channels
        self.max_duration_sec = max_duration_sec

        # Resolve device and native sample rate
        if device not in (None, "", "default"):
            self.device = int(device) if str(device).isdigit() else device
            try:
                info = sd.query_devices(self.device)
                self.native_sample_rate = int(info.get("default_samplerate", 48000))
            except Exception:
                self.native_sample_rate = 48000
        else:
            self.device, self.native_sample_rate = find_default_wasapi_input_device()

        self._stream: sd.InputStream | None = None
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._is_recording = False
        self._start_time = 0.0
        self._microphone_lease = MicrophoneLease()
        self.last_error = ''

    @property
    def device_name(self) -> str:
        try:
            if self.device is not None:
                info = sd.query_devices(self.device)
                return info.get("name", f"Device {self.device}")
        except Exception:
            pass
        return "Default Microphone"

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._is_recording

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        with self._lock:
            if not self._is_recording:
                return
            self._chunks.append(indata.copy())
            if time.time() - self._start_time >= self.max_duration_sec:
                self._is_recording = False

    def start_recording(self) -> bool:
        """Starts recording audio from the PC microphone via WASAPI."""
        with self._lock:
            if self._is_recording:
                return True
            if not self._microphone_lease.acquire():
                self.last_error = 'The PC microphone is in use by the other workspace. Finish that recording first.'
                return False
            self.last_error = ''
            self._chunks = []
            self._is_recording = True
            self._start_time = time.time()

        try:
            logging.info(
                "Opening WASAPI audio stream on device %s at %d Hz...",
                self.device,
                self.native_sample_rate,
            )
            self._stream = sd.InputStream(
                samplerate=self.native_sample_rate,
                channels=self.channels,
                dtype="int16",
                device=self.device,
                callback=self._audio_callback,
                blocksize=1024,
            )
            self._stream.start()
            return True
        except Exception as e:
            with self._lock:
                self._is_recording = False
            if self._stream is not None:
                try:
                    self._stream.close()
                finally:
                    self._stream = None
                    self._microphone_lease.release()
            else:
                self._microphone_lease.release()
            self.last_error = 'The PC microphone could not open. Check Windows microphone permissions and device selection.'
            logging.error("Failed to start WASAPI audio stream: %s", e)
            return False

    def stop_recording(self) -> tuple[bytes, float, float]:
        """
        Stops recording and returns:
        (wav_bytes_16khz, duration_seconds, rms_level)
        """
        with self._lock:
            self._is_recording = False

        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logging.error("Error closing stream: %s", e)
            finally:
                self._stream = None
        self._microphone_lease.release()

        with self._lock:
            chunks = list(self._chunks)
            self._chunks = []

        if not chunks:
            return b"", 0.0, 0.0

        audio_data = np.concatenate(chunks, axis=0)
        num_frames = audio_data.shape[0]
        duration = num_frames / float(self.native_sample_rate)

        # Calculate RMS amplitude
        flat_data = audio_data.astype(np.float32).flatten()
        if len(flat_data) > 0:
            mean_sq = np.mean(flat_data ** 2)
            rms = math.sqrt(mean_sq) if mean_sq > 0 else 0.0
        else:
            rms = 0.0

        # Resample to 16kHz for Whisper if needed
        if self.native_sample_rate != self.target_sample_rate:
            target_length = int(num_frames * self.target_sample_rate / float(self.native_sample_rate))
            if HAS_SCIPY:
                resampled_data = scipy.signal.resample(audio_data, target_length).astype(np.int16)
            else:
                x_old = np.linspace(0, 1, num_frames)
                x_new = np.linspace(0, 1, target_length)
                resampled_data = np.interp(x_new, x_old, audio_data.flatten()).astype(np.int16).reshape(-1, self.channels)
            final_audio = resampled_data
        else:
            final_audio = audio_data

        # Encode to WAV in-memory at 16000Hz
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.target_sample_rate)
            wf.writeframes(final_audio.tobytes())

        return wav_buf.getvalue(), duration, rms


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("[AudioCapture] Self-test: recording 2 seconds of audio with WASAPI...")
    cap = AudioCapture()
    if cap.start_recording():
        time.sleep(2.0)
        raw_wav, dur, rms = cap.stop_recording()
        print(f"[AudioCapture] Captured {len(raw_wav)} bytes at 16kHz, duration: {dur:.2f}s, RMS: {rms:.1f}")
        assert len(raw_wav) > 1000, "WAV buffer is empty"
        print("[AudioCapture] Test Passed!")
    else:
        print("[AudioCapture] Test Failed to start stream.")
