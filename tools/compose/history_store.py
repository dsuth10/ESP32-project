"""Persistent, text-only history for the classroom companion."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


_SCHEMA_VERSION = 1
_MAX_TITLE_LENGTH = 200
_MAX_LIST_LIMIT = 500


def _default_database_path() -> Path:
    override = os.environ.get("ESP32_COMPANION_DATA_DIR")
    if override:
        data_dir = Path(override).expanduser()
    elif os.environ.get("LOCALAPPDATA"):
        data_dir = Path(os.environ["LOCALAPPDATA"]) / "ESP32ClassroomCompanion"
    elif os.name == "nt":
        data_dir = Path.home() / "AppData" / "Local" / "ESP32ClassroomCompanion"
    elif os.environ.get("XDG_DATA_HOME"):
        data_dir = Path(os.environ["XDG_DATA_HOME"]) / "ESP32ClassroomCompanion"
    else:
        data_dir = Path.home() / ".local" / "share" / "ESP32ClassroomCompanion"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "companion.sqlite3"


class HistoryStore:
    """Store conversation text in SQLite, opening a fresh connection per call."""

    def __init__(self, path: Path | str | None = None) -> None:
        # An explicit path names the database file, not its containing directory.
        self.path = Path(path).expanduser() if path is not None else _default_database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.create_function("casefold", 1, lambda value: value.casefold() if value is not None else "")
        try:
            yield connection
        finally:
            connection.close()

    def _initialise(self) -> None:
        with self._connect() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > _SCHEMA_VERSION:
                raise RuntimeError(
                    f"History database schema version {version} is newer than supported "
                    f"version {_SCHEMA_VERSION}"
                )
            if version == _SCHEMA_VERSION:
                return
            connection.execute("BEGIN IMMEDIATE")
            try:
                # Recheck after acquiring the write lock in case another instance initialised it.
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version > _SCHEMA_VERSION:
                    raise RuntimeError(
                        f"History database schema version {version} is newer than supported "
                        f"version {_SCHEMA_VERSION}"
                    )
                if version == 0:
                    connection.execute(
                        """CREATE TABLE IF NOT EXISTS history (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            mode TEXT NOT NULL,
                            request TEXT NOT NULL,
                            response TEXT NOT NULL,
                            provider TEXT NOT NULL DEFAULT '',
                            status TEXT NOT NULL DEFAULT 'completed',
                            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                            title TEXT,
                            saved INTEGER NOT NULL DEFAULT 0 CHECK (saved IN (0, 1))
                        )"""
                    )
                    connection.execute("CREATE INDEX IF NOT EXISTS history_created_at ON history(id DESC)")
                    connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

    @staticmethod
    def _entry(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        entry = dict(row)
        entry["saved"] = bool(entry["saved"])
        return entry

    def add_entry(
        self,
        mode: str,
        request: str,
        response: str,
        provider: str = "",
        status: str = "completed",
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO history (mode, request, response, provider, status) VALUES (?, ?, ?, ?, ?)",
                (mode, request, response, provider, status),
            )
            return int(cursor.lastrowid)

    def list_entries(
        self, query: str = "", saved_only: bool = False, limit: int = 100
    ) -> list[dict[str, Any]]:
        limit = min(_MAX_LIST_LIMIT, max(0, int(limit)))
        sql = "SELECT * FROM history"
        clauses: list[str] = []
        parameters: list[Any] = []
        if saved_only:
            clauses.append("saved = 1")
        if query:
            # instr treats %, _ and backslashes literally, unlike LIKE.
            clauses.append(
                "(instr(casefold(request), casefold(?)) > 0 "
                "OR instr(casefold(response), casefold(?)) > 0 "
                "OR instr(casefold(COALESCE(title, '')), casefold(?)) > 0)"
            )
            parameters.extend((query, query, query))
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id DESC LIMIT ?"
        parameters.append(limit)
        with self._connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [self._entry(row) for row in rows]  # type: ignore[misc]

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM history WHERE id = ?", (entry_id,)).fetchone()
        return self._entry(row)

    def set_saved(self, entry_id: int, saved: bool = True, title: str | None = None) -> bool:
        if title is not None:
            title = title[:_MAX_TITLE_LENGTH]
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE history SET saved = ?, title = COALESCE(?, title) WHERE id = ?",
                (int(bool(saved)), title, entry_id),
            )
            return cursor.rowcount > 0

    def delete_entry(self, entry_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM history WHERE id = ?", (entry_id,))
            return cursor.rowcount > 0
