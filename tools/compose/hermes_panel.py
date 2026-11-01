"""Explicit Hermes task UI. Work and callbacks are kept off the Tk worker path."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, scrolledtext

from board_theme_tokens import style_tk_text


class HermesPanel(ttk.Frame):
    def __init__(self, parent, service, post_ui, queue_text, local_only, settings_saving, enabled,
                 review_library=None):
        super().__init__(parent, padding=12)
        self.service = service
        self.post_ui = post_ui
        self.queue_text = queue_text
        self.review_library = review_library
        self.local_only = local_only
        self.settings_saving = settings_saving
        self.enabled = enabled
        self._busy = False
        self._closed = False
        self._operation_generation = 0
        self._operation_request = None
        self._restoring_selection = False
        self._active_request = None
        self._prepared_request = None
        self._active_run_id = None
        self._selected_status = ""
        self._prepared_task = ""
        self._prepared_context = ""
        self._result_text = ""
        self._result_request_id = None
        self._selected_context = ''
        self.columnconfigure(0, weight=1)
        self.rowconfigure(7, weight=2)

        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Hermes sends only the task and selected context shown here. Groq Ask and local History stay separate.",
                  wraplength=760).grid(row=0, column=0, sticky="w")
        ttk.Button(header, text="Test connection", command=self.test_connection).grid(row=0, column=1, padx=4)
        ttk.Button(header, text="Refresh runs", command=self.refresh_runs).grid(row=0, column=2, padx=4)
        self.notice = ttk.Label(self, text="Hermes setup is loading. Configure an HTTPS endpoint and protected token in Settings.",
                                wraplength=760, justify="left")
        self.notice.grid(row=1, column=0, sticky="ew", pady=(7, 5))

        ttk.Label(self, text="Teacher task (required)").grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.task = scrolledtext.ScrolledText(self, wrap="word", height=4, font=("Segoe UI", 10))
        style_tk_text(self.task)
        self.task.grid(row=3, column=0, sticky="ew", pady=(3, 5))
        ttk.Label(self, text="Selected context (optional; review before sending; History is never copied)").grid(
            row=4, column=0, sticky="nw", pady=(4, 0))
        self.context = scrolledtext.ScrolledText(self, wrap="word", height=3, font=("Segoe UI", 10))
        style_tk_text(self.context)
        self.context.grid(row=5, column=0, sticky="ew", pady=(3, 5))

        controls = ttk.Frame(self)
        controls.grid(row=6, column=0, sticky="ew", pady=5)
        self.prepare_button = ttk.Button(controls, text="Prepare preview", command=self.prepare)
        self.prepare_button.pack(side="left")
        self.submit_button = ttk.Button(controls, text="Send this prepared task", command=self.submit, state="disabled")
        self.submit_button.pack(side="left", padx=5)
        self.status_line = ttk.Label(controls, text="No task prepared.")
        self.status_line.pack(side="left", padx=8)

        body = ttk.Panedwindow(self, orient="horizontal")
        body.grid(row=7, column=0, sticky="nsew", pady=5)
        request_frame = ttk.Frame(body, padding=(0, 0, 5, 0))
        detail_frame = ttk.Frame(body, padding=(5, 0, 0, 0))
        request_frame.columnconfigure(0, weight=1)
        request_frame.rowconfigure(1, weight=1)
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(1, weight=1)
        body.add(request_frame, weight=1)
        body.add(detail_frame, weight=2)
        ttk.Label(request_frame, text="Saved runs").grid(row=0, column=0, sticky="w")
        self.runs = ttk.Treeview(request_frame, columns=("status", "created"), show="tree headings", height=8)
        self.runs.heading("#0", text="Request")
        self.runs.heading("status", text="Status")
        self.runs.heading("created", text="Created")
        self.runs.column("#0", width=150, stretch=True)
        self.runs.column("status", width=105, stretch=False)
        self.runs.column("created", width=130, stretch=False)
        self.runs.grid(row=1, column=0, sticky="nsew")
        self.runs.bind("<<TreeviewSelect>>", self._selected)

        actions = ttk.Frame(detail_frame)
        actions.grid(row=0, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        ttk.Button(actions, text="Refresh status and events", command=self.refresh_active).grid(
            row=0, column=0, sticky="ew", padx=2, pady=2)
        self.stop_button = ttk.Button(actions, text="Request cancellation", command=self.stop_active, state="disabled")
        self.stop_button.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        self.discard_button = ttk.Button(actions, text="Discard unsent preview", command=self.discard_active, state="disabled")
        self.discard_button.grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        self.queue_button = ttk.Button(actions, text="Queue result for Paste Ready", command=self.queue_result, state="disabled")
        self.queue_button.grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        self.details = scrolledtext.ScrolledText(detail_frame, wrap="word", height=12, state="disabled", font=("Segoe UI", 9))
        style_tk_text(self.details)
        self.details.grid(row=1, column=0, sticky="nsew", pady=(4, 0))

    def set_service(self, service):
        if self._closed:
            service.close()
            return
        self.service = service
        if self.local_only():
            self.set_notice("Local-only mode is active. Hermes remains disconnected until it is turned off.")
        elif not self.enabled():
            self.set_notice("Enable Hermes in Settings before testing or preparing a task.")
        else:
            self.set_notice("Connection status is unverified until you test the configured Hermes endpoint.")
        self.refresh_runs()

    def set_notice(self, text):
        if not self._closed:
            self.notice.configure(text=text)

    def _blocked(self):
        if self.service is None:
            self.set_notice("Hermes local request storage is not ready.")
            return True
        if self.local_only():
            self.set_notice("Local-only mode is active. Hermes network calls are disabled.")
            return True
        if not self.enabled():
            self.set_notice("Enable Hermes in Settings before testing or preparing a task.")
            return True
        if self.settings_saving():
            self.set_notice("Settings are being checked and saved. Wait before starting another Hermes action.")
            return True
        return False

    def _start(self, operation, callback, request_id=None):
        if self._closed or self._busy:
            return False
        self._busy = True
        self._operation_generation += 1
        generation = self._operation_generation
        self._operation_request = request_id
        self.prepare_button.configure(state="disabled")
        self.submit_button.configure(state="disabled")
        threading.Thread(target=self._worker, args=(operation, callback, request_id, generation), daemon=True).start()
        return True

    def _worker(self, operation, callback, request_id, generation):
        try:
            result = operation()
            error = None
        except Exception:
            result = None
            error = "Hermes could not complete that action. Check the endpoint, credentials and saved run status."
        if not self._closed:
            self.post_ui(self._finished, callback, result, error, request_id, generation)

    def _finished(self, callback, result, error, request_id=None, generation=None):
        if self._closed:
            return
        if generation is not None and generation != self._operation_generation:
            return
        self._busy = False
        self._operation_request = None
        if request_id is not None and request_id != self._active_request:
            self._sync_controls()
            return
        self.prepare_button.configure(state="normal")
        if error:
            self.set_notice(error)
            self._sync_controls()
            return
        callback(result)
        self._sync_controls()

    def _sync_controls(self):
        enabled = (not self._busy and self.service is not None and not self.local_only()
                   and not self.settings_saving() and self.enabled())
        self.prepare_button.configure(state="normal" if enabled and not self._prepared_request else "disabled")
        self.submit_button.configure(state="normal" if enabled and self._prepared_request else "disabled")
        self.stop_button.configure(state="normal" if enabled and self._active_run_id else "disabled")
        self.discard_button.configure(state="normal" if enabled and self._selected_status == "prepared" else "disabled")
        final_status = self._selected_status in {"completed", "succeeded", "success", "finished", "done"}
        queueable = self._result_text and self._result_request_id == self._active_request and final_status
        from hermes_catalogue import is_catalogue_context
        library_result = is_catalogue_context(getattr(self, '_selected_context', ''))
        self.queue_button.configure(state="normal" if queueable else "disabled",
                                    text="Preview library choice" if library_result else "Queue result for Paste Ready")
        input_state = "disabled" if self._prepared_request else "normal"
        self.task.configure(state=input_state)
        self.context.configure(state=input_state)

    def test_connection(self):
        if self._blocked():
            return
        self._start(self.service.test_connection, self._show_connection)

    def _show_connection(self, result):
        notice = "Connection test: " + str(result.get("status", "unknown")) + ". " + str(
            result.get("message", "No status message."))
        capabilities = result.get("capabilities")
        features = capabilities.get("features") if isinstance(capabilities, dict) else None
        if isinstance(features, dict):
            advertised = sorted(str(key) for key, enabled in features.items() if enabled is True)
            if advertised:
                notice += " Supported capabilities: " + ", ".join(advertised[:12]) + "."
        self.set_notice(notice)

    def prepare(self):
        if self._blocked():
            return
        task = self.task.get("1.0", "end-1c").strip()
        context = self.context.get("1.0", "end-1c").strip()
        if not task or len(task) > 16000:
            self.set_notice("Enter a task of 1–16000 characters.")
            return
        if len(context) > 12000:
            self.set_notice("Selected context must be no longer than 12000 characters.")
            return
        if self._start(lambda: self.service.prepare(task, context), self._prepared):
            self._prepared_request = None
            self._prepared_task = task
            self._prepared_context = context
            self.set_notice("Saving the bounded task preview locally…")
            return True
        return False

    def load_library_task(self, task, context):
        """Stage a visibly selected catalogue; the existing Send action remains explicit."""
        if self._blocked():
            return False
        if self._busy or self._prepared_request:
            self.set_notice("Finish or discard the current prepared Hermes task before selecting a library catalogue.")
            return False
        for widget, value in ((self.task, task), (self.context, context)):
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.insert("1.0", value)
        return bool(self.prepare())

    def _prepared(self, result):
        self._prepared_request = result.get("request_id")
        self._active_request = self._prepared_request
        self._active_run_id = None
        self._selected_status = str(result.get("status", "prepared")).casefold()
        self._result_text = ""
        self._result_request_id = None
        self._selected_context = self._prepared_context
        self.status_line.configure(text="Prepared: " + str(result.get("status", "unknown")))
        self.set_notice("Preview saved locally. Send only when you are ready; Hermes has not received it yet.")
        preview = self._prepared_task.strip()
        if self._prepared_context.strip():
            preview += "\n\nSelected context:\n" + self._prepared_context.strip()
        self._append_details({"kind": "prepared", "preview": preview,
                              "message": result.get("message")})
        self.refresh_runs()

    def submit(self):
        if self._blocked() or not self._prepared_request:
            return
        request_id = self._prepared_request
        if self._start(lambda: self.service.submit(request_id), self._show_action_result, request_id):
            self._prepared_request = None
            self.set_notice("Sending the prepared request with its saved identity…")

    def refresh_runs(self):
        if self.service is None or self._closed or self._busy:
            return
        self._start(self.service.list_requests, self._show_runs)

    def _show_runs(self, requests):
        selection = self._active_request
        for child in self.runs.get_children():
            self.runs.delete(child)
        for index, item in enumerate(requests, start=1):
            request_id = str(item.get("request_id", ""))
            self.runs.insert("", "end", iid=request_id,
                             text=f"Request {index}", values=(item.get("status", "unknown"), item.get("created_utc", "")[:19]))
        if selection and self.runs.exists(selection):
            self._restoring_selection = True
            try:
                self.runs.selection_set(selection)
                self.runs.see(selection)
            finally:
                self._restoring_selection = False
        self._sync_controls()

    def _selected(self, _event=None):
        if self._restoring_selection:
            return
        selected = self.runs.selection()
        if selected:
            request_id = selected[0]
            if self._busy:
                operation_request = self._operation_request or self._active_request
                if operation_request and self.runs.exists(operation_request):
                    self._restoring_selection = True
                    try:
                        self.runs.selection_set(operation_request)
                    finally:
                        self._restoring_selection = False
                return
            if request_id == self._prepared_request:
                return
            self._active_request = request_id
            self._prepared_request = None
            self._active_run_id = None
            self._result_text = ""
            self._result_request_id = None
            self._selected_context = ''
            self._selected_status = "loading"
            self._sync_controls()
            self._start(lambda: self.service.preview(request_id), self._show_preview, request_id)

    def _show_preview(self, result):
        self._selected_status = str(result.get("status", "unknown")).casefold()
        self._active_run_id = result.get("run_id")
        can_retry = result.get("retry_allowed", self._selected_status == "prepared") is True
        if can_retry and self._selected_status in {"prepared", "uncertain", "http_error"} and not self._active_run_id:
            self._prepared_request = result.get("request_id")
            self.status_line.configure(text="Retry the same saved request" if self._selected_status != "prepared"
                                       else "Prepared for review")
        else:
            self.status_line.configure(text="Status: " + self._selected_status)
        preview = str(result.get("task", ""))
        context = str(result.get("context", ""))
        self._selected_context = context
        from hermes_catalogue import is_catalogue_context
        if is_catalogue_context(context) and isinstance(result.get('text'), str):
            self._result_text = result['text'][:20000]
            self._result_request_id = self._active_request
        if context:
            preview += "\n\nSelected context:\n" + context
        self._append_details({"kind": "saved_preview", "preview": preview,
                              "status": self._selected_status,
                              "message": result.get("message", "Saved request loaded.")})
        if self._selected_status in {"uncertain", "http_error"} and not can_retry:
            self.set_notice("The saved request has an ambiguous dispatch lock. Review its recorded status before any retry.")
        self._sync_controls()

    def refresh_active(self):
        if self._blocked() or not self._active_request:
            if not self._active_request:
                self.set_notice("Select a saved run first.")
            return
        request_id = self._active_request
        def action():
            status = self.service.poll(request_id)
            events = self.service.events(request_id) if status.get("run_id") else {"events": []}
            return {"status": status, "events": events}
        self._start(action, self._show_refresh, request_id)

    def _show_refresh(self, result):
        self._show_action_result(result["status"])
        events = result["events"].get("events", [])
        if events:
            self._append_details({"events": events[-100:]})
        self.refresh_runs()

    def stop_active(self):
        if self._blocked() or not self._active_request or not self._active_run_id:
            return
        request_id = self._active_request
        if self._start(lambda: self.service.stop(request_id), self._show_action_result, request_id):
            self.set_notice("Requesting cancellation for the selected run…")

    def discard_active(self):
        if self._blocked() or not self._active_request or self._selected_status != "prepared":
            return
        request_id = self._active_request
        self._start(lambda: self.service.discard(request_id), self._discarded, request_id)

    def _discarded(self, result):
        self._active_request = self._prepared_request = None
        self._active_run_id = None
        self._selected_status = ""
        self._result_text = ""
        self._result_request_id = None
        self._selected_context = ''
        self.task.configure(state="normal")
        self.context.configure(state="normal")
        self.status_line.configure(text="Unsent preview discarded locally.")
        self.set_notice(str(result.get("message", "The unsent preview was discarded.")))
        self.refresh_runs()

    def _show_action_result(self, result):
        self._selected_status = str(result.get("status", "unknown")).casefold()
        self._active_run_id = result.get("run_id") or self._active_run_id
        self.status_line.configure(text="Status: " + self._selected_status)
        self.set_notice(str(result.get("message", "Hermes status updated.")))
        text = result.get("text")
        if isinstance(text, str) and text.strip():
            self._result_text = text[:20000]
            self._result_request_id = self._active_request
            self._append_details({"result": self._result_text})
        self._append_details({"kind": "status", "status": self._selected_status,
                              "message": result.get("message", "")})
        if self._selected_status in {"uncertain", "http_error"} and not self._active_run_id and self._active_request:
            request_id = self._active_request
            self._start(lambda: self.service.preview(request_id), self._show_preview, request_id)
        if self._active_request:
            self._refresh_run_rows(result)

    def _refresh_run_rows(self, result):
        if not self.runs.exists(self._active_request):
            self.runs.insert("", 0, iid=self._active_request, text="Selected request",
                             values=(result.get("status", "unknown"), ""))
        else:
            self.runs.set(self._active_request, "status", result.get("status", "unknown"))

    def _append_details(self, value):
        kind = value.get("kind")
        if kind in {"prepared", "saved_preview"}:
            rendered = "Prepared task preview\n" + value.get("preview", "") + "\n\n" + value.get("message", "")
        elif kind == "status":
            rendered = "Progress: " + value.get("status", "unknown") + "\n" + value.get("message", "")
        elif "result" in value:
            rendered = "Hermes result\n" + str(value.get("result", ""))
        elif "events" in value:
            lines = ["Recent activity"]
            for event in value.get("events", [])[-100:]:
                if not isinstance(event, dict):
                    continue
                label = str(event.get("event", "update")).replace(".", " ").replace("_", " ").capitalize()[:100]
                data = event.get("data") if isinstance(event.get("data"), dict) else {}
                message = data.get("message") or data.get("text") or data.get("status") or ""
                lines.append(label + (": " + str(message)[:300] if message else ""))
            rendered = "\n".join(lines)
        else:
            rendered = str(value.get("message", "Hermes status updated."))
        self.details.configure(state="normal")
        self.details.insert("end", rendered[:20000] + "\n\n")
        self.details.see("end")
        self.details.configure(state="disabled")

    def queue_result(self):
        if (not self._result_text or not self._active_request or
                self._result_request_id != self._active_request or
                self._selected_status not in {"completed", "succeeded", "success", "finished", "done"}):
            self.set_notice("Select the saved request that produced this result before queueing it.")
            return
        from hermes_catalogue import is_catalogue_context
        if is_catalogue_context(getattr(self, '_selected_context', '')):
            callback = getattr(self, 'review_library', None)
            if callback:
                callback()
            else:
                self.set_notice('Preview this library choice from Image library before queueing an image.')
            return
        try:
            self.queue_text(self._result_text)
        except Exception:
            self.set_notice("Finish any current recording or writing task before queueing the result.")
        else:
            self.set_notice("Result queued for deliberate Paste Ready. It was not inserted into a document.")

    def close(self):
        self._closed = True
