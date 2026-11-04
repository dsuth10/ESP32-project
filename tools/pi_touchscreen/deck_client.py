"""HTTP client and configuration loader for the Teacher Deck companion API.

Australian English spelling conventions and Python standard library only.
Provides authenticated access to lesson status, image candidate staging,
page navigation, and classroom display switching with zero external dependencies.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


class DeckClientError(Exception):
    """Structured error raised by TeacherDeckClient on network or API failures."""

    def __init__(self, status: int, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(f"[{status}] {message}" if status else message)
        self.status = status
        self.message = message
        self.details = details or {}


class TeacherDeckClient:
    """Authenticated HTTP client for the Windows-hosted Teacher Deck service."""

    def __init__(self, base_url: str, token: str, timeout: float = 3.0) -> None:
        cleaned_url = str(base_url or "").strip().rstrip("/")
        if not cleaned_url:
            raise ValueError("base_url must be a non-empty string.")
        self.base_url = cleaned_url
        self.token = str(token or "").strip()
        self.timeout = max(0.1, float(timeout))
        self._thumb_cache: dict[str, bytes] = {}

    def _request(
        self,
        method: str,
        path: str,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        is_binary: bool = False,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            clean_query = {k: v for k, v in query.items() if v is not None}
            if clean_query:
                qs = urllib.parse.urlencode(clean_query)
                url = f"{url}?{qs}"

        data: bytes | None = None
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self.token}",
        }
        if is_binary:
            headers["Accept"] = "image/png, image/*, */*"
        else:
            headers["Accept"] = "application/json"

        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw_bytes = resp.read()
                if is_binary:
                    return raw_bytes
                text = raw_bytes.decode("utf-8")
                return json.loads(text) if text else {}
        except urllib.error.HTTPError as exc:
            raw_err = exc.read().decode("utf-8", errors="replace")
            msg = exc.reason
            details: dict[str, Any] = {}
            try:
                err_json = json.loads(raw_err)
                if isinstance(err_json, dict):
                    details = err_json
                    msg = err_json.get("error", exc.reason)
            except Exception:
                pass
            raise DeckClientError(status=exc.code, message=str(msg), details=details) from exc
        except urllib.error.URLError as exc:
            raise DeckClientError(status=0, message=f"Connection failed: {exc.reason}", details={}) from exc
        except Exception as exc:
            raise DeckClientError(status=0, message=str(exc), details={}) from exc

    def health(self) -> dict[str, Any]:
        """Check service health (unauthenticated GET /health)."""
        url = f"{self.base_url}/health"
        req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                text = resp.read().decode("utf-8")
                return json.loads(text) if text else {}
        except urllib.error.HTTPError as exc:
            raise DeckClientError(status=exc.code, message=f"Health probe failed: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise DeckClientError(status=0, message=f"Health probe unreachable: {exc.reason}") from exc
        except Exception as exc:
            raise DeckClientError(status=0, message=str(exc)) from exc

    def get_status(self) -> dict[str, Any]:
        """Fetch current lesson metadata, page structure, and display state."""
        return self._request("GET", "/api/v1/status")

    def list_staged(self, series_id: str | None = None) -> list[dict[str, Any]]:
        """Retrieve candidate staged images, optionally filtered by series_id."""
        query = {"series_id": series_id} if series_id else None
        res = self._request("GET", "/api/v1/staged", query=query)
        if isinstance(res, dict):
            return res.get("items", [])
        return res if isinstance(res, list) else []

    def search_library(self, query: str = "", limit: int = 12) -> list[dict[str, Any]]:
        """Search the reusable resource library for images."""
        query_params = {"q": query, "limit": limit}
        res = self._request("GET", "/api/v1/library", query=query_params)
        if isinstance(res, dict):
            return res.get("items", [])
        return res if isinstance(res, list) else []

    def get_thumbnail(self, version_id: str) -> bytes:
        """Fetch and locally cache downscaled thumbnail bytes for a version_id."""
        cleaned_vid = str(version_id or "").strip()
        if not cleaned_vid:
            raise ValueError("version_id is required to fetch a thumbnail.")
        if cleaned_vid in self._thumb_cache:
            return self._thumb_cache[cleaned_vid]

        encoded_vid = urllib.parse.quote(cleaned_vid)
        raw_bytes = self._request("GET", f"/api/v1/thumb/{encoded_vid}", is_binary=True)
        if not isinstance(raw_bytes, bytes):
            raise DeckClientError(status=500, message="Invalid thumbnail response received.")
        self._thumb_cache[cleaned_vid] = raw_bytes
        return raw_bytes

    def stage_images(
        self,
        query: str | None = None,
        version_ids: list[str] | None = None,
        series_id: str | None = None,
    ) -> dict[str, Any]:
        """Stage candidate images from a query or version list into the staging tray."""
        body: dict[str, Any] = {}
        if query is not None:
            body["query"] = query
        if version_ids is not None:
            body["version_ids"] = version_ids
        if series_id is not None:
            body["series_id"] = series_id
        return self._request("POST", "/api/v1/board/stage", body=body)

    def present_image(
        self,
        version_id: str,
        target: str = "current_page",
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Present a staged image on the Teaching Board in clear space."""
        cleaned_vid = str(version_id or "").strip()
        if not cleaned_vid:
            raise ValueError("version_id is required to present an image.")
        body: dict[str, Any] = {
            "version_id": cleaned_vid,
            "target": target,
        }
        if expected_revision is not None:
            body["expected_revision"] = expected_revision
        return self._request("POST", "/api/v1/board/present-image", body=body)

    def board_control(self, action: str) -> dict[str, Any]:
        """Execute a board session control or navigation action."""
        cleaned_action = str(action or "").strip().lower()
        if not cleaned_action:
            raise ValueError("action is required.")
        return self._request("POST", "/api/v1/board/control", body={"action": cleaned_action})

    def switch_display(self, target: str) -> dict[str, Any]:
        """Switch the classroom student display to a specific application or the Board."""
        cleaned_target = str(target or "").strip().lower()
        if not cleaned_target:
            raise ValueError("target is required.")
        return self._request("POST", "/api/v1/display/switch", body={"target": cleaned_target})


class InProcessDeckClient:
    """Direct in-process client adapter for launching TeacherDeckWindow inside the Qt host process."""

    def __init__(self, bridge: Any, base_url: str = "http://127.0.0.1:8790") -> None:
        self.bridge = bridge
        self.base_url = base_url
        self._thumb_cache: dict[str, bytes] = {}

    def _call(self, fn, *args, **kwargs) -> Any:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            status = getattr(exc, "status", 400 if isinstance(exc, ValueError) else 500)
            message = getattr(exc, "message", str(exc))
            details = getattr(exc, "details", {})
            raise DeckClientError(status=status, message=message, details=details) from exc

    def health(self) -> dict[str, Any]:
        return {"ok": True, "status": "ok"}

    def get_status(self) -> dict[str, Any]:
        return self._call(self.bridge.get_status)

    def list_staged(self, series_id: str | None = None) -> list[dict[str, Any]]:
        return self._call(self.bridge.list_staged, series_id=series_id)

    def search_library(self, query: str = "", limit: int = 12) -> list[dict[str, Any]]:
        return self._call(self.bridge.search_library, query=query, limit=limit)

    def get_thumbnail(self, version_id: str) -> bytes:
        cleaned_vid = str(version_id or "").strip()
        if cleaned_vid in self._thumb_cache:
            return self._thumb_cache[cleaned_vid]
        thumb = self._call(self.bridge.get_thumbnail, cleaned_vid)
        if not thumb:
            raise DeckClientError(status=404, message="Thumbnail not found")
        self._thumb_cache[cleaned_vid] = thumb
        return thumb

    def stage_images(
        self,
        query: str | None = None,
        version_ids: list[str] | None = None,
        series_id: str | None = None,
    ) -> dict[str, Any]:
        sid, items = self._call(
            self.bridge.stage_images,
            query=query,
            version_ids=version_ids,
            series_id=series_id,
        )
        return {"ok": True, "series_id": sid, "items": items}

    def present_image(
        self,
        version_id: str,
        target: str = "current_page",
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        return self._call(
            self.bridge.present_image,
            version_id=version_id,
            target=target,
            expected_revision=expected_revision,
        )

    def board_control(self, action: str) -> dict[str, Any]:
        return self._call(self.bridge.board_control, action)

    def switch_display(self, target: str) -> dict[str, Any]:
        return self._call(self.bridge.switch_display, target)


def load_deck_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """Load configuration merged from defaults, optional JSON file, and environment variables."""
    cfg: dict[str, Any] = {
        "url": "http://127.0.0.1:8790",
        "token": "",
        "poll_ms": 1000,
        "windowed": False,
        "kiosk": False,
        "width": 1024,
        "height": 600,
    }

    if config_path is not None:
        p = Path(config_path).expanduser().resolve()
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    if "url" in data:
                        cfg["url"] = str(data["url"]).strip()
                    if "token" in data:
                        cfg["token"] = str(data["token"]).strip()
                    if "poll_ms" in data:
                        cfg["poll_ms"] = int(data["poll_ms"])
                    if "windowed" in data:
                        cfg["windowed"] = bool(data["windowed"])
                    if "kiosk" in data:
                        cfg["kiosk"] = bool(data["kiosk"])
                    if "width" in data:
                        cfg["width"] = int(data["width"])
                    if "height" in data:
                        cfg["height"] = int(data["height"])
            except Exception:
                pass

    env_url = os.environ.get("TEACHER_DECK_URL")
    if env_url:
        cfg["url"] = env_url.strip()

    env_token = os.environ.get("TEACHER_DECK_TOKEN")
    if env_token:
        cfg["token"] = env_token.strip()

    env_poll = os.environ.get("TEACHER_DECK_POLL_MS")
    if env_poll:
        try:
            cfg["poll_ms"] = int(env_poll.strip())
        except ValueError:
            pass

    env_win = os.environ.get("TEACHER_DECK_WINDOWED")
    if env_win:
        cfg["windowed"] = env_win.strip().lower() in {"1", "true", "yes"}

    env_kiosk = os.environ.get("TEACHER_DECK_KIOSK")
    if env_kiosk:
        cfg["kiosk"] = env_kiosk.strip().lower() in {"1", "true", "yes"}

    env_w = os.environ.get("TEACHER_DECK_WIDTH")
    if env_w:
        try:
            cfg["width"] = int(env_w.strip())
        except ValueError:
            pass

    env_h = os.environ.get("TEACHER_DECK_HEIGHT")
    if env_h:
        try:
            cfg["height"] = int(env_h.strip())
        except ValueError:
            pass

    return cfg
