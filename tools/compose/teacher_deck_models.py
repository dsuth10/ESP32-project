"""Teacher Deck data models, multi-image staging tray and validation helpers.

Australian English spelling conventions and standard library only.
Provides thread-safe staging of candidate image series and validation
for the Raspberry Pi Teacher Touchscreen companion API.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
from typing import Any
import uuid

HASH_RE = re.compile(r"^[0-9a-fA-F]{64}$")
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

VALID_CONTROL_ACTIONS = frozenset(
    {"freeze", "resume", "prev_page", "next_page", "new_page", "undo", "redo"}
)
VALID_PRESENT_TARGETS = frozenset({"current_page", "new_page"})
VALID_DISPLAY_TARGETS = frozenset({"board", "onenote", "word", "chrome"})
VALID_ORIGINS = frozenset({"generated", "library", "web", "import"})
VALID_REVIEW_STATES = frozenset({"draft", "approved"})

MAX_STAGED_ITEMS = 64
MAX_TITLE_LENGTH = 200
MAX_CREDIT_LENGTH = 2048


def _now() -> str:
    """Return the current UTC timestamp formatted as ISO-8601."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def validate_uuid(value: Any, label: str = "UUID") -> str:
    """Validate that the supplied value is a canonical UUID string."""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a UUID string.")
    cleaned = value.strip()
    if not UUID_RE.fullmatch(cleaned):
        raise ValueError(f"{label} must be a valid UUID string.")
    try:
        return str(uuid.UUID(cleaned))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"{label} must be a valid UUID string.") from exc


def validate_sha256(value: Any, label: str = "SHA-256") -> str:
    """Validate that the supplied value is a 64-character hexadecimal digest."""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a 64-character hexadecimal string.")
    cleaned = value.strip().lower()
    if not HASH_RE.fullmatch(cleaned):
        raise ValueError(f"{label} must be a valid 64-character hexadecimal SHA-256 digest.")
    return cleaned


def validate_control_action(action: Any) -> str:
    """Validate a board navigation or session control action."""
    if not isinstance(action, str):
        raise ValueError("Control action must be a string.")
    cleaned = action.strip().lower()
    if cleaned not in VALID_CONTROL_ACTIONS:
        allowed = ", ".join(sorted(VALID_CONTROL_ACTIONS))
        raise ValueError(f"Invalid control action '{action}'. Allowed actions: {allowed}")
    return cleaned


def validate_present_target(target: Any) -> str:
    """Validate a present-image placement target."""
    if not isinstance(target, str):
        raise ValueError("Present target must be a string.")
    cleaned = target.strip().lower()
    if cleaned not in VALID_PRESENT_TARGETS:
        allowed = ", ".join(sorted(VALID_PRESENT_TARGETS))
        raise ValueError(f"Invalid present target '{target}'. Allowed targets: {allowed}")
    return cleaned


def validate_display_target(target: Any) -> str:
    """Validate a student display switch target."""
    if not isinstance(target, str):
        raise ValueError("Display target must be a string.")
    cleaned = target.strip().lower()
    if cleaned not in VALID_DISPLAY_TARGETS:
        allowed = ", ".join(sorted(VALID_DISPLAY_TARGETS))
        raise ValueError(f"Invalid display target '{target}'. Allowed targets: {allowed}")
    return cleaned


@dataclass(frozen=True)
class StagedImageItem:
    """Immutable record for a candidate image staged on the Teacher Deck."""

    stage_id: str
    series_id: str
    asset_id: str
    version_id: str
    sha256: str
    title: str
    width: int
    height: int
    origin: str
    review_state: str
    credit: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "stage_id", validate_uuid(self.stage_id, "stage_id"))
        if not isinstance(self.series_id, str) or not self.series_id.strip():
            raise ValueError("series_id must be a non-empty string.")
        object.__setattr__(self, "series_id", self.series_id.strip())

        object.__setattr__(self, "asset_id", validate_uuid(self.asset_id, "asset_id"))
        object.__setattr__(self, "version_id", validate_uuid(self.version_id, "version_id"))
        object.__setattr__(self, "sha256", validate_sha256(self.sha256, "sha256"))

        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title must be a non-empty string.")
        cleaned_title = self.title.strip()
        if len(cleaned_title) > MAX_TITLE_LENGTH:
            raise ValueError(f"title exceeds maximum length of {MAX_TITLE_LENGTH} characters.")
        object.__setattr__(self, "title", cleaned_title)

        if isinstance(self.width, bool) or not isinstance(self.width, int) or self.width <= 0:
            raise ValueError("width must be a positive integer.")
        if isinstance(self.height, bool) or not isinstance(self.height, int) or self.height <= 0:
            raise ValueError("height must be a positive integer.")

        if not isinstance(self.origin, str) or self.origin.strip().lower() not in VALID_ORIGINS:
            allowed = ", ".join(sorted(VALID_ORIGINS))
            raise ValueError(f"origin must be one of: {allowed}")
        object.__setattr__(self, "origin", self.origin.strip().lower())

        if (
            not isinstance(self.review_state, str)
            or self.review_state.strip().lower() not in VALID_REVIEW_STATES
        ):
            allowed = ", ".join(sorted(VALID_REVIEW_STATES))
            raise ValueError(f"review_state must be one of: {allowed}")
        object.__setattr__(self, "review_state", self.review_state.strip().lower())

        credit_str = str(self.credit or "").strip()
        if len(credit_str) > MAX_CREDIT_LENGTH:
            raise ValueError(f"credit exceeds maximum length of {MAX_CREDIT_LENGTH} characters.")
        object.__setattr__(self, "credit", credit_str)

        created = str(self.created_at or "").strip() or _now()
        object.__setattr__(self, "created_at", created)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dictionary including thumbnail endpoint."""
        return {
            "stage_id": self.stage_id,
            "series_id": self.series_id,
            "asset_id": self.asset_id,
            "version_id": self.version_id,
            "sha256": self.sha256,
            "title": self.title,
            "width": self.width,
            "height": self.height,
            "origin": self.origin,
            "review_state": self.review_state,
            "credit": self.credit,
            "created_at": self.created_at,
            "thumb_url": f"/api/v1/thumb/{self.version_id}",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StagedImageItem:
        """Construct a StagedImageItem from a dictionary."""
        if not isinstance(data, dict):
            raise ValueError("data must be a dictionary.")
        stage_id = data.get("stage_id") or str(uuid.uuid4())
        series_id = data.get("series_id") or str(uuid.uuid4())
        asset_id = data.get("asset_id") or str(uuid.uuid4())
        version_id = data.get("version_id")
        if not version_id:
            raise ValueError("version_id is required.")
        return cls(
            stage_id=str(stage_id),
            series_id=str(series_id),
            asset_id=str(asset_id),
            version_id=str(version_id),
            sha256=str(data.get("sha256", "")),
            title=str(data.get("title", "Untitled")),
            width=int(data.get("width", 800)),
            height=int(data.get("height", 600)),
            origin=str(data.get("origin", "library")),
            review_state=str(data.get("review_state", "draft")),
            credit=str(data.get("credit", "")),
            created_at=str(data.get("created_at", "")),
        )


class StagingTray:
    """Thread-safe staging queue for multi-image series and candidate assets."""

    def __init__(
        self,
        max_items: int = MAX_STAGED_ITEMS,
        storage_path: Path | str | None = None,
    ) -> None:
        self.max_items = max(1, int(max_items))
        self.storage_path = Path(storage_path) if storage_path is not None else None
        self._lock = threading.RLock()
        self._items: list[StagedImageItem] = []
        if self.storage_path is not None and self.storage_path.is_file():
            self._load()

    def _load(self) -> None:
        if self.storage_path is None or not self.storage_path.is_file():
            return
        try:
            raw = self.storage_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, list):
                loaded: list[StagedImageItem] = []
                for entry in data:
                    try:
                        loaded.append(StagedImageItem.from_dict(entry))
                    except Exception:
                        continue
                self._items = loaded[: self.max_items]
        except Exception:
            pass

    def _persist(self) -> None:
        if self.storage_path is None:
            return
        temp_path: Path | None = None
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            serialised = [item.as_dict() for item in self._items]
            encoded = json.dumps(serialised, indent=2, ensure_ascii=False)
            temp_path = self.storage_path.with_name(
                f".{self.storage_path.name}.{uuid.uuid4().hex}.tmp"
            )
            temp_path.write_text(encoded, encoding="utf-8")
            temp_path.replace(self.storage_path)
        except Exception:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    def stage_item(self, item: StagedImageItem) -> StagedImageItem:
        """Stage an item, deduplicating or updating by version_id while maintaining bounds."""
        if not isinstance(item, StagedImageItem):
            raise ValueError("item must be a StagedImageItem instance.")
        with self._lock:
            # Check for existing version_id
            existing_index = next(
                (idx for idx, existing in enumerate(self._items) if existing.version_id == item.version_id),
                None,
            )
            if existing_index is not None:
                # Update existing item in place
                self._items[existing_index] = item
            else:
                # Prepend newest candidate to the front
                self._items.insert(0, item)
                if len(self._items) > self.max_items:
                    self._items = self._items[: self.max_items]
            self._persist()
            return item

    def stage_series(
        self,
        items: list[StagedImageItem],
        series_id: str | None = None,
    ) -> list[StagedImageItem]:
        """Stage a batch of candidate images under a shared series_id."""
        if not isinstance(items, list):
            raise ValueError("items must be a list of StagedImageItem instances.")
        effective_series_id = series_id.strip() if (series_id and series_id.strip()) else str(uuid.uuid4())
        staged: list[StagedImageItem] = []
        with self._lock:
            for raw_item in items:
                if not isinstance(raw_item, StagedImageItem):
                    raise ValueError("Each item must be a StagedImageItem instance.")
                item_to_stage = (
                    replace(raw_item, series_id=effective_series_id)
                    if raw_item.series_id != effective_series_id
                    else raw_item
                )
                staged.append(self.stage_item(item_to_stage))
        return staged

    def list_items(self, series_id: str | None = None) -> list[dict[str, Any]]:
        """Return serialised dictionary records, optionally filtered by series_id."""
        with self._lock:
            if series_id is not None:
                cleaned = series_id.strip()
                return [item.as_dict() for item in self._items if item.series_id == cleaned]
            return [item.as_dict() for item in self._items]

    def get_version(self, version_id: str) -> StagedImageItem | None:
        """Retrieve a staged item by its version_id."""
        if not isinstance(version_id, str):
            return None
        cleaned = version_id.strip().lower()
        with self._lock:
            for item in self._items:
                if item.version_id.lower() == cleaned:
                    return item
            return None

    def remove_version(self, version_id: str) -> bool:
        """Remove a staged item by its version_id; return True if found and removed."""
        if not isinstance(version_id, str):
            return False
        cleaned = version_id.strip().lower()
        with self._lock:
            for idx, item in enumerate(self._items):
                if item.version_id.lower() == cleaned:
                    self._items.pop(idx)
                    self._persist()
                    return True
            return False

    def clear(self) -> None:
        """Clear all staged items."""
        with self._lock:
            self._items.clear()
            self._persist()
