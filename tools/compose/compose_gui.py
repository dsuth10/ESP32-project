"""
ESP32 & Windows Voice Compose & Dictate Companion - Interactive Desktop App
Provides a dedicated visual interface, live hardware event log, and manual test triggers.
Guarantees full visibility for the user so they can see recording status, microphone activity,
transcriptions, and generated text in real time.
"""

import sys
import os
import time
import threading
import ctypes
import ctypes.wintypes
import queue
import logging
from pathlib import Path
import tkinter as tk
from tkinter import ttk, scrolledtext

# Ensure current directory is on python path
sys.path.insert(0, str(Path(__file__).parent))

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
from receiver_service import VoiceReceiver
from web_grounding import WebGrounding
from config_loader import load_env_config as load_shared_env_config
from history_store import HistoryStore
from library_panel import LibraryPanel
from assistant_service import AssistantService
from assistant_panel import AssistantPanel
from companion_settings import data_directory, load_settings
try:
    from media_store import MediaStore
    from media_service import MediaService
    from media_panel import MediaPanel
    from media_sync import SyncClient
except ImportError:
    MediaStore = MediaService = MediaPanel = SyncClient = None
from settings_panel import SettingsPanel
from media_voice_bridge import VoiceBridge
from hermes_panel import HermesPanel
from hermes_service import HermesService, HermesServiceError


def truthy(value):
    return str(value or '').lower() in {'1', 'true', 'yes', 'on'}


def load_env_config() -> dict:
    return load_shared_env_config(
        Path(__file__).parent,
        settings_loader=load_settings,
        defaults={"ESP32_START_RECEIVER": "0", "ESP32_ENABLE_HOTKEYS": "0"},
    )


class ComposeApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self._last_external_snap = FocusTracker.snapshot_foreground_window()
        if self._last_external_snap.get("pid") == os.getpid():
            self._last_external_snap = None
        self.root.title("🎙️ ESP32 Voice Compose & Dictate Companion")
        self.root.geometry("920x740")
        self.root.minsize(720, 640)
        self.root.configure(bg="#0B0F19")
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(300, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()

        self.config = load_env_config()
        self.local_only = self.config.get("LOCAL_ONLY", "0").lower() in ("1", "true", "yes")
        self.history_enabled = self.config.get("HISTORY_ENABLED", "1").lower() in ("1", "true", "yes")
        self.history = None
        self._history_error = False
        try:
            self.history = HistoryStore()
        except Exception:
            # Recording/paste should remain usable if local storage is unavailable.
            self._history_error = True

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

        self.restore_delay = float(self.config.get("CLIPBOARD_RESTORE_DELAY", "0.15"))
        self.pending_ready_payload: str | None = None
        self.pending_media = None
        self.pending_media_job = None
        self._sync_stop = threading.Event()
        self._sync_thread = None
        self.media_store = None
        try:
            self.media_store = MediaStore(data_directory())
        except Exception:
            pass

        # State
        self.is_recording = False
        self.recording_mode = "compose"  # "compose" or "dictate"
        self._target_focus_snap = None
        self._target_selected_text = ""
        self._stop_poller = False
        self._busy = False
        self._ui_events = queue.Queue()
        self._recording_timer = None

        self._build_ui()
        self.voice_bridge = None
        receiver_env = {}
        if self.media_store and not self.local_only and truthy(self.config.get("ESP32_START_RECEIVER", "1")):
            self.voice_bridge = VoiceBridge(self.media_store)
            receiver_env = {"COMPANION_MEDIA_BRIDGE_URL": self.voice_bridge.url, "COMPANION_MEDIA_BRIDGE_TOKEN": self.voice_bridge.token,
                            "DISCOVERY_UDP_PORT": os.environ.get("ESP32_DISCOVERY_UDP_PORT", "8789")}
        self.receiver = VoiceReceiver(port=int(os.environ.get("ESP32_RECEIVER_PORT", "8787")), extra_env=receiver_env)
        self._receiver_watch_ticks = 0
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(20, self._drain_ui_events)
        self.log(f"Service initialized. Active Microphone: {self.audio_capture.device_name} (WASAPI)")
        provider = "Local Whisper + Ollama" if self.local_only or not self.config.get("GROQ_API_KEY") else "Groq Whisper + Groq LLM"
        self.log(f"Processing: {provider}")
        self.log(self.web_grounding.describe())
        self.log("Ready and listening for ESP32 MacroPad or keyboard hotkeys!")
        if self._history_error:
            self.log("History unavailable. Check access to your companion data folder; writing still works.")
        if not self.local_only and truthy(self.config.get("ESP32_START_RECEIVER", "1")):
            try:
                self.log(self.receiver.start())
            except Exception:
                logging.exception("Voice receiver failed to start")
                self.log("Voice receiver failed to start. See companion.log")
            self.root.after(1000, self._watch_receiver)
        else:
            self.receiver_lbl.configure(text=("Local-only mode: feature voice receiver paused; use the PC microphone or BLE controls."
                if self.local_only else "Feature preview: receiver startup disabled; live receiver left alone."))

        # Start hardware key listener thread
        if truthy(self.config.get("ESP32_ENABLE_HOTKEYS", "1")):
            self.poller_thread = threading.Thread(target=self._hardware_key_poller, daemon=True)
            self.poller_thread.start()
        self._configure_media_sync()
        self.root.after(500, self._drain_media_voice_requests)
        self.root.after(200, self._remember_external_focus)

    def _build_ui(self):
        status = tk.Frame(self.root, bg="#111827")
        status.pack(fill="x", padx=8, pady=(8, 0))
        self.global_status_dot = tk.Label(status, text="●", bg="#111827", fg="#10B981", padx=8)
        self.global_status_dot.pack(side="left", anchor="n", pady=6)
        self.global_status_lbl = tk.Label(status, text="READY: Waiting for an action", bg="#111827",
                                          fg="#F8FAFC", justify="left", anchor="w", wraplength=650, pady=6)
        self.global_status_lbl.pack(side="left", fill="x", expand=True)
        self.root.bind("<Configure>", self._resize_global_status, add="+")
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=8)
        self.writing_tab = tk.Frame(self.tabs, bg="#0B0F19")
        self.tabs.add(self.writing_tab, text="Compose & Dictate")
        self.assistant_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.assistant_tab, text="Ask your companion")
        self.assistant_tabs = ttk.Notebook(self.assistant_tab)
        self.assistant_tabs.pack(fill="both", expand=True)
        self.ask_tab = ttk.Frame(self.assistant_tabs)
        self.assistant_tabs.add(self.ask_tab, text="Groq Ask / Manage")
        self.hermes_tab = ttk.Frame(self.assistant_tabs)
        self.assistant_tabs.add(self.hermes_tab, text="Hermes tasks")
        self.library_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.library_tab, text="History & saved text")
        self.media_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.media_tab, text="Image library")
        self.settings_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.settings_tab, text="Settings")
        self.media_service = MediaService(self.media_store, self.config) if self.media_store else None
        if self.media_service:
            self.media_service.recover_interrupted_jobs()
            self.media_panel = MediaPanel(self.media_tab, self.media_service, self._post_ui,
                                          self._queue_media, self._toggle_media_recording, self._record_history)
            self.media_panel.settings_saving = self._settings_saving
            self.media_panel.pack(fill="both", expand=True)
            media_options = ttk.Frame(self.media_tab)
            media_options.pack(fill="x", before=self.media_panel)
            self.media_hotkey = tk.BooleanVar(value=False)
            ttk.Checkbutton(media_options, text="Route Compose hotkey to media requests this session", variable=self.media_hotkey).pack(side="left")
            ttk.Button(media_options, text="Clear queued image", command=self._clear_media_queue).pack(side="right")
        else:
            ttk.Label(self.media_tab, text="Media storage unavailable. Existing writing and History remain usable.").pack()
        self.settings_panel = SettingsPanel(self.settings_tab, self.config,
                                            self._validate_settings_before_save, self._apply_saved_settings,
                                            self._post_ui)
        self.settings_panel.pack(fill="both", expand=True)

        self.assistant_service = AssistantService(self.config, self._assistant_status, self.history)
        self.assistant_panel = AssistantPanel(
            self.ask_tab, self.assistant_service, self._post_ui,
            self._queue_library_text, self._record_history,
        )
        self.assistant_panel.settings_saving = self._settings_saving
        self.assistant_panel.pack(fill="both", expand=True)
        self.hermes_panel = HermesPanel(self.hermes_tab, None, self._post_ui,
                                        self._queue_library_text, lambda: self.local_only,
                                        lambda: self.settings_panel._saving,
                                        lambda: truthy(self.config.get("HERMES_ENABLED")))
        self.hermes_panel.pack(fill="both", expand=True)
        self.hermes_service = None
        self._start_hermes_service()
        if self.history is not None:
            self.library_panel = LibraryPanel(
                self.library_tab, self.history, self._queue_library_text,
                on_notice=lambda text: self.set_status(text),
            )
            self.library_panel.pack(fill="both", expand=True)
        else:
            ttk.Label(self.library_tab, text="History could not open. Check access to your companion data folder.",
                      wraplength=600).pack(padx=16, pady=16)
        privacy = ttk.Frame(self.root)
        privacy.pack(side="bottom", fill="x", padx=14, pady=(0, 8), before=self.tabs)
        self.history_var = tk.BooleanVar(value=self.history_enabled)
        ttk.Checkbutton(privacy, text="Save new requests in local History (this session)",
                        variable=self.history_var, command=self._toggle_history).pack(side="left")
        ttk.Label(privacy, text="No audio is stored in History.").pack(side="right")

        parent = self.writing_tab
        # Header Frame
        hdr = tk.Frame(parent, bg="#111827", padx=16, pady=12, highlightthickness=1, highlightbackground="#374151")
        hdr.pack(fill="x", padx=14, pady=(14, 8))

        title_lbl = tk.Label(hdr, text="🎙️ ESP32 Voice Compose & Dictate", font=("Segoe UI", 13, "bold"), fg="#F9FAFB", bg="#111827")
        title_lbl.pack(anchor="w")

        sub_text = f"Hardware Satellite Companion  •  Mic: {self.audio_capture.device_name}  •  WASAPI Native"
        sub_lbl = tk.Label(hdr, text=sub_text, font=("Segoe UI", 8), fg="#9CA3AF", bg="#111827")
        sub_lbl.pack(anchor="w", pady=(2, 0))

        self.receiver_lbl = tk.Label(
            hdr,
            text="Voice receiver: starting…",
            font=("Segoe UI", 8),
            fg="#FBBF24",
            bg="#111827",
        )
        self.receiver_lbl.pack(anchor="w", pady=(4, 0))

        # Status Bar Card
        status_card = tk.Frame(parent, bg="#1F2937", padx=14, pady=10, highlightthickness=1, highlightbackground="#374151")
        status_card.pack(fill="x", padx=14, pady=6)

        self.status_dot = tk.Label(status_card, text="●", font=("Segoe UI", 14), fg="#10B981", bg="#1F2937")
        self.status_dot.pack(side="left", padx=(0, 8))

        self.status_lbl = tk.Label(status_card, text="READY: Waiting for button press...", font=("Segoe UI", 10, "bold"), fg="#F9FAFB", bg="#1F2937")
        self.status_lbl.pack(side="left")

        # Quick Test Button Bar
        btn_frame = tk.Frame(parent, bg="#0B0F19")
        btn_frame.pack(fill="x", padx=14, pady=8)

        self.btn_compose = tk.Button(
            btn_frame,
            text="🎙️ COMPOSE (Click to Speak)",
            font=("Segoe UI", 10, "bold"),
            bg="#D97706",
            fg="#FFFFFF",
            activebackground="#B45309",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=14,
            pady=8,
            cursor="hand2",
            command=self.toggle_compose_ui,
        )
        self.btn_compose.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.btn_dictate = tk.Button(
            btn_frame,
            text="📝 DICTATE (Click to Speak)",
            font=("Segoe UI", 10, "bold"),
            bg="#0891B2",
            fg="#FFFFFF",
            activebackground="#0E7490",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=14,
            pady=8,
            cursor="hand2",
            command=self.toggle_dictate_ui,
        )
        self.btn_dictate.pack(side="left", expand=True, fill="x", padx=6)

        self.btn_paste = tk.Button(
            btn_frame,
            text="📋 PASTE READY",
            font=("Segoe UI", 10, "bold"),
            bg="#059669",
            fg="#FFFFFF",
            activebackground="#047857",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=14,
            pady=8,
            cursor="hand2",
            command=self.inject_paste_ui,
        )
        self.btn_paste.pack(side="left", expand=True, fill="x", padx=(6, 0))

        # Instructions / Shortcut Guide
        guide_frame = tk.Frame(parent, bg="#111827", padx=12, pady=8, highlightthickness=1, highlightbackground="#1F2937")
        guide_frame.pack(fill="x", padx=14, pady=4)

        guide_txt = (
            "ESP32 Page 6: Tap or Hold 'COMPOSE' or 'DICTATE'.\n"
            "PC Keyboard Shortcuts: F13 or Ctrl+Alt+Shift+F9 (Compose)  •  F14 or Ctrl+Alt+Shift+F10 (Dictate)  •  F15 or Ctrl+Alt+Shift+F11 (Paste)"
        )
        tk.Label(guide_frame, text=guide_txt, font=("Segoe UI", 8), fg="#9CA3AF", bg="#111827", justify="left", wraplength=650).pack(anchor="w")

        # Live Event Log
        log_header = tk.Label(parent, text="LIVE EVENT & TRANSCRIPT LOG:", font=("Segoe UI", 9, "bold"), fg="#9CA3AF", bg="#0B0F19")
        log_header.pack(anchor="w", padx=16, pady=(10, 2))

        self.log_box = scrolledtext.ScrolledText(
            parent,
            bg="#030712",
            fg="#E5E7EB",
            font=("Consolas", 9),
            insertbackground="#FFFFFF",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#374151",
            padx=10,
            pady=8,
            height=8,
        )
        self.log_box.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    def log(self, text: str, content: bool = False):
        if not content:
            logging.info("%s", text)
        t_str = time.strftime("%H:%M:%S")
        msg = f"[{t_str}] {text}\n"
        self._ui_events.put((self._append_log, (msg,)))

    def _post_ui(self, callback, *args):
        if not self._stop_poller:
            self._ui_events.put((callback, args))

    def _toggle_history(self):
        self.history_enabled = self.history_var.get()

    def _record_history(self, mode, request, response, provider="", status="completed"):
        if getattr(self, "_stop_poller", False):
            return None
        if getattr(self, "history", None) is not None:
            self._post_ui(self._refresh_library)
        if not getattr(self, "history_enabled", False) or getattr(self, "history", None) is None:
            return None
        try:
            entry_id = self.history.add_entry(mode, request, response, provider, status)
            self._post_ui(self._refresh_library)
            return entry_id
        except Exception:
            self.log("Could not save this response to History. The result remains available in this session.")
            return None

    def _refresh_library(self):
        if hasattr(self, "library_panel"):
            self.library_panel.refresh()

    def _queue_library_text(self, text):
        if self._busy or self.is_recording:
            raise RuntimeError("Finish the current recording or writing task before queueing text.")
        if not text.strip():
            raise ValueError("There is no response text to queue.")
        if getattr(self, "pending_media", None):
            raise ValueError("Paste or clear the queued image before queueing text.")
        self.pending_ready_payload = text
        self.set_status("READY: Focus your document, then press PASTE READY", "#F59E0B")

    def _toggle_media_recording(self):
        if self.is_recording:
            self.stop_recording_flow()
        elif self.media_service:
            self.start_recording_flow("media")

    def _drain_media_voice_requests(self):
        if self._stop_poller:
            return
        if self.media_store and not self._settings_saving() and not self._busy and not self.is_recording and not self.media_panel._busy:
            for job in reversed(self.media_store.list_jobs()):
                if job['kind'] == 'voice_request' and job['phase'] == 'queued':
                    self.media_store.update_job(job['job_id'], 'interpreting')
                    self.media_panel.ask(job['request'], inbound_job_id=job['job_id'])
                    break
        self.root.after(500, self._drain_media_voice_requests)

    def _queue_media(self, version, target=None):
        if self._busy or self.is_recording:
            raise ValueError("Finish recording or writing before queueing an image.")
        if self.pending_ready_payload:
            raise ValueError("Paste the queued text before queueing an image; text has been retained.")
        if self.pending_media:
            raise ValueError("Paste or clear the queued image first.")
        job = self.media_store.create_job("insert", "Explicit image queue")
        job_id = job["job_id"] if isinstance(job, dict) else job
        self.media_store.update_job(job_id, "insert_queued", version_id=version["version_id"])
        self.pending_media, self.pending_media_job = version, job_id
        self.media_panel.refresh_jobs()
        self.set_status("IMAGE READY: Focus Word or OneNote, then press PASTE READY", "#F59E0B")
        if target and target.get('executable') == 'WINWORD.EXE':
            self._insert_ready_image(target)

    def _clear_media_queue(self):
        if self.pending_media_job:
            self.media_store.update_job(self.pending_media_job, "cancelled")
        self.pending_media = self.pending_media_job = None
        self.media_panel.refresh_jobs()
        self.media_panel.tell("Undispatched image queue cleared.")

    def _insert_ready_image(self, expected_target=None):
        from media_targets import capture_target, insert_image
        job_id, version = self.pending_media_job, self.pending_media
        try:
            target = capture_target()
            if expected_target and any(target.get(key) != expected_target.get(key) for key in ('hwnd','pid','executable','document','start','end')):
                self._report_image_status("Target changed. Image retained in READY; select the destination and press PASTE READY.", "#F59E0B")
                return
        except Exception as error:
            self._report_image_status(str(error) if isinstance(error, ValueError) else "Image target unavailable. Image retained in READY.", "#F59E0B")
            return
        # All checks before dispatch can safely retain the queue. From this point,
        # an exception may follow an insertion and must not cause duplicate retries.
        self.media_store.update_job(job_id, "inserting")
        self.pending_media = self.pending_media_job = None
        try:
            receipt = insert_image(self.media_store.blob_path(version["sha256"]), target)
            self.media_store.update_job(job_id, "completed", receipt=receipt)
            self._report_image_status(receipt["message"])
        except Exception:
            self.media_store.update_job(job_id, "needs_recovery", error="Check the target document before retrying; insertion outcome may be uncertain.")
            self._report_image_status("Check the target document before retrying; image attempt needs recovery.", "#F59E0B")
        self._post_ui(self.media_panel.refresh_jobs)

    def _report_image_status(self, message, colour="#10B981"):
        self.set_status(message, colour)
        self._post_ui(self.media_panel.tell, message)

    def _settings_saving(self):
        return bool(getattr(getattr(self, "settings_panel", None), "_saving", False))

    def _quiesce_sync(self):
        self._sync_stop.set()
        worker = getattr(self, "_sync_thread", None)
        if worker is not None and worker.is_alive():
            worker.join(timeout=18.0)
            if worker.is_alive():
                raise ValueError("Media sync is still finishing a network request. Settings have not changed; wait and save again.")

    def _hermes_values(self, values):
        selected = {key: values.get(key, self.config.get(key, ""))
                    for key in ("HERMES_ENABLED", "HERMES_URL", "HERMES_TOKEN", "LOCAL_ONLY")}
        selected["HERMES_ENABLED"] = truthy(selected["HERMES_ENABLED"])
        selected["LOCAL_ONLY"] = truthy(selected["LOCAL_ONLY"])
        return selected

    def _validate_settings_before_save(self, values):
        if (self._busy or self.is_recording or
                (hasattr(self, "media_panel") and self.media_panel._busy) or
                (hasattr(self, "assistant_panel") and self.assistant_panel._busy) or
                (hasattr(self, "hermes_panel") and self.hermes_panel._busy)):
            raise ValueError("Finish recording, media and Hermes operations before applying settings.")
        old_hermes = self._hermes_values(self.config)
        new_hermes = self._hermes_values(values)
        if self.hermes_service is not None:
            try:
                self.hermes_service.update_config(new_hermes)
            except HermesServiceError as error:
                raise ValueError(str(error)) from None

        try:
            self._quiesce_sync()
            if new_hermes["LOCAL_ONLY"]:
                receiver = getattr(self, "receiver", None)
                if receiver is not None and receiver.owns_process:
                    receiver.stop()
                bridge = getattr(self, "voice_bridge", None)
                if bridge is not None:
                    bridge.close()
                    self.voice_bridge = None
        except Exception:
            if self.hermes_service is not None:
                self.hermes_service.update_config(old_hermes)
            raise

        def rollback():
            if self.hermes_service is not None:
                self.hermes_service.update_config(old_hermes)
            self._post_ui(self._configure_media_sync)
        return rollback

    def _apply_saved_settings(self, values):
        self.config.update(values)
        self.local_only = truthy(self.config.get("LOCAL_ONLY"))
        self.speech_pipeline.local_only = self.local_only
        self.llm_pipeline.local_only = self.local_only
        self.assistant_service.config.update(values)
        if self.media_service:
            self.media_service.config = dict(self.config)
        self._configure_media_sync()
        if self.local_only:
            self.receiver_lbl.configure(text="Local-only mode: feature voice receiver paused; use the PC microphone or BLE controls.")
        if hasattr(self, "hermes_panel"):
            self.hermes_panel._sync_controls()
            if truthy(self.config.get("HERMES_ENABLED")):
                self.hermes_panel.set_notice("Hermes settings updated. Test the connection before sending a task.")

    def _start_hermes_service(self):
        config = dict(self.config)
        root = data_directory()
        threading.Thread(target=self._hermes_service_worker, args=(config, root), daemon=True).start()

    def _hermes_service_worker(self, config, root):
        try:
            service = HermesService(config, root)
            if self._stop_poller:
                service.close()
                return
            self._post_ui(self._hermes_service_created, service)
        except Exception:
            self._post_ui(self.hermes_panel.set_notice,
                          "Hermes local request storage is unavailable. Other companion features remain usable.")

    def _hermes_service_created(self, service):
        if self._stop_poller:
            service.close()
            return
        config = self._hermes_values(self.config)
        threading.Thread(target=self._configure_hermes_worker, args=(service, config), daemon=True).start()

    def _configure_hermes_worker(self, service, config):
        try:
            service.update_config(config)
            if not self._stop_poller:
                self._post_ui(self._hermes_service_ready, service)
            else:
                service.close()
        except Exception:
            service.close()
            self._post_ui(self.hermes_panel.set_notice,
                          "Hermes could not load safely. Review its settings and unresolved requests.")

    def _hermes_service_ready(self, service):
        if self._stop_poller:
            service.close()
            return
        latest = self._hermes_values(self.config)
        if any(service.config.get(key) != value for key, value in latest.items()):
            threading.Thread(target=self._configure_hermes_worker, args=(service, latest), daemon=True).start()
            return
        self.hermes_service = service
        self.hermes_panel.set_service(service)

    def _configure_media_sync(self):
        self._sync_stop.set()
        stop = threading.Event()
        self._sync_stop = stop
        if not self.media_service:
            return
        self.media_service.sync = None
        if self.local_only:
            self.settings_panel.set_status("Local-only mode is active. Hermes, Groq, web, image providers and media sync make no remote calls.")
            return
        if not truthy(self.config.get("MEDIA_SYNC_ENABLED")):
            self.settings_panel.set_status("Automatic sync is disabled. Media stays on this computer. Restart after changing text-provider keys or hardware options.")
            return
        try:
            client = SyncClient(self.media_store, self.config.get("MEDIA_SERVER_URL", ""), self.config.get("MEDIA_SERVER_TOKEN", ""),
                local_only=False, allow_private_sync=True)
            client.cancel_event = stop
            self.media_service.sync = client
        except Exception:
            self.settings_panel.set_status("Sync could not be configured. Use a private HTTPS URL (loopback HTTP is allowed for tests) and the media-server token.")
            return
        def sync_worker():
            try:
                while not stop.is_set():
                    try:
                        result = client.sync_once()
                        text = "Automatic sync: " + str(result)
                    except Exception:
                        text = "Private sync unavailable. Cached media remains usable; check server access and credentials."
                    if not stop.is_set():
                        self._post_ui(self.settings_panel.set_status, text)
                        self._post_ui(self.media_panel.refresh)
                    stop.wait(20)
            finally:
                client.close()
        self._sync_thread = threading.Thread(target=sync_worker, daemon=True)
        self._sync_thread.start()

    def _assistant_status(self):
        # Return only explicit diagnostic fields: no config, keys, document or log content.
        receiver = getattr(self, "receiver", None)
        return {
            "application": "ESP32 Classroom Companion",
            "recording": self.is_recording,
            "writing_busy": self._busy,
            "microphone_configured": bool(getattr(self.audio_capture, "device_name", "")),
            "processing_policy": "local_only" if self.local_only else "cloud_permitted",
            "history_available": self.history is not None,
            "save_new_history": self.history_enabled,
            "paste_ready": bool(self.pending_ready_payload),
            "receiver_port_open": bool(receiver and receiver.is_listening()),
            "receiver_note": "An open port does not verify receiver identity or backend health.",
            "device_configuration": "Firmware-defined pages; runtime button updates are not implemented.",
            "bluetooth": "Not verified by this diagnostic; use a hardware shortcut to test.",
        }

    def _append_log(self, msg: str):
        self.log_box.insert("end", msg)
        self.log_box.see("end")

    def set_status(self, text: str, dot_color: str = "#10B981"):
        self._ui_events.put((self._update_status, (text, dot_color)))

    def _update_status(self, text: str, dot_color: str):
        self.status_lbl.config(text=text)
        self.status_dot.config(fg=dot_color)
        self.global_status_lbl.configure(text=text)
        self.global_status_dot.configure(fg=dot_color)

    def _resize_global_status(self, event):
        if event.widget is self.root:
            self.global_status_lbl.configure(wraplength=max(280, event.width - 60))

    # ── UI Button Actions ───────────────────────────────────────────────

    def toggle_compose_ui(self):
        if not self.is_recording:
            # Capture focus BEFORE starting recording
            self.start_recording_flow("compose")
        else:
            self.stop_recording_flow()

    def toggle_dictate_ui(self):
        if not self.is_recording:
            self.start_recording_flow("dictate")
        else:
            self.stop_recording_flow()

    def inject_paste_ui(self):
        if self._busy or self.is_recording:
            self.log("Finish the current operation before pasting.")
            return
        if getattr(self, "pending_media", None):
            self._insert_ready_image()
            return
        payload = self.pending_ready_payload
        if not payload:
            self.log("Ready queue is empty. Nothing to paste.")
            return
        # Only the explicit Paste Ready gesture may restore a document window.
        snap = FocusTracker.get_focus_snapshot()
        if snap.get("pid") == os.getpid():
            target = getattr(self, "_last_external_snap", None)
            if not target or not FocusTracker.restore_focus(target) or not FocusTracker.is_focus_matched(target):
                self.set_status("READY: Focus your document, then press PASTE READY", "#F59E0B")
                return
        if ClipboardManager.inject_paste(payload, restore_delay=self.restore_delay):
            self.pending_ready_payload = None
            self.set_status("Paste shortcut sent", "#10B981")
        else:
            self.set_status("Paste failed; text retained in READY", "#EF4444")

    def _deliver_result(self, text, focus_snap):
        self.pending_ready_payload = text
        if focus_snap and FocusTracker.is_focus_matched(focus_snap):
            if ClipboardManager.inject_paste(text, restore_delay=self.restore_delay):
                self.pending_ready_payload = None
                self.log("Paste shortcut sent to the original document.")
                self.set_status("COMPLETED: Paste shortcut sent", "#10B981")
                return
        self.log("Text retained in READY. Focus your document and press PASTE READY.")
        self.set_status("READY: Focus document, then press PASTE READY", "#F59E0B")

    def _drain_ui_events(self):
        for _ in range(100):
            try:
                callback, args = self._ui_events.get_nowait()
            except queue.Empty:
                break
            try:
                callback(*args)
            except Exception:
                logging.exception("Companion UI action failed")
                self._update_status("Action failed; see companion.log", "#EF4444")
        if not self._stop_poller:
            self.root.after(20, self._drain_ui_events)

    def _watch_receiver(self):
        if self._stop_poller or self.local_only or self._settings_saving():
            return
        self._receiver_watch_ticks += 1
        if self.receiver.is_listening():
            note = "Closing this window stops it." if self.receiver.owns_process else "Already running; closing this window leaves it running."
            self.receiver_lbl.config(text=f"Voice receiver: running on port {self.receiver.port}. {note}", fg="#34D399")
            return
        if self.receiver.exited():
            self.receiver_lbl.config(text="Voice receiver stopped. See receiver.log", fg="#F87171")
            self.log("Voice receiver exited. See tools/compose/receiver.log")
            return
        if self._receiver_watch_ticks < 60:
            self.root.after(1000, self._watch_receiver)
            return
        self.receiver_lbl.config(text="Voice receiver is still starting. See receiver.log", fg="#FBBF24")

    def close(self):
        if self._settings_saving():
            self.settings_panel.set_status("Settings are still being protected. Wait for saving to finish, then close again.")
            return
        self._stop_poller = True
        if hasattr(self, "_sync_stop"):
            self._sync_stop.set()
        if hasattr(self, "media_panel"):
            self.media_panel.close()
        if hasattr(self, "assistant_panel"):
            self.assistant_panel.close()
        if hasattr(self, "hermes_panel"):
            self.hermes_panel.close()
        if hasattr(self, "settings_panel"):
            self.settings_panel.close()
        if getattr(self, "hermes_service", None):
            self.hermes_service.close()
        if self._recording_timer is not None:
            self.root.after_cancel(self._recording_timer)
        self.audio_capture.stop_recording()
        if hasattr(self, "receiver"):
            self.receiver.stop()
        if getattr(self, "voice_bridge", None):
            self.voice_bridge.close()
        self.root.destroy()

    # ── Unified Recording & Synthesis Pipeline ──────────────────────────

    def start_recording_flow(self, mode: str = "compose"):
        if self.is_recording or self._busy or self._settings_saving():
            return
        if not self.audio_capture.start_recording():
            self.log("Microphone could not open. Check Windows microphone permissions and device selection.")
            self.set_status("ERROR: Could not open microphone", "#EF4444")
            return
        self.is_recording = True
        self.recording_mode = mode
        self._media_request_target = None
        if mode == 'media':
            try:
                from media_targets import capture_target
                self._media_request_target = capture_target()
            except Exception:
                pass

        # Snapshot window focus and selected text safely
        try:
            self._target_focus_snap = FocusTracker.get_focus_snapshot()
            if self._target_focus_snap.get("pid") == os.getpid():
                previous = getattr(self, "_last_external_snap", None)
                self._target_focus_snap = None
                if mode != "media" and previous and FocusTracker.restore_focus(previous) and FocusTracker.is_focus_matched(previous):
                    self._target_focus_snap = FocusTracker.get_focus_snapshot()
            fg_hwnd = self._target_focus_snap.get("hwnd", 0) if self._target_focus_snap else 0
            self._target_selected_text = FocusTracker.capture_selected_text(fg_hwnd) if mode == "compose" and fg_hwnd else ""
        except Exception as e:
            self._target_focus_snap = None
            self._target_selected_text = ""

        self._recording_timer = self.root.after(60000, self.stop_recording_flow)

        if mode == "compose":
            if self._target_selected_text:
                preview = self._target_selected_text.strip().replace("\n", " ")
                if len(preview) > 60:
                    preview = preview[:57] + "..."
                self.log(f"📋 Context captured from document ({len(self._target_selected_text)} chars): \"{preview}\"", content=True)
            else:
                self.log("📋 Context: No text selected in document.")
            self.set_status("RECORDING (Compose)... Speak prompt, click again to write!", "#F59E0B")
            self.btn_compose.config(text="🛑 FINISH RECORDING", bg="#DC2626")
            self.log(">>> RECORDING STARTED (Compose) <<< Speak your instruction into your microphone...")
        elif mode == "media":
            self.set_status("RECORDING (Media request)... Speak, then finish recording.", "#06B6D4")
        else:
            self.set_status("RECORDING (Dictate)... Speak text, click again to paste!", "#06B6D4")
            self.btn_dictate.config(text="🛑 FINISH RECORDING", bg="#DC2626")
            self.log(">>> RECORDING STARTED (Dictate) <<< Speak verbatim text into your microphone...")

    def stop_recording_flow(self):
        if not self.is_recording:
            return
        self.is_recording = False
        if self._recording_timer is not None:
            self.root.after_cancel(self._recording_timer)
            self._recording_timer = None

        self.btn_compose.config(text="🎙️ COMPOSE (Click to Speak)", bg="#D97706")
        self.btn_dictate.config(text="📝 DICTATE (Click to Speak)", bg="#0891B2")

        wav_bytes, dur, rms = self.audio_capture.stop_recording()
        self.log(f"Recording stopped. Duration: {dur:.2f}s | RMS: {rms:.1f} | Captured {len(wav_bytes)} bytes")

        if dur < 0.20:
            self.log("Recording too short (<0.2s), dropped.")
            self.set_status("READY: Waiting for button press...", "#10B981")
            return

        mode = self.recording_mode
        focus_snap = self._target_focus_snap
        sel_txt = self._target_selected_text

        self._busy = True
        # Run transcription & synthesis in background worker thread
        threading.Thread(
            target=self._process_pipeline_worker,
            args=(mode, wav_bytes, focus_snap, sel_txt),
            daemon=True,
        ).start()

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
        if hasattr(self, "assistant_service"):
            self.assistant_service.config["LOCAL_ONLY"] = "1"
        if getattr(self, "media_service", None):
            self.media_service.config["LOCAL_ONLY"] = "1"
        self.log("Cloud services are unreachable. Using local Whisper and Ollama for the rest of this session.")

    def _process_pipeline_worker(self, mode: str, wav_bytes: bytes, focus_snap: dict | None, selected_text: str):
        transcript = ""
        try:
            self.set_status("TRANSCRIBING: Sending speech to Whisper...", "#8B5CF6")
            self.log("Transcribing audio via Speech Pipeline...")
            transcript, stt_prov, stt_lat = self.speech_pipeline.transcribe(wav_bytes)

            if not transcript.strip():
                self.log("⚠️ No speech detected in recording.")
                self.set_status("No speech detected", "#EF4444")
                return

            self.log(f"Transcript ({stt_prov}, {stt_lat:.2f}s): \"{transcript}\"", content=True)
            self._stay_local_if_cloud_blocked()

            if mode == "media":
                target = getattr(self, '_media_request_target', None)
                self._post_ui(lambda: self.media_panel.ask(transcript, target=target))
                return
            if mode == "compose":
                web_context = ""
                grounding = getattr(self, "web_grounding", None)
                if grounding is not None:
                    self.set_status("ROUTING: Checking if live web info is needed...", "#8B5CF6")
                    web = grounding.fetch_context(
                        transcript, selected_text, local_only=self.local_only,
                        on_status=lambda msg: self.set_status(f"SEARCHING: {msg}", "#3B82F6"),
                    )
                    self.log(web.summary())
                    web_context = web.context

                self.set_status("WRITING: Synthesizing response with LLM...", "#8B5CF6")
                self.log("Building prompt and generating response with LLM...")
                messages = build_compose_messages(transcript, selected_text, web_context)
                reply, llm_prov, llm_lat, parts = self.llm_pipeline.generate(messages, temperature=0.3)
                self._stay_local_if_cloud_blocked()

                if not reply.strip():
                    self.log("⚠️ LLM returned empty reply.")
                    self.set_status("LLM returned empty reply", "#EF4444")
                    return

                self.log(f"Generated text ({llm_prov}, {llm_lat:.2f}s, {len(reply)} chars):")
                self.log(f"--- PREVIEW ---\n{reply}\n---------------", content=True)

                self._record_history("compose", transcript, reply, llm_prov)
                self._ui_events.put((self._deliver_result, (reply, focus_snap)))

            else:  # Dictate
                self.set_status("CLEANING: Polishing verbatim text...", "#8B5CF6")
                self.log("Running Grammar Guard and formatting dictate output...")
                messages = build_dictate_messages(transcript)
                llm_prov = "original transcript"
                try:
                    candidate, llm_prov, llm_lat, _ = self.llm_pipeline.generate(messages, temperature=0.0)
                except Exception:
                    self.log("Grammar cleanup unavailable; retaining the original transcript.")
                    candidate = transcript
                self._stay_local_if_cloud_blocked()

                final_text = verify_dictate_overlap(transcript, candidate)
                self.log(f"Dictate output: {final_text}", content=True)
                self._record_history("dictate", transcript, final_text, f"{stt_prov}; {llm_prov}")
                self._ui_events.put((self._deliver_result, (final_text, focus_snap)))

        except Exception as e:
            self._record_history(mode, transcript, "Writing could not complete.", status="failed")
            self.log(f"Pipeline failed ({type(e).__name__}). Check the microphone and processing provider.")
            self.set_status("Writing failed; check microphone and processing provider", "#EF4444")
        finally:
            self._ui_events.put((self._pipeline_finished, ()))

    def _pipeline_finished(self):
        self._busy = False

    # ── Hardware & Global Hotkey Poller ─────────────────────────────────

    def _remember_external_focus(self):
        if self._stop_poller:
            return
        try:
            snap = FocusTracker.snapshot_foreground_window()
            if snap.get("pid") and snap.get("pid") != os.getpid():
                self._last_external_snap = snap
        except Exception:
            logging.debug("Foreground window tracking unavailable", exc_info=True)
        self.root.after(200, self._remember_external_focus)

    def _handle_hardware_event(self, mode, edge):
        if self._settings_saving():
            return
        self.log(f"[HOTKEY] {mode} {edge}")
        if mode == "compose" and hasattr(self, "media_hotkey") and self.media_hotkey.get():
            mode = "media"
        if mode == "paste":
            if edge == "up":
                self.inject_paste_ui()
        elif edge == "down":
            self.start_recording_flow(mode)
        elif self.is_recording and self.recording_mode == mode:
            self.stop_recording_flow()

    def _hardware_key_poller(self):
        state = HotkeyState()
        user32 = ctypes.windll.user32
        while not self._stop_poller:
            try:
                for mode, edge in state.update(lambda key: bool(user32.GetAsyncKeyState(key) & 0x8000)):
                    self._ui_events.put((self._handle_hardware_event, (mode, edge)))
            except Exception:
                logging.exception("Hardware hotkey polling failed")
            time.sleep(0.015)


if __name__ == "__main__":
    logging.basicConfig(filename=Path(__file__).with_name("companion.log"),
                        level=logging.INFO, encoding="utf-8",
                        format="%(asctime)s %(levelname)s %(message)s")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.wintypes.BOOL, ctypes.wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = ctypes.wintypes.HANDLE
    import hashlib
    instance_name = "Local\\ESP32ComposeGui"
    if os.environ.get("ESP32_COMPANION_DATA_DIR"):
        instance_name += "-" + hashlib.sha256(str(data_directory().resolve()).casefold().encode()).hexdigest()[:12]
    instance_mutex = kernel32.CreateMutexW(None, False, instance_name)
    if not instance_mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        print("The ESP32 companion is already running.")
        sys.exit(0)
    root = tk.Tk()
    app = ComposeApp(root)
    root.mainloop()
