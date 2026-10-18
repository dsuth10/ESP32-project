"""
ESP32 & Windows Voice Compose & Dictate Companion Service
Resides in the Windows system tray and intercepts BLE HID hotkeys (F13, F14, F15)
to provide instant, high-fidelity voice compose and verbatim dictation.
"""

import os
import sys
import time
import logging
import threading
from pathlib import Path
from PIL import Image, ImageDraw
import pystray
from hotkey_state import HotkeyState

from audio_capture import AudioCapture
from focus_tracker import FocusTracker
from prompt_engine import (
    build_compose_messages,
    build_dictate_messages,
    verify_dictate_overlap,
)
from speech_pipeline import SpeechPipeline
from llm_pipeline import LlmPipeline
from clipboard_manager import ClipboardManager
from status_overlay import StatusOverlay
from web_grounding import WebGrounding

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(line_buffering=True, encoding='utf-8', errors='replace')

log_file = Path(__file__).parent / "companion.log"
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(log_file), mode="a", encoding="utf-8"),
    ],
)


def load_env_config() -> dict:
    """Loads configuration from compose.env and system environment."""
    env_vars = {}
    env_file = Path(__file__).parent / "compose.env"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()

    # System environment overrides file
    for k in [
        "GROQ_API_KEY",
        "GROQ_BASE_URL",
        "GROQ_STT_MODEL",
        "GROQ_LLM_MODEL",
        "LOCAL_WHISPER_MODEL",
        "LOCAL_WHISPER_DEVICE",
        "OLLAMA_HOST",
        "OLLAMA_MODEL",
        "LOCAL_ONLY",
        "AUDIO_INPUT_DEVICE",
        "AUDIO_SAMPLE_RATE",
        "CLIPBOARD_RESTORE_DELAY",
        "CONTINUATION_MAX_ROUNDS",
        "WEB_SEARCH_ENABLED",
        "BRAVE_API_KEY",
        "BRAVE_COUNTRY",
        "BRAVE_RESULT_COUNT",
        "INTENT_ROUTER",
        "OPENROUTER_API_KEY",
        "JEV_MODEL",
        "ROUTER_GROQ_MODEL",
    ]:
        if k in os.environ and os.environ[k]:
            env_vars[k] = os.environ[k]

    return env_vars


def create_tray_icon_image(local_only: bool = False) -> Image.Image:
    """Creates a tray icon with amber/emerald indicator dot."""
    img = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Base rounded dark square
    draw.rounded_rectangle([4, 4, 60, 60], radius=12, fill="#1F2937", outline="#374151", width=2)

    # Mic icon or 'C' glyph
    draw.text((18, 12), "C", fill="#FFFFFF", font=None)

    # Local-only or Cloud dot
    dot_color = "#10B981" if local_only else "#F59E0B"
    draw.ellipse([42, 42, 54, 54], fill=dot_color, outline="#111827", width=2)
    return img


class ComposeCompanion:
    def __init__(self):
        self.config = load_env_config()
        self.local_only = self.config.get("LOCAL_ONLY", "0").lower() in ("1", "true", "yes")

        sample_rate = int(self.config.get("AUDIO_SAMPLE_RATE", "16000"))
        device = self.config.get("AUDIO_INPUT_DEVICE")

        self.audio_capture = AudioCapture(sample_rate=sample_rate, device=device)
        self.speech_pipeline = SpeechPipeline(
            groq_api_key=self.config.get("GROQ_API_KEY"),
            groq_base_url=self.config.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            groq_stt_model=self.config.get("GROQ_STT_MODEL", "whisper-large-v3-turbo"),
            local_model_name=self.config.get("LOCAL_WHISPER_MODEL", "base"),
            local_device=self.config.get("LOCAL_WHISPER_DEVICE", "auto"),
            local_only=self.local_only,
        )
        self.llm_pipeline = LlmPipeline(
            groq_api_key=self.config.get("GROQ_API_KEY"),
            groq_base_url=self.config.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            groq_model=self.config.get("GROQ_LLM_MODEL", "llama-3.3-70b-versatile"),
            ollama_host=self.config.get("OLLAMA_HOST", "http://127.0.0.1:11434"),
            ollama_model=self.config.get("OLLAMA_MODEL", "llama3.2:latest"),
            local_only=self.local_only,
            max_continuation_rounds=int(self.config.get("CONTINUATION_MAX_ROUNDS", "4")),
        )
        self.web_grounding = WebGrounding.from_config(self.config)
        logging.info(self.web_grounding.describe())
        self.overlay = StatusOverlay()

        self.restore_delay = float(self.config.get("CLIPBOARD_RESTORE_DELAY", "0.15"))
        self.pending_ready_payload: str | None = None
        self.tray_icon: pystray.Icon | None = None

        # State tracking for key holds
        self._f13_down = False
        self._f14_down = False
        self._active_mode: str | None = None  # "compose" or "dictate"
        self._focus_snapshot: dict | None = None
        self._selected_text: str = ""
        self._lock = threading.Lock()

    def set_local_only(self, value: bool):
        self.local_only = value
        self.speech_pipeline.local_only = value
        self.llm_pipeline.local_only = value
        if not value:
            self.speech_pipeline.cloud_down = False
        logging.info("Privacy mode set: LOCAL_ONLY = %s", value)
        if self.tray_icon:
            self.tray_icon.icon = create_tray_icon_image(self.local_only)

    # ── Key Hook Handlers ───────────────────────────────────────────────

    def handle_f13_down(self):
        """F13 Pressed: Begin Compose recording."""
        with self._lock:
            if self._f13_down:
                return  # Windows key repeat suppression
            self._f13_down = True
            self._active_mode = "compose"

        logging.info("[Compose] Key Down: Starting recording & focus snapshot...")
        if not self.audio_capture.start_recording():
            self._f13_down = False
            self.overlay.show_error("Could not open microphone")
            return
        self.overlay.show_listening_compose()
        try:
            self._focus_snapshot = FocusTracker.get_focus_snapshot()
        except Exception as e:
            logging.debug("Focus snapshot error: %s", e)
            self._focus_snapshot = None
        try:
            fg_hwnd = self._focus_snapshot.get("hwnd", 0) if self._focus_snapshot else 0
            self._selected_text = FocusTracker.capture_selected_text(fg_hwnd)
            if self._selected_text:
                logging.info("[Compose] Captured selected text (%d chars): %s...", len(self._selected_text), self._selected_text[:60].replace("\n", " "))
            else:
                logging.info("[Compose] No text selected in active window.")
        except Exception as e:
            logging.debug("Capture selected text error: %s", e)
            self._selected_text = ""

    def handle_f13_up(self):
        """F13 Released: Stop recording and dispatch Compose pipeline."""
        with self._lock:
            if not self._f13_down:
                return
            self._f13_down = False

        logging.info("[Compose] Key Up: Recording finished, processing...")
        wav_bytes, dur, rms = self.audio_capture.stop_recording()
        if dur < 0.15:
            logging.info("[Compose] Key press too short (%.2fs), dropped as transient debounce", dur)
            self.overlay.hide()
            return

        focus_snap = self._focus_snapshot
        selected_txt = self._selected_text
        threading.Thread(
            target=self._process_compose_worker,
            args=(wav_bytes, focus_snap, selected_txt),
            daemon=True,
        ).start()

    def handle_f14_down(self):
        """F14 Pressed: Begin Dictate recording."""
        with self._lock:
            if self._f14_down:
                return  # Windows key repeat suppression
            self._f14_down = True
            self._active_mode = "dictate"

        logging.info("[Dictate] Key Down: Starting recording & focus snapshot...")
        if not self.audio_capture.start_recording():
            self._f14_down = False
            self.overlay.show_error("Could not open microphone")
            return
        self.overlay.show_listening_dictate()
        try:
            self._focus_snapshot = FocusTracker.get_focus_snapshot()
        except Exception as e:
            logging.debug("Focus snapshot error: %s", e)
            self._focus_snapshot = None

    def handle_f14_up(self):
        """F14 Released: Stop recording and dispatch Dictate pipeline."""
        with self._lock:
            if not self._f14_down:
                return
            self._f14_down = False

        logging.info("[Dictate] Key Up: Recording finished, processing...")
        wav_bytes, dur, rms = self.audio_capture.stop_recording()
        if dur < 0.15:
            logging.info("[Dictate] Key press too short (%.2fs), dropped as transient debounce", dur)
            self.overlay.hide()
            return

        focus_snap = self._focus_snapshot
        threading.Thread(
            target=self._process_dictate_worker,
            args=(wav_bytes, focus_snap),
            daemon=True,
        ).start()

    def handle_f15_tap(self):
        """F15 Tapped: Inject pending payload if in READY status."""
        logging.info("[Companion] F15 Tapped: Checking ready queue...")
        with self._lock:
            payload = self.pending_ready_payload
            self.pending_ready_payload = None

        if payload:
            logging.info("Pasting queued payload (%d characters)...", len(payload))
            ClipboardManager.inject_paste(payload, restore_delay=self.restore_delay)
            self.overlay.show_pasted()
        else:
            logging.info("No payload pending in READY queue.")
            self.overlay.show("Queue Empty", "No text waiting to paste", color="#9CA3AF", autohide_ms=1000)

    # ── Pipeline Worker Threads ─────────────────────────────────────────

    def _stay_local_if_cloud_blocked(self):
        """A blocked school network should not add a cloud timeout to every later button press."""
        speech_blocked = getattr(self.speech_pipeline, "cloud_down", False) is True
        llm_blocked = getattr(self.llm_pipeline, "local_only", False) is True and getattr(self, "local_only", False) is not True
        if getattr(self, "local_only", False) is True or not (speech_blocked or llm_blocked):
            return
        self.local_only = True
        self.llm_pipeline.local_only = True
        self.speech_pipeline.local_only = True
        self.speech_pipeline.cloud_down = True
        logging.info("Cloud services are unreachable. Using local Whisper and Ollama for the rest of this session.")

    def _process_compose_worker(self, wav_bytes: bytes, focus_snap: dict | None, selected_text: str):
        try:
            self.overlay.show_processing("Transcribing...")
            transcript, stt_prov, stt_lat = self.speech_pipeline.transcribe(wav_bytes)

            if not transcript.strip():
                logging.warning("Compose: No transcript generated from audio")
                self.overlay.show_error("No speech detected")
                return

            logging.info("[Compose] Prompt: '%s' (via %s in %.2fs)", transcript, stt_prov, stt_lat)
            self._stay_local_if_cloud_blocked()

            web = self.web_grounding.fetch_context(
                transcript, selected_text, local_only=self.local_only,
                on_status=lambda msg: self.overlay.show_processing(msg),
            )
            logging.info("[Compose] %s", web.summary())

            self.overlay.show_processing("Writing...")

            messages = build_compose_messages(transcript, selected_text, web.context)
            reply_text, llm_prov, llm_lat, parts = self.llm_pipeline.generate(
                messages,
                temperature=0.3,
                on_status_update=lambda msg: self.overlay.show_processing(msg),
            )
            self._stay_local_if_cloud_blocked()

            if not reply_text.strip():
                self.overlay.show_error("Empty generation")
                return

            logging.info("[Compose] Generated %d chars via %s in %.2fs (%d parts)", len(reply_text), llm_prov, llm_lat, parts)

            # Check focus integrity
            if focus_snap and FocusTracker.is_focus_matched(focus_snap):
                logging.info("[Compose] Focus matched. Injecting paste directly...")
                ClipboardManager.inject_paste(reply_text, restore_delay=self.restore_delay)
                self.overlay.show_pasted()
            else:
                logging.info("[Compose] Target focus shifted during generation! Queuing as READY...")
                with self._lock:
                    self.pending_ready_payload = reply_text
                self.overlay.show_ready_to_paste()

        except Exception as e:
            logging.error("[Compose] Worker error: %s", e, exc_info=True)
            self.overlay.show_error(str(e))

    def _process_dictate_worker(self, wav_bytes: bytes, focus_snap: dict | None):
        try:
            self.overlay.show_processing("Transcribing...")
            raw_transcript, stt_prov, stt_lat = self.speech_pipeline.transcribe(wav_bytes)

            if not raw_transcript.strip():
                logging.warning("Dictate: No transcript generated from audio")
                self.overlay.show_error("No speech detected")
                return

            logging.info("[Dictate] Raw transcript: '%s' (via %s in %.2fs)", raw_transcript, stt_prov, stt_lat)
            self._stay_local_if_cloud_blocked()
            self.overlay.show_processing("Tidying text...")

            # Fast grammar clean
            dictate_msgs = build_dictate_messages(raw_transcript)
            cleaned_text, llm_prov, llm_lat, _ = self.llm_pipeline.generate(
                dictate_msgs,
                temperature=0.0,
            )
            self._stay_local_if_cloud_blocked()

            # Strict Grammar Guard to eliminate hallucination
            final_text = verify_dictate_overlap(raw_transcript, cleaned_text)
            logging.info("[Dictate] Cleaned text: '%s' (via %s in %.2fs)", final_text, llm_prov, llm_lat)

            # Check focus integrity
            if focus_snap and FocusTracker.is_focus_matched(focus_snap):
                logging.info("[Dictate] Focus matched. Injecting paste directly...")
                ClipboardManager.inject_paste(final_text, restore_delay=self.restore_delay)
                self.overlay.show_pasted()
            else:
                logging.info("[Dictate] Target focus shifted during generation! Queuing as READY...")
                with self._lock:
                    self.pending_ready_payload = final_text
                self.overlay.show_ready_to_paste()

        except Exception as e:
            logging.error("[Dictate] Worker error: %s", e, exc_info=True)
            self.overlay.show_error(str(e))

    # ── System Tray & Event Loop ────────────────────────────────────────

    def _poll_keys_worker(self):
        import ctypes
        state = HotkeyState()
        handlers = {
            ("compose", "down"): self.handle_f13_down,
            ("compose", "up"): self.handle_f13_up,
            ("dictate", "down"): self.handle_f14_down,
            ("dictate", "up"): self.handle_f14_up,
            ("paste", "up"): self.handle_f15_tap,
        }
        while not self._stop_poller:
            try:
                for event in state.update(lambda key: bool(ctypes.windll.user32.GetAsyncKeyState(key) & 0x8000)):
                    handler = handlers.get(event)
                    if handler:
                        handler()
            except Exception:
                logging.exception("Hotkey handler failed")
            time.sleep(0.015)

    def run(self):
        banner = (
            "\n" + "=" * 65 + "\n"
            "   ESP32 & Windows Voice Compose & Dictate Companion (Active)\n"
            + "=" * 65 + "\n"
            f"   Status      : LISTENING FOR ESP32 HOTKEYS\n"
            f"   Microphone  : {self.audio_capture.device_name} (WASAPI)\n"
            f"   Privacy Mode: {'Local Only (Ollama)' if self.local_only else 'Cloud Groq + Local Ollama'}\n\n"
            "   Controls:\n"
            "    - COMPOSE  (ESP32 / Ctrl+Alt+Shift+F9)  : Tap or Hold to write\n"
            "    - DICTATE  (ESP32 / Ctrl+Alt+Shift+F10) : Tap or Hold to transcribe\n"
            "    - PASTE    (ESP32 / Ctrl+Alt+Shift+F11) : Tap to insert ready queue\n"
            + "=" * 65 + "\n"
        )
        print(banner, flush=True)
        logging.info("Starting poller thread and keyboard listener...")

        self._stop_poller = False
        self._poller_thread = threading.Thread(target=self._poll_keys_worker, daemon=True)
        self._poller_thread.start()

        # Build System Tray Menu
        def toggle_local_only(icon, item):
            self.set_local_only(not self.local_only)

        def paste_ready_action(icon, item):
            self.handle_f15_tap()

        def clear_queue_action(icon, item):
            with self._lock:
                self.pending_ready_payload = None
            logging.info("Ready queue cleared.")

        def open_config_action(icon, item):
            cfg_path = Path(__file__).parent / "compose.env"
            if cfg_path.exists():
                os.startfile(str(cfg_path))

        def quit_action(icon, item):
            logging.info("Shutting down Compose Companion...")
            self._stop_poller = True
            self.audio_capture.stop_recording()
            icon.stop()
            sys.exit(0)

        menu = pystray.Menu(
            pystray.MenuItem("Compose / Dictate Companion", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Local Only (Offline / Private)",
                toggle_local_only,
                checked=lambda item: self.local_only,
            ),
            pystray.MenuItem("Paste Ready Payload (F15)", paste_ready_action),
            pystray.MenuItem("Clear Ready Queue", clear_queue_action),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open Configuration (.env)", open_config_action),
            pystray.MenuItem("Quit", quit_action),
        )

        self.tray_icon = pystray.Icon(
            "compose_companion",
            create_tray_icon_image(self.local_only),
            "ESP32 Compose & Dictate Companion",
            menu,
        )

        try:
            self.tray_icon.run()
        except KeyboardInterrupt:
            logging.info("Interrupted. Exiting...")
            self._stop_poller = True
            self.audio_capture.stop_recording()


if __name__ == "__main__":
    companion = ComposeCompanion()
    companion.run()
