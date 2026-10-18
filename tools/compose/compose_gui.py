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
from web_grounding import WebGrounding


def load_env_config() -> dict:
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


class ComposeApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🎙️ ESP32 Voice Compose & Dictate Companion")
        self.root.geometry("640x540")
        self.root.configure(bg="#0B0F19")
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(300, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()

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

        self.restore_delay = float(self.config.get("CLIPBOARD_RESTORE_DELAY", "0.15"))
        self.pending_ready_payload: str | None = None

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
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(20, self._drain_ui_events)
        self.log(f"Service initialized. Active Microphone: {self.audio_capture.device_name} (WASAPI)")
        provider = "Local Whisper + Ollama" if self.local_only or not self.config.get("GROQ_API_KEY") else "Groq + local fallback"
        self.log(f"Processing: {provider}")
        self.log(self.web_grounding.describe())
        self.log("Ready and listening for ESP32 MacroPad or keyboard hotkeys!")

        # Start hardware key listener thread
        self.poller_thread = threading.Thread(target=self._hardware_key_poller, daemon=True)
        self.poller_thread.start()

    def _build_ui(self):
        # Header Frame
        hdr = tk.Frame(self.root, bg="#111827", padx=16, pady=12, highlightthickness=1, highlightbackground="#374151")
        hdr.pack(fill="x", padx=14, pady=(14, 8))

        title_lbl = tk.Label(hdr, text="🎙️ ESP32 Voice Compose & Dictate", font=("Segoe UI", 13, "bold"), fg="#F9FAFB", bg="#111827")
        title_lbl.pack(anchor="w")

        sub_text = f"Hardware Satellite Companion  •  Mic: {self.audio_capture.device_name}  •  WASAPI Native"
        sub_lbl = tk.Label(hdr, text=sub_text, font=("Segoe UI", 8), fg="#9CA3AF", bg="#111827")
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # Status Bar Card
        status_card = tk.Frame(self.root, bg="#1F2937", padx=14, pady=10, highlightthickness=1, highlightbackground="#374151")
        status_card.pack(fill="x", padx=14, pady=6)

        self.status_dot = tk.Label(status_card, text="●", font=("Segoe UI", 14), fg="#10B981", bg="#1F2937")
        self.status_dot.pack(side="left", padx=(0, 8))

        self.status_lbl = tk.Label(status_card, text="READY: Waiting for button press...", font=("Segoe UI", 10, "bold"), fg="#F9FAFB", bg="#1F2937")
        self.status_lbl.pack(side="left")

        # Quick Test Button Bar
        btn_frame = tk.Frame(self.root, bg="#0B0F19")
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
        guide_frame = tk.Frame(self.root, bg="#111827", padx=12, pady=8, highlightthickness=1, highlightbackground="#1F2937")
        guide_frame.pack(fill="x", padx=14, pady=4)

        guide_txt = (
            "ESP32 Page 6: Tap or Hold 'COMPOSE' or 'DICTATE'.\n"
            "PC Keyboard Shortcuts: F13 or Ctrl+Alt+Shift+F9 (Compose)  •  F14 or Ctrl+Alt+Shift+F10 (Dictate)  •  F15 or Ctrl+Alt+Shift+F11 (Paste)"
        )
        tk.Label(guide_frame, text=guide_txt, font=("Segoe UI", 8), fg="#9CA3AF", bg="#111827", justify="left").pack(anchor="w")

        # Live Event Log
        log_header = tk.Label(self.root, text="LIVE EVENT & TRANSCRIPT LOG:", font=("Segoe UI", 9, "bold"), fg="#9CA3AF", bg="#0B0F19")
        log_header.pack(anchor="w", padx=16, pady=(10, 2))

        self.log_box = scrolledtext.ScrolledText(
            self.root,
            bg="#030712",
            fg="#E5E7EB",
            font=("Consolas", 9),
            insertbackground="#FFFFFF",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#374151",
            padx=10,
            pady=8,
        )
        self.log_box.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    def log(self, text: str):
        logging.info("%s", text)
        t_str = time.strftime("%H:%M:%S")
        msg = f"[{t_str}] {text}\n"
        self._ui_events.put((self._append_log, (msg,)))

    def _append_log(self, msg: str):
        self.log_box.insert("end", msg)
        self.log_box.see("end")

    def set_status(self, text: str, dot_color: str = "#10B981"):
        self._ui_events.put((self._update_status, (text, dot_color)))

    def _update_status(self, text: str, dot_color: str):
        self.status_lbl.config(text=text)
        self.status_dot.config(fg=dot_color)

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
        payload = self.pending_ready_payload
        if not payload:
            self.log("Ready queue is empty. Nothing to paste.")
            return
        # A GUI click focuses this window. Keep the payload until the user
        # returns to their document and presses the hardware Paste Ready key.
        snap = FocusTracker.get_focus_snapshot()
        if snap.get("pid") == os.getpid():
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

    def close(self):
        self._stop_poller = True
        if self._recording_timer is not None:
            self.root.after_cancel(self._recording_timer)
        self.audio_capture.stop_recording()
        self.root.destroy()

    # ── Unified Recording & Synthesis Pipeline ──────────────────────────

    def start_recording_flow(self, mode: str = "compose"):
        if self.is_recording or self._busy:
            return
        if not self.audio_capture.start_recording():
            self.log("Microphone could not open. Check Windows microphone permissions and device selection.")
            self.set_status("ERROR: Could not open microphone", "#EF4444")
            return
        self.is_recording = True
        self.recording_mode = mode

        # Snapshot window focus and selected text safely
        try:
            self._target_focus_snap = FocusTracker.get_focus_snapshot()
            if self._target_focus_snap.get("pid") == os.getpid():
                self._target_focus_snap = None
            fg_hwnd = self._target_focus_snap.get("hwnd", 0) if self._target_focus_snap else 0
            self._target_selected_text = FocusTracker.capture_selected_text(fg_hwnd) if mode == "compose" else ""
        except Exception as e:
            self._target_focus_snap = None
            self._target_selected_text = ""

        self._recording_timer = self.root.after(60000, self.stop_recording_flow)

        if mode == "compose":
            if self._target_selected_text:
                preview = self._target_selected_text.strip().replace("\n", " ")
                if len(preview) > 60:
                    preview = preview[:57] + "..."
                self.log(f"📋 Context captured from document ({len(self._target_selected_text)} chars): \"{preview}\"")
            else:
                self.log("📋 Context: No text selected in document.")
            self.set_status("RECORDING (Compose)... Speak prompt, click again to write!", "#F59E0B")
            self.btn_compose.config(text="🛑 FINISH RECORDING", bg="#DC2626")
            self.log(">>> RECORDING STARTED (Compose) <<< Speak your instruction into your microphone...")
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
        self.log("Cloud services are unreachable. Using local Whisper and Ollama for the rest of this session.")

    def _process_pipeline_worker(self, mode: str, wav_bytes: bytes, focus_snap: dict | None, selected_text: str):
        try:
            self.set_status("TRANSCRIBING: Sending speech to Whisper...", "#8B5CF6")
            self.log("Transcribing audio via Speech Pipeline...")
            transcript, stt_prov, stt_lat = self.speech_pipeline.transcribe(wav_bytes)

            if not transcript.strip():
                self.log("⚠️ No speech detected in recording.")
                self.set_status("No speech detected", "#EF4444")
                return

            self.log(f"Transcript ({stt_prov}, {stt_lat:.2f}s): \"{transcript}\"")
            self._stay_local_if_cloud_blocked()

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
                self.log(f"--- PREVIEW ---\n{reply}\n---------------")

                self._ui_events.put((self._deliver_result, (reply, focus_snap)))

            else:  # Dictate
                self.set_status("CLEANING: Polishing verbatim text...", "#8B5CF6")
                self.log("Running Grammar Guard and formatting dictate output...")
                messages = build_dictate_messages(transcript)
                try:
                    candidate, llm_prov, llm_lat, _ = self.llm_pipeline.generate(messages, temperature=0.0)
                except Exception:
                    self.log("Grammar cleanup unavailable; retaining the original transcript.")
                    candidate = transcript
                self._stay_local_if_cloud_blocked()

                final_text = verify_dictate_overlap(transcript, candidate)
                self.log(f"Dictate output: {final_text}")
                self._ui_events.put((self._deliver_result, (final_text, focus_snap)))

        except Exception as e:
            self.log(f"❌ Pipeline Error: {e}")
            self.set_status(f"Error: {e}", "#EF4444")
        finally:
            self._ui_events.put((self._pipeline_finished, ()))

    def _pipeline_finished(self):
        self._busy = False

    # ── Hardware & Global Hotkey Poller ─────────────────────────────────

    def _handle_hardware_event(self, mode, edge):
        self.log(f"[HOTKEY] {mode} {edge}")
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
    instance_mutex = kernel32.CreateMutexW(None, False, "Local\\ESP32ComposeGui")
    if not instance_mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        print("The ESP32 companion is already running.")
        sys.exit(0)
    root = tk.Tk()
    app = ComposeApp(root)
    root.mainloop()
