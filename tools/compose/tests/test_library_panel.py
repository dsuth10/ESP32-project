import sys
import tkinter as tk
from pathlib import Path
from tkinter import TclError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import library_panel as library_panel_module
from history_store import HistoryStore
from library_panel import LibraryPanel


@pytest.fixture(scope="module")
def tk_root():
    try:
        root = tk.Tk()
    except TclError as error:
        pytest.skip(f"Tk display is unavailable: {error}")
    root.geometry("720x580")
    yield root
    root.destroy()


@pytest.fixture
def ui(tk_root, tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite3")
    queued = []
    notices = []
    panel = LibraryPanel(tk_root, store, queued.append, on_notice=notices.append)
    panel.pack(fill="both", expand=True)
    tk_root.update_idletasks()
    yield tk_root, store, panel, queued
    panel.destroy()
    tk_root.update_idletasks()


def select(panel, entry_id):
    panel.tree.selection_set(str(entry_id))
    panel.tree.focus(str(entry_id))
    panel.tree.event_generate("<<TreeviewSelect>>")
    panel.update_idletasks()


def test_search_saved_filter_and_selection_details(ui):
    _root, store, panel, _queued = ui
    kept = store.add_entry("compose", "Planning prompt", "Useful plan", "local model", "completed")
    store.set_saved(kept, title="Term planning")
    store.add_entry("dictate", "Unrelated words", "Transcript", "speech model", "failed")

    panel.refresh()
    assert set(panel.tree.get_children()) == {str(kept), str(kept + 1)}
    assert panel.tree.heading("title")["text"] == "Title"
    assert panel.search_entry.winfo_exists()
    assert panel.tree.set(str(kept + 1), "title") == "Unrelated words"

    panel.search_var.set("Term planning")
    panel.saved_only_var.set(True)
    panel.refresh()
    assert panel.tree.get_children() == (str(kept),)
    select(panel, kept)
    details = panel.detail_text.get("1.0", "end")
    assert "Planning prompt" in details
    assert "Useful plan" in details
    assert "Provider: local model" in details
    assert "Status: completed" in details
    assert panel.detail_text.cget("state") == "disabled"


def test_copy_and_queue_response_do_not_inject_text(ui):
    root, store, panel, queued = ui
    entry_id = store.add_entry("compose", "prompt", "A response\nwith two lines")
    panel.refresh()
    select(panel, entry_id)

    panel.copy_response()
    root.update()
    assert root.clipboard_get() == "A response\nwith two lines"
    panel.queue_response()
    assert queued == ["A response\nwith two lines"]


def test_save_and_unsave_selected_entry(ui, monkeypatch):
    _root, store, panel, _queued = ui
    entry_id = store.add_entry("compose", "prompt", "response")
    panel.refresh()
    select(panel, entry_id)
    monkeypatch.setattr(library_panel_module.simpledialog, "askstring", lambda *args, **kwargs: "Revision")

    panel.toggle_saved()
    assert store.get_entry(entry_id)["saved"] is True
    assert store.get_entry(entry_id)["title"] == "Revision"
    assert panel.save_button.cget("text") == "Unsave"
    panel.toggle_saved()
    assert store.get_entry(entry_id)["saved"] is False
    assert panel.save_button.cget("text") == "Save"


def test_confirmed_delete_and_utf8_export(ui, tmp_path, monkeypatch):
    _root, store, panel, _queued = ui
    entry_id = store.add_entry("compose", "Kia ora", "Café 🌿")
    panel.refresh()
    select(panel, entry_id)
    monkeypatch.setattr(library_panel_module.messagebox, "askyesno", lambda *args, **kwargs: True)
    panel.delete_selected()
    assert store.get_entry(entry_id) is None
    assert panel.tree.get_children() == ()
    assert str(panel.copy_button.cget("state")) == "disabled"

    export_id = store.add_entry("compose", "Kia ora", "Café 🌿")
    export_path = tmp_path / "entry.txt"
    monkeypatch.setattr(library_panel_module.filedialog, "asksaveasfilename", lambda **kwargs: str(export_path))
    panel.refresh()
    select(panel, export_id)
    panel.export_selected()
    assert export_path.read_text(encoding="utf-8") == "Request\nKia ora\n\nResponse\nCafé 🌿\n"
