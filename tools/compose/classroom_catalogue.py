"""Curated MrSutherland.net classroom lesson catalogue and allowlisted URL validator.

Provides a standard-library-only loader and strict HTTPS host allowlist for
launching interactive web lessons onto the classroom display via JoshuaOS Podium.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


ALLOWED_WEB_HOSTS = frozenset({"mrsutherland.net", "www.mrsutherland.net"})
MAX_WEB_URL_LENGTH = 512
_FORBIDDEN_URL_CHARS = frozenset({
    '"', "'", "`", ";", "|", "&", "$", "<", ">", "\\", "\0", "\r", "\n", "\t",
})

DEFAULT_REPO_CATALOGUE_PATH = Path(__file__).resolve().parent / "classroom_catalogue.json"
DEFAULT_LOCAL_OVERRIDE_PATH = Path(__file__).resolve().parents[2] / ".local" / "classroom_catalogue.json"


def is_allowlisted_web_url(url: str) -> bool:
    """Return True if *url* is a safe, allowlisted HTTPS MrSutherland.net URL."""
    if not isinstance(url, str):
        return False
    if not url or len(url) > MAX_WEB_URL_LENGTH:
        return False
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 or ch in _FORBIDDEN_URL_CHARS for ch in url):
        return False
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    if port not in (None, 443):
        return False
    hostname = (parsed.hostname or "").lower()
    if hostname not in ALLOWED_WEB_HOSTS:
        return False
    if "@" in (parsed.netloc or ""):
        return False
    if parsed.path and not parsed.path.startswith("/"):
        return False
    return True


@dataclass(frozen=True)
class CatalogueItem:
    id: str
    title: str
    category: str
    url: str
    description: str = ""
    display_target: str = "chrome"
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        item_id = (self.id or "").strip() if isinstance(self.id, str) else ""
        title = (self.title or "").strip() if isinstance(self.title, str) else ""
        category = (self.category or "").strip() if isinstance(self.category, str) else ""
        url = (self.url or "").strip() if isinstance(self.url, str) else ""
        description = (self.description or "").strip() if isinstance(self.description, str) else ""
        display_target = (self.display_target or "chrome").strip() if isinstance(self.display_target, str) else "chrome"

        if not item_id:
            raise ValueError("CatalogueItem id must be a non-empty string.")
        if not title:
            raise ValueError("CatalogueItem title must be a non-empty string.")
        if not category:
            raise ValueError("CatalogueItem category must be a non-empty string.")
        if not is_allowlisted_web_url(url):
            raise ValueError(f"CatalogueItem url is not allowlisted: {self.url!r}")

        raw_tags = self.tags or ()
        if isinstance(raw_tags, (list, tuple)):
            normalised_tags = tuple(
                str(tag).strip() for tag in raw_tags if isinstance(tag, (str, int, float)) and str(tag).strip()
            )
        else:
            normalised_tags = ()

        object.__setattr__(self, "id", item_id)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "url", url)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "display_target", display_target or "chrome")
        object.__setattr__(self, "tags", normalised_tags)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "CatalogueItem":
        if not isinstance(data, dict):
            raise ValueError("Catalogue entry must be a JSON object.")
        raw_tags = data.get("tags", ())
        tags: tuple[str, ...]
        if isinstance(raw_tags, (list, tuple)):
            tags = tuple(str(t).strip() for t in raw_tags if str(t).strip())
        else:
            tags = ()
        return cls(
            id=str(data.get("id") or "").strip(),
            title=str(data.get("title") or "").strip(),
            category=str(data.get("category") or "").strip(),
            url=str(data.get("url") or "").strip(),
            description=str(data.get("description") or "").strip(),
            display_target=str(data.get("display_target") or "chrome").strip() or "chrome",
            tags=tags,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "url": self.url,
            "description": self.description,
            "display_target": self.display_target,
            "tags": list(self.tags),
        }


def _read_catalogue_entries(path: Path) -> list[CatalogueItem]:
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        logging.warning("Classroom catalogue file %s could not be read: %s", path, exc)
        return []

    if isinstance(raw, dict):
        entries = raw.get("items", [])
    elif isinstance(raw, list):
        entries = raw
    else:
        return []

    if not isinstance(entries, list):
        return []

    valid: list[CatalogueItem] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            valid.append(CatalogueItem.from_mapping(entry))
        except ValueError as exc:
            logging.warning("Ignoring invalid classroom catalogue item in %s: %s", path, exc)
    return valid


def load_classroom_catalogue(
    repo_path: Path | None = None,
    local_override_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Load the tracked classroom catalogue and merge optional `.local` overrides by `id`."""
    base_file = Path(repo_path) if repo_path is not None else DEFAULT_REPO_CATALOGUE_PATH
    override_file = (
        Path(local_override_path)
        if local_override_path is not None
        else DEFAULT_LOCAL_OVERRIDE_PATH
    )

    merged_by_id: dict[str, CatalogueItem] = {}
    ordered_ids: list[str] = []

    for item in _read_catalogue_entries(base_file):
        if item.id not in merged_by_id:
            ordered_ids.append(item.id)
        merged_by_id[item.id] = item

    for item in _read_catalogue_entries(override_file):
        if item.id not in merged_by_id:
            ordered_ids.append(item.id)
        merged_by_id[item.id] = item

    return [merged_by_id[item_id].as_dict() for item_id in ordered_ids]


def get_catalogue_item(
    item_id: str,
    repo_path: Path | None = None,
    local_override_path: Path | None = None,
) -> dict[str, Any] | None:
    """Return a single allowlisted catalogue item by *item_id*, or None if not found."""
    wanted = (item_id or "").strip()
    if not wanted:
        return None
    for item in load_classroom_catalogue(repo_path=repo_path, local_override_path=local_override_path):
        if item.get("id") == wanted:
            return item
    return None
