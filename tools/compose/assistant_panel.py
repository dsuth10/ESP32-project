"""Embedded assistant UI; all Tk operations stay on the main thread."""

import threading
import tkinter as tk
from tkinter import ttk, scrolledtext

from assistant_service import AssistantService


class AssistantPanel(ttk.Frame):
    def __init__(self, parent, service, post_ui, on_queue, record_history):
        super().__init__(parent, padding=12)
        self.service = service
        self.post_ui = post_ui
        self.on_queue = on_queue
        self.record_history = record_history
        self.conversations = {"ask": [], "manage": []}
        self._busy = False
        self._cancel_event = threading.Event()
        self._last_text = ""
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, sticky="ew")
        self.mode = tk.StringVar(value="Ask / write")
        self.mode_box = ttk.Combobox(toolbar, textvariable=self.mode, state="readonly",
                                    values=("Ask / write", "Manage companion"), width=24)
        self.mode_box.pack(side="left")
        self.mode_box.bind("<<ComboboxSelected>>", self._mode_changed)
        self.new_button = ttk.Button(toolbar, text="New conversation", command=self.new_conversation)
        self.new_button.pack(side="right")
        self.policy_label = ttk.Label(self, wraplength=760)
        self.policy_label.grid(row=1, column=0, sticky="ew", pady=8)

        self.chat = scrolledtext.ScrolledText(self, wrap="word", state="disabled", height=12,
                                              font=("Segoe UI", 11))
        self.chat.grid(row=2, column=0, sticky="nsew")
        ttk.Label(self, text="Your request (Ctrl+Enter to send)").grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.prompt = scrolledtext.ScrolledText(self, wrap="word", height=4, font=("Segoe UI", 11))
        self.prompt.grid(row=4, column=0, sticky="ew", pady=(4, 5))
        self.prompt.bind("<Control-Return>", self._send_shortcut)

        self.allow_history = tk.BooleanVar(value=False)
        self.history_check = ttk.Checkbutton(
            self, text="Allow History search for this request (matching text goes to the selected AI)",
            variable=self.allow_history,
        )
        self.history_check.grid(row=5, column=0, sticky="w")
        controls = ttk.Frame(self)
        controls.grid(row=6, column=0, sticky="ew", pady=8)
        self.send_button = ttk.Button(controls, text="Send (Ctrl+Enter)", command=self.send)
        self.send_button.pack(side="left")
        self.copy_button = ttk.Button(controls, text="Copy response", command=self.copy_response, state="disabled")
        self.copy_button.pack(side="left", padx=8)
        self.queue_button = ttk.Button(controls, text="Queue for Paste Ready", command=self.queue_response, state="disabled")
        self.queue_button.pack(side="left")
        self.notice = ttk.Label(self, text="", wraplength=760)
        self.notice.grid(row=7, column=0, sticky="ew")
        self._mode_changed()
        self._append("Companion", "Ask for writing, or choose Manage companion to check status and save text. "
                     "Handheld button/page changes are not available in this first version.")

    def _mode_changed(self, _event=None):
        manage = self.mode.get() == "Manage companion"
        self.history_check.configure(state="normal" if manage and not self._busy else "disabled")
        self.allow_history.set(False)
        config = self.service.config
        local = AssistantService._truthy(config.get("LOCAL_ONLY")) or not config.get("GROQ_API_KEY")
        destination = "Configured Ollama endpoint" if local else "Groq cloud"
        detail = ("Can inspect status and save text. History search requires the checkbox below."
                  if manage else "Writing only; no management tools or access to retained History. No live web search.")
        self.policy_label.configure(text=f"{destination}. Your request and this mode's recent conversation are sent for processing. {detail}")

    def _append(self, author, text):
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{author}\n{text}\n\n")
        self.chat.see("end")
        self.chat.configure(state="disabled")

    def _send_shortcut(self, _event):
        self.send()
        return "break"

    def send(self):
        if getattr(self, "settings_saving", lambda: False)():
            self.notice.configure(text="Wait until settings have finished saving.")
            return
        if self._busy:
            return
        prompt = self.prompt.get("1.0", "end-1c").strip()
        if not prompt or len(prompt) > 16000:
            self.notice.configure(text="Enter a request of 1–16000 characters.")
            return
        mode = "manage" if self.mode.get() == "Manage companion" else "ask"
        config = dict(self.service.config)
        config["ASSISTANT_HISTORY_ACCESS"] = mode == "manage" and self.allow_history.get()
        request_service = AssistantService(config, self.service.status_provider, self.service.store,
                                           cancel_event=self._cancel_event)
        conversation = list(self.conversations[mode][-8:])
        self._busy = True
        self.send_button.configure(state="disabled")
        self.new_button.configure(state="disabled")
        self.mode_box.configure(state="disabled")
        self.history_check.configure(state="disabled")
        self.allow_history.set(False)
        self.prompt.delete("1.0", "end")
        self._append("You · " + self.mode.get(), prompt)
        self.notice.configure(text="Working… Compose and Dictate remain available in their tab.")
        threading.Thread(target=self._worker, args=(request_service, prompt, mode, conversation), daemon=True).start()

    def _worker(self, service, prompt, mode, conversation):
        try:
            result = service.reply(prompt, mode=mode, conversation=conversation)
            if not self._cancel_event.is_set():
                self.record_history("assistant_" + mode, prompt, result["text"], result["provider"],
                                    "completed" if result.get("ok", True) else "failed")
        except Exception:
            result = {"text": "The assistant could not finish this request. Please try again.",
                      "provider": "unavailable", "actions": [], "ok": False}
        finally:
            service.session.close()
        if not self._cancel_event.is_set():
            self.post_ui(self._finished, prompt, mode, result)

    def _finished(self, prompt, mode, result):
        self._busy = False
        self._last_text = result["text"]
        self._append("Companion · " + result["provider"], self._last_text)
        if result.get("actions"):
            self._append("Operations performed", "\n".join(result["actions"]))
        if result.get("ok", True):
            self.conversations[mode].extend(({"role": "user", "content": prompt},
                                             {"role": "assistant", "content": self._last_text}))
            self.conversations[mode] = self.conversations[mode][-8:]
        self.send_button.configure(state="normal")
        self.new_button.configure(state="normal")
        self.mode_box.configure(state="readonly")
        self.copy_button.configure(state="normal")
        self.queue_button.configure(state="normal")
        self._mode_changed()
        self.notice.configure(text="Response retained here. Copy it or queue it for deliberate pasting."
                              if result.get("ok", True) else "Request did not complete. Any operations listed above already occurred.")

    def new_conversation(self):
        if self._busy:
            return
        self.conversations = {"ask": [], "manage": []}
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")
        self._last_text = ""
        self.copy_button.configure(state="disabled")
        self.queue_button.configure(state="disabled")
        self.allow_history.set(False)
        self.notice.configure(text="New conversation. Stored History is unchanged.")

    def close(self):
        self._cancel_event.set()
        self.service.session.close()

    def copy_response(self):
        if self._last_text:
            self.clipboard_clear()
            self.clipboard_append(self._last_text)
            self.notice.configure(text="Response copied to the clipboard.")

    def queue_response(self):
        try:
            self.on_queue(self._last_text)
        except Exception:
            self.notice.configure(text="Finish any recording or writing task before queueing a response.")
        else:
            self.notice.configure(text="Queued. Focus your document and press the hardware or keyboard Paste Ready shortcut.")
