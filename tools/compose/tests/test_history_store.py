from concurrent.futures import ThreadPoolExecutor
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import history_store as history_store_module
from history_store import HistoryStore


def test_persistence_unicode_multiline_and_entry_shape(tmp_path):
    database = tmp_path / "nested" / "history.sqlite3"
    store = HistoryStore(database)
    request = "Kia ora — 你好\nsecond line"
    response = "Café 🌿\n\nthird line"
    entry_id = store.add_entry("dictation", request, response, "local", "completed")

    reopened = HistoryStore(database)
    entry = reopened.get_entry(entry_id)
    assert entry == reopened.list_entries()[0]
    assert entry["request"] == request
    assert entry["response"] == response
    assert entry["saved"] is False
    assert set(entry) == {
        "id", "mode", "request", "response", "provider", "status", "created_at", "title", "saved"
    }


def test_concurrent_adds_are_persisted(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite3")

    def add(number):
        return store.add_entry("compose", f"request {number}", f"response {number}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(add, range(40)))

    assert len(set(ids)) == 40
    entries = store.list_entries(limit=100)
    assert len(entries) == 40
    assert {entry["id"] for entry in entries} == set(ids)
    assert [entry["id"] for entry in entries] == sorted(ids, reverse=True)


def test_save_unpin_and_delete(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite3")
    entry_id = store.add_entry("compose", "request", "response")
    assert store.set_saved(entry_id, title="Planning notes") is True
    assert store.get_entry(entry_id)["saved"] is True
    assert store.get_entry(entry_id)["title"] == "Planning notes"
    assert [entry["id"] for entry in store.list_entries(saved_only=True)] == [entry_id]

    assert store.set_saved(entry_id, False) is True
    assert store.get_entry(entry_id)["saved"] is False
    assert store.get_entry(entry_id)["title"] == "Planning notes"
    assert store.list_entries(saved_only=True) == []
    assert store.delete_entry(entry_id) is True
    assert store.get_entry(entry_id) is None
    assert store.delete_entry(entry_id) is False
    assert store.set_saved(entry_id) is False


def test_title_is_bounded(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite3")
    entry_id = store.add_entry("compose", "request", "response")
    title = "界" * 300
    store.set_saved(entry_id, title=title)
    assert store.get_entry(entry_id)["title"] == title[:200]


def test_query_treats_sql_wildcards_as_literal_text(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite3")
    literal_id = store.add_entry("compose", "find 100%_ready\\now", "literal")
    store.add_entry("compose", "find 100xxready/now", "decoy")

    results = store.list_entries(query="100%_ready\\now")
    assert [entry["id"] for entry in results] == [literal_id]


def test_query_is_unicode_case_insensitive_and_list_limit_is_capped(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite3")
    entry_id = store.add_entry("compose", "Straße and ÉCOLE", "response")
    assert [entry["id"] for entry in store.list_entries(query="STRASSE AND école")] == [entry_id]
    for number in range(510):
        store.add_entry("compose", str(number), "response")
    assert len(store.list_entries(limit=10000)) == 500


def test_connection_closes_when_operation_raises(tmp_path, monkeypatch):
    store = HistoryStore(tmp_path / "history.sqlite3")
    real_connect = sqlite3.connect
    made = []

    class TrackingConnection(sqlite3.Connection):
        closed = False

        def close(self):
            self.closed = True
            super().close()

    def tracking_connect(*args, **kwargs):
        kwargs["factory"] = TrackingConnection
        connection = real_connect(*args, **kwargs)
        made.append(connection)
        return connection

    monkeypatch.setattr(history_store_module.sqlite3, "connect", tracking_connect)
    with pytest.raises(RuntimeError, match="operation failed"):
        with store._connect():
            raise RuntimeError("operation failed")
    assert made[0].closed is True


def test_newer_schema_is_rejected_without_reset(tmp_path):
    database = tmp_path / "future.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE keep_me (value TEXT)")
        connection.execute("INSERT INTO keep_me VALUES ('preserve')")
        connection.execute("PRAGMA user_version = 999")

    with pytest.raises(RuntimeError, match="newer than supported"):
        HistoryStore(database)

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM keep_me").fetchone() == ("preserve",)
        assert connection.execute("PRAGMA user_version").fetchone() == (999,)
