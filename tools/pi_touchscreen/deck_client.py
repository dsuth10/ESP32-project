"""HTTP client and configuration loader for the JoshuaOS Podium & Teacher Deck API.

Australian English spelling conventions and Python standard library only.
Provides authenticated access to lesson status, multi-host Tailscale switching,
image candidate staging, page navigation, MrSutherland.net web lesson launching,
Glass Ink overlay controls, and Hermes Showrunner predictive cues with zero
external dependencies.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


def _normalise_hosts(
    hosts: list[dict[str, Any]] | None,
    default_url: str,
    default_token: str,
) -> list[dict[str, str]]:
    """Normalise a list of host dicts into a guaranteed non-empty list."""
    normalised: list[dict[str, str]] = []
    if isinstance(hosts, list):
        for idx, raw in enumerate(hosts):
            if not isinstance(raw, dict):
                continue
            url = str(raw.get("url") or "").strip().rstrip("/")
            if not url:
                continue
            host_id = str(raw.get("id") or f"host-{idx + 1}").strip()
            label = str(raw.get("label") or host_id).strip()
            token = str(raw.get("token") if raw.get("token") is not None else default_token).strip()
            normalised.append(
                {
                    "id": host_id,
                    "label": label,
                    "url": url,
                    "token": token,
                }
            )
    if not normalised:
        normalised.append(
            {
                "id": "default",
                "label": "Classroom PC",
                "url": default_url,
                "token": default_token,
            }
        )
    return normalised


def _dispatch_showrunner_cue(client: Any, cue: dict[str, Any]) -> dict[str, Any]:
    """Execute a predictive Hermes Showrunner cue against any deck client."""
    if not isinstance(cue, dict):
        raise ValueError("cue must be a dictionary.")
    kind = str(cue.get("kind") or "").strip().lower()
    if not kind:
        raise ValueError("cue['kind'] is required.")
    payload = cue.get("payload") if isinstance(cue.get("payload"), dict) else cue

    if kind == "open_web":
        url = str(payload.get("url") or "").strip()
        title = str(payload.get("title") or cue.get("label") or "").strip()
        return client.open_web_lesson(url=url, title=title)
    if kind == "switch_display":
        target = str(payload.get("target") or "board").strip()
        return client.switch_display(target=target)
    if kind == "stage_query":
        query = str(payload.get("query") or "").strip()
        return client.stage_images(query=query)
    if kind == "glass_ink":
        action = str(payload.get("action") or "draw").strip()
        colour = payload.get("colour")
        width = payload.get("width")
        target = str(payload.get("target") or "new_page").strip()
        return client.glass_control(action=action, colour=colour, width=width, target=target)
    if kind == "board_control":
        action = str(payload.get("action") or "next_page").strip()
        return client.board_control(action=action)

    raise ValueError(f"Unsupported showrunner cue kind: {kind}")


class DeckClientError(Exception):
    """Structured error raised by TeacherDeckClient on network or API failures."""

    def __init__(self, status: int, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(f"[{status}] {message}" if status else message)
        self.status = status
        self.message = message
        self.details = details or {}


class TeacherDeckClient:
    """Authenticated HTTP client for the Windows-hosted JoshuaOS Podium / Teacher Deck service."""

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 3.0,
        hosts: list[dict[str, Any]] | None = None,
        active_host_id: str | None = None,
    ) -> None:
        cleaned_url = str(base_url or "").strip().rstrip("/")
        if not cleaned_url:
            raise ValueError("base_url must be a non-empty string.")
        self.base_url = cleaned_url
        self.token = str(token or "").strip()
        self.timeout = max(0.1, float(timeout))
        self._thumb_cache: dict[str, bytes] = {}

        self._hosts: list[dict[str, str]] = _normalise_hosts(
            hosts=hosts,
            default_url=self.base_url,
            default_token=self.token,
        )
        resolved_id = str(active_host_id or "").strip()
        matching_host = next((h for h in self._hosts if h["id"] == resolved_id), None)
        if matching_host is not None:
            self.active_host_id = matching_host["id"]
        else:
            url_match = next((h for h in self._hosts if h["url"] == self.base_url), None)
            self.active_host_id = (url_match or self._hosts[0])["id"]

    def list_hosts(self) -> list[dict[str, Any]]:
        """Return configured Tailscale/LAN host targets."""
        return [dict(h) for h in self._hosts]

    def get_active_host(self) -> dict[str, Any]:
        """Return the currently active host profile dictionary."""
        for h in self._hosts:
            if h["id"] == self.active_host_id:
                return dict(h)
        return dict(self._hosts[0])

    def switch_host(self, host_id: str) -> dict[str, Any]:
        """Switch the client target to another configured host (e.g. School PC <-> Home PC)."""
        cleaned_id = str(host_id or "").strip()
        target = next((h for h in self._hosts if h["id"] == cleaned_id), None)
        if target is None:
            raise ValueError(f"Unknown host_id: {cleaned_id}")
        self.active_host_id = target["id"]
        self.base_url = target["url"].rstrip("/")
        if target.get("token"):
            self.token = target["token"]
        self._thumb_cache.clear()
        return dict(target)

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
        """Fetch current lesson metadata, page structure, display state, and showrunner cues."""
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

    def list_catalogue(self) -> list[dict[str, Any]]:
        """Fetch interactive web lessons and MrSutherland.net launchpad items."""
        res = self._request("GET", "/api/v1/catalogue")
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

    def open_web_lesson(self, url: str, title: str = "") -> dict[str, Any]:
        """Launch a web lesson (e.g. from MrSutherland.net) on the student display."""
        cleaned_url = str(url or "").strip()
        if not cleaned_url:
            raise ValueError("url is required to open a web lesson.")
        body = {
            "url": cleaned_url,
            "title": str(title or "").strip(),
        }
        return self._request("POST", "/api/v1/display/open-url", body=body)

    def glass_control(
        self,
        action: str,
        colour: str | None = None,
        width: float | None = None,
        target: str = "new_page",
    ) -> dict[str, Any]:
        """Control the transparent Glass Ink annotation overlay over any application."""
        cleaned_action = str(action or "").strip().lower()
        if not cleaned_action:
            raise ValueError("action is required for glass_control.")
        body: dict[str, Any] = {
            "action": cleaned_action,
            "target": str(target or "new_page").strip(),
        }
        if colour is not None:
            body["colour"] = str(colour).strip()
        if width is not None:
            body["width"] = float(width)
        return self._request("POST", "/api/v1/glass/control", body=body)

    def execute_showrunner_cue(self, cue: dict[str, Any]) -> dict[str, Any]:
        """Execute a predictive Hermes Showrunner cue."""
        return _dispatch_showrunner_cue(self, cue)


class InProcessDeckClient:
    """Direct in-process client adapter for launching TeacherDeckWindow inside the Qt host process."""

    def __init__(
        self,
        bridge: Any,
        base_url: str = "http://127.0.0.1:8790",
        hosts: list[dict[str, Any]] | None = None,
        active_host_id: str | None = None,
    ) -> None:
        self.bridge = bridge
        self.base_url = str(base_url or "http://127.0.0.1:8790").strip().rstrip("/")
        self._thumb_cache: dict[str, bytes] = {}
        self._hosts: list[dict[str, str]] = _normalise_hosts(
            hosts=hosts,
            default_url=self.base_url,
            default_token="",
        )
        resolved_id = str(active_host_id or "").strip()
        matching_host = next((h for h in self._hosts if h["id"] == resolved_id), None)
        self.active_host_id = matching_host["id"] if matching_host else self._hosts[0]["id"]

    def list_hosts(self) -> list[dict[str, Any]]:
        return [dict(h) for h in self._hosts]

    def get_active_host(self) -> dict[str, Any]:
        for h in self._hosts:
            if h["id"] == self.active_host_id:
                return dict(h)
        return dict(self._hosts[0])

    def switch_host(self, host_id: str) -> dict[str, Any]:
        cleaned_id = str(host_id or "").strip()
        target = next((h for h in self._hosts if h["id"] == cleaned_id), None)
        if target is None:
            raise ValueError(f"Unknown host_id: {cleaned_id}")
        self.active_host_id = target["id"]
        self.base_url = target["url"].rstrip("/")
        self._thumb_cache.clear()
        return dict(target)

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

    def list_catalogue(self) -> list[dict[str, Any]]:
        if hasattr(self.bridge, "list_catalogue"):
            res = self._call(self.bridge.list_catalogue)
            if isinstance(res, dict):
                return res.get("items", [])
            return res if isinstance(res, list) else []
        return []

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

    def open_web_lesson(self, url: str, title: str = "") -> dict[str, Any]:
        cleaned_url = str(url or "").strip()
        if not cleaned_url:
            raise ValueError("url is required to open a web lesson.")
        if hasattr(self.bridge, "open_web_lesson"):
            return self._call(self.bridge.open_web_lesson, url=cleaned_url, title=str(title or "").strip())
        return self.switch_display("chrome")

    def glass_control(
        self,
        action: str,
        colour: str | None = None,
        width: float | None = None,
        target: str = "new_page",
    ) -> dict[str, Any]:
        cleaned_action = str(action or "").strip().lower()
        if not cleaned_action:
            raise ValueError("action is required for glass_control.")
        if hasattr(self.bridge, "glass_control"):
            return self._call(
                self.bridge.glass_control,
                action=cleaned_action,
                colour=colour,
                width=width,
                target=target,
            )
        return {"ok": True, "action": cleaned_action}

    def execute_showrunner_cue(self, cue: dict[str, Any]) -> dict[str, Any]:
        return _dispatch_showrunner_cue(self, cue)


def load_deck_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """Load configuration merged from defaults, optional JSON file, and environment variables."""
    cfg: dict[str, Any] = {
        "url": "http://127.0.0.1:8790",
        "token": "",
        "active_host_id": "default",
        "hosts": [],
        "poll_ms": 1000,
        "windowed": False,
        "kiosk": False,
        "width": 1280,
        "height": 800,
    }

    explicit_url_in_file = False
    if config_path is not None:
        p = Path(config_path).expanduser().resolve()
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    if "url" in data and str(data["url"]).strip():
                        cfg["url"] = str(data["url"]).strip()
                        explicit_url_in_file = True
                    if "token" in data:
                        cfg["token"] = str(data["token"]).strip()
                    if "active_host_id" in data:
                        cfg["active_host_id"] = str(data["active_host_id"]).strip()
                    if isinstance(data.get("hosts"), list):
                        cfg["hosts"] = _normalise_hosts(
                            data["hosts"],
                            default_url=cfg["url"],
                            default_token=cfg["token"],
                        )
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

    env_host_id = os.environ.get("TEACHER_DECK_HOST_ID")
    if env_host_id:
        cfg["active_host_id"] = env_host_id.strip()

    if cfg["hosts"]:
        active_entry = next(
            (h for h in cfg["hosts"] if h["id"] == cfg["active_host_id"]),
            cfg["hosts"][0],
        )
        cfg["active_host_id"] = active_entry["id"]
        if not explicit_url_in_file or env_host_id:
            cfg["url"] = active_entry["url"]
        if active_entry.get("token"):
            cfg["token"] = active_entry["token"]

    env_url = os.environ.get("TEACHER_DECK_URL")
    if env_url:
        cfg["url"] = env_url.strip()

    env_token = os.environ.get("TEACHER_DECK_TOKEN")
    if env_token:
        cfg["token"] = env_token.strip()

    if not cfg["hosts"]:
        cfg["hosts"] = _normalise_hosts(
            None,
            default_url=cfg["url"],
            default_token=cfg["token"],
        )

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
