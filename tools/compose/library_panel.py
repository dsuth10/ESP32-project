"""Local history and saved-text browser for the compose companion."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, scrolledtext, ttk
from datetime import datetime
from typing import Any, Callable

from board_theme_tokens import style_tk_text


class LibraryPanel(ttk.Frame):
    """Browse local history and queue saved responses for the paste-ready flow."""

    def __init__(
        self,
        parent: tk.Misc,
        store: Any,
        on_queue: Callable[[str], Any],
        on_notice: Callable[[str], Any] | None = None,
    ) -> None:
        super().__init__(parent, padding=8)
        self.store = store
        self.on_queue = on_queue
        self.on_notice = on_notice
        self._selected_id: int | None = None
        self._entries: dict[int, dict[str, Any]] = {}

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        search_row = ttk.Frame(self)
        search_row.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        search_row.columnconfigure(1, weight=1)
        self.search_var = tk.StringVar()
        ttk.Label(search_row, text="Search").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.search_entry = ttk.Entry(search_row, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6))
        self.search_entry.bind("<Return>", lambda _event: self.refresh())
        self.saved_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            search_row, text="Saved only", variable=self.saved_only_var,
            command=self.refresh,
        ).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(search_row, text="Refresh", command=self.refresh).grid(row=0, column=3)

        body = ttk.Panedwindow(self, orient=tk.VERTICAL)
        body.grid(row=1, column=0, sticky="nsew")
        listing = ttk.Frame(body)
        listing.columnconfigure(0, weight=1)
        listing.rowconfigure(0, weight=1)
        details = ttk.Frame(body)
        details.columnconfigure(0, weight=1)
        details.rowconfigure(1, weight=1)
        body.add(listing, weight=3)
        body.add(details, weight=2)

        columns = ("date", "mode", "title", "saved")
        self.tree = ttk.Treeview(listing, columns=columns, show="headings", selectmode="browse")
        for key, heading, width in (
            ("date", "Date", 142), ("mode", "Mode", 78),
            ("title", "Title", 180), ("saved", "Saved", 58),
        ):
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width, minwidth=48, stretch=(key == "title"), anchor="w")
        yscroll = ttk.Scrollbar(listing, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(listing, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)

        ttk.Label(details, text="Request and response").grid(row=0, column=0, sticky="w", pady=(4, 3))
        self.detail_text = scrolledtext.ScrolledText(details, height=7, wrap="word", state="disabled")
        style_tk_text(self.detail_text)
        self.detail_text.grid(row=1, column=0, sticky="nsew")

        action_row = ttk.Frame(self)
        action_row.grid(row=2, column=0, sticky="ew", pady=(7, 2))
        self.copy_button = ttk.Button(action_row, text="Copy response", command=self.copy_response)
        self.queue_button = ttk.Button(action_row, text="Queue for Paste Ready", command=self.queue_response)
        self.save_button = ttk.Button(action_row, text="Save", command=self.toggle_saved)
        self.delete_button = ttk.Button(action_row, text="Delete selected", command=self.delete_selected)
        self.export_button = ttk.Button(action_row, text="Export selected", command=self.export_selected)
        for index, button in enumerate((self.copy_button, self.queue_button, self.save_button)):
            button.grid(row=0, column=index, padx=(0 if index == 0 else 5, 0), sticky="ew")
            action_row.columnconfigure(index, weight=1)
        for index, button in enumerate((self.delete_button, self.export_button)):
            button.grid(row=1, column=index, padx=(0 if index == 0 else 5, 0), pady=(5, 0), sticky="ew")
            action_row.columnconfigure(index, weight=1)
        action_row.columnconfigure(2, weight=1)

        ttk.Label(
            self, text="History is stored on this computer. Delete entries when no longer needed.",
            wraplength=570,
        ).grid(row=3, column=0, sticky="w", pady=(5, 0))
        self.notice = ttk.Label(self, text="", wraplength=650)
        self.notice.grid(row=4, column=0, sticky="ew")
        self._set_actions(False)
        self.refresh()

    def _notify(self, message: str, *, error: bool = False) -> None:
        self.notice.configure(text=message)
        if self.on_notice is not None:
            try:
                self.on_notice(message)
            except Exception:
                pass
        elif error:
            messagebox.showerror("History", message, parent=self)
        else:
            messagebox.showinfo("History", message, parent=self)

    def _set_actions(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in (self.copy_button, self.queue_button, self.save_button,
                       self.delete_button, self.export_button):
            button.configure(state=state)

    def _set_details(self, value: str) -> None:
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", value)
        self.detail_text.configure(state="disabled")

    def _selection_changed(self, _event: tk.Event | None = None) -> None:
        selection = self.tree.selection()
        if not selection:
            self._clear_selection()
            return
        try:
            entry_id = int(selection[0])
            entry = self.store.get_entry(entry_id)
        except Exception:
            self._clear_selection()
            self._notify("Could not load the selected history entry.", error=True)
            return
        if not entry:
            self._clear_selection()
            return
        self._selected_id = entry_id
        self._entries[entry_id] = entry
        request = entry.get("request") or ""
        response = entry.get("response") or ""
        provider = entry.get("provider") or "Unknown provider"
        status = entry.get("status") or "Unknown status"
        self._set_details(
            f"Provider: {provider}  |  Status: {status}\n\n"
            f"Request\n{request}\n\nResponse\n{response}"
        )
        self.save_button.configure(text="Unsave" if entry.get("saved") else "Save")
        self._set_actions(True)

    def _clear_selection(self) -> None:
        self._selected_id = None
        self._set_details("")
        self.save_button.configure(text="Save")
        self._set_actions(False)

    def refresh(self) -> None:
        previous_id = self._selected_id
        try:
            entries = self.store.list_entries(
                query=self.search_var.get(), saved_only=self.saved_only_var.get(), limit=100
            )
        except Exception:
            self._notify("Could not refresh local history.", error=True)
            return

        for item in self.tree.get_children(""):
            self.tree.delete(item)
        self._entries.clear()
        selected_still_present = False
        for entry in entries:
            entry_id = int(entry["id"])
            self._entries[entry_id] = entry
            created = str(entry.get("created_at") or "")
            try:
                parsed = datetime.fromisoformat(created.replace("Z", "+00:00"))
                created = parsed.astimezone().strftime("%d/%m/%Y %H:%M")
            except (ValueError, OverflowError):
                created = created.replace("T", " ").replace("Z", "")
            title = entry.get("title") or ""
            if not title:
                excerpt = (entry.get("request") or entry.get("response") or "").strip()
                title = " ".join(excerpt.split())[:56]
                if len(" ".join(excerpt.split())) > 56:
                    title += "…"
            self.tree.insert("", "end", iid=str(entry_id), values=(
                created, entry.get("mode", ""), title, "Yes" if entry.get("saved") else "",
            ))
            selected_still_present |= entry_id == previous_id
        if selected_still_present:
            self.tree.selection_set(str(previous_id))
            self.tree.focus(str(previous_id))
            self._selection_changed()
        else:
            self.tree.selection_remove(self.tree.selection())
            self._clear_selection()

    def _selected_entry(self) -> dict[str, Any] | None:
        if self._selected_id is None:
            return None
        return self._entries.get(self._selected_id)

    def copy_response(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(entry.get("response") or "")
            self._notify("Response copied to the clipboard.")
        except Exception:
            self._notify("Could not copy the response to the clipboard.", error=True)

    def queue_response(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        try:
            self.on_queue(entry.get("response") or "")
            self._notify("Response queued. Focus your document and use the Paste Ready shortcut.")
        except Exception:
            self._notify("Could not queue the response for Paste Ready.", error=True)

    def toggle_saved(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        saved = bool(entry.get("saved"))
        title: str | None = None
        if not saved:
            title = simpledialog.askstring(
                "Save response", "Title (optional):", initialvalue=entry.get("title") or "",
                parent=self,
            )
            if title is None:
                return
            title = title.strip() or None
        try:
            if not self.store.set_saved(self._selected_id, saved=not saved, title=title):
                self._notify("That history entry is no longer available.", error=True)
                self.refresh()
                return
        except Exception:
            self._notify("Could not update the saved status.", error=True)
            return
        self.refresh()

    def delete_selected(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        if not messagebox.askyesno(
            "Delete history entry", "Delete this history entry permanently?", parent=self
        ):
            return
        try:
            if not self.store.delete_entry(self._selected_id):
                self._notify("That history entry is no longer available.", error=True)
            self.refresh()
        except Exception:
            self._notify("Could not delete the history entry.", error=True)

    def export_selected(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self, title="Export history entry", defaultextension=".txt",
            filetypes=(("Text files", "*.txt"), ("All files", "*")),
        )
        if not path:
            return
        content = f"Request\n{entry.get('request') or ''}\n\nResponse\n{entry.get('response') or ''}\n"
        try:
            with open(path, "w", encoding="utf-8", newline="") as output:
                output.write(content)
            self._notify("History entry exported.")
        except Exception:
            self._notify("Could not export the history entry.", error=True)
