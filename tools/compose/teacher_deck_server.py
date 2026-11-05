"""Private, authenticated Teacher Deck HTTP API for the Raspberry Pi Touchscreen.

Provides glanceable lesson status, candidate multi-image staging, clear-space
image presentation (strictly preserving existing board objects), board control,
and classroom display switching. Built strictly with standard library HTTP
and PySide6 / PIL thumbnail generation.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import replace
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import textwrap
import threading
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit
import uuid

from board_images import import_prepared
from board_model import (
    BoardConflictError,
    BoardModel,
    BoardValidationError,
    new_object,
    new_page,
)
from board_runtime import _free_image_areas
from board_session import BoardSession
from classroom_catalogue import is_allowlisted_web_url, load_classroom_catalogue
from glass_overlay import GlassInkController
from lesson_showrunner import LessonShowrunner
from monitor_shortcut import (
    APP_BOARD,
    APP_CHROME,
    APP_ONENOTE,
    APP_WORD,
    ActionReceipt,
    MonitorShortcutController,
    active_profile,
)
from teacher_deck_models import (
    StagedImageItem,
    StagingTray,
    validate_control_action,
    validate_display_target,
    validate_present_target,
    validate_uuid,
)

MAX_BODY_BYTES = 64 * 1024  # 64 KiB request body limit
THUMBNAIL_MAX_WIDTH = 320
THUMBNAIL_MAX_HEIGHT = 240
DEFAULT_THUMBNAIL_CACHE_LIMIT = 64


class ApiError(Exception):
    """Structured API error mapped to an HTTP status code."""

    def __init__(self, status: int, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.details = details or {}


def _strict_json_loads(data: bytes | str) -> Any:
    """Parse JSON strictly, rejecting duplicate keys and non-standard constants."""
    text = data.decode("utf-8") if isinstance(data, bytes) else data

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, val in items:
            if key in result:
                raise ValueError(f"Duplicate key in JSON: {key}")
            result[key] = val
        return result

    return json.loads(
        text,
        object_pairs_hook=pairs,
        parse_constant=lambda const: (_ for _ in ()).throw(
            ValueError(f"Constant '{const}' is not allowed in strict JSON.")
        ),
    )


def make_thumbnail_png(
    raw_bytes: bytes,
    max_width: int = THUMBNAIL_MAX_WIDTH,
    max_height: int = THUMBNAIL_MAX_HEIGHT,
) -> bytes:
    """Generate a downscaled PNG thumbnail fitting within the bounding box."""
    try:
        from PySide6.QtCore import QBuffer, QIODevice, Qt
        from PySide6.QtGui import QImage

        qimg = QImage.fromData(raw_bytes)
        if not qimg.isNull():
            scaled = qimg.scaled(
                max_width,
                max_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            scaled.save(buffer, "PNG")
            thumb_bytes = bytes(buffer.data())
            buffer.close()
            return thumb_bytes
    except Exception:
        pass

    # Fallback to PIL if PySide6 image decoding is unavailable
    from PIL import Image
    import io

    with Image.open(io.BytesIO(raw_bytes)) as img:
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()


class LRUThumbnailCache:
    """Thread-safe, bounded in-memory cache for downscaled image thumbnails."""

    def __init__(self, capacity: int = DEFAULT_THUMBNAIL_CACHE_LIMIT) -> None:
        self.capacity = max(1, capacity)
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> bytes | None:
        with self._lock:
            if key not in self._cache:
                return None
            self._cache.move_to_end(key)
            return self._cache[key]

    def put(self, key: str, value: bytes) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            if len(self._cache) > self.capacity:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


def _compute_image_layout(
    page: dict[str, Any],
    img_width: int,
    img_height: int,
    credit: str,
    margin: float,
) -> list[tuple[float, float, float, float, float, float, float, float, float]]:
    """Calculate non-overlapping candidate positions for an image and optional credit."""
    credit_text = credit.strip()
    layouts: list[tuple[float, float, float, float, float, float, float, float, float]] = []
    for x1, y1, x2, y2 in _free_image_areas(page, margin):
        credit_width = x2 - x1
        lines = len(textwrap.wrap(credit_text, width=max(1, int(credit_width / 24)))) if credit_text else 0
        credit_height = lines * 28 + 16 if credit_text else 0
        available_height = y2 - y1 - credit_height - (28 if credit_text else 0)
        if available_height <= 0 or credit_width <= 0:
            continue
        scale = min(credit_width / img_width, available_height / img_height)
        w, h = img_width * scale, img_height * scale
        if min(w, h) >= 80 and max(w, h) >= 128:
            layouts.append((w * h, x1, y1, x2, y2, w, h, available_height, credit_height))
    return layouts


class TeacherDeckBridge:
    """Adapter bridging BoardSession, MediaStore, and controls to the Teacher Deck."""

    def __init__(
        self,
        session: BoardSession,
        library: Any | None = None,
        lesson_media: Any | None = None,
        shortcut_controller: MonitorShortcutController | None = None,
        staging_tray: StagingTray | None = None,
        dispatch_fn: Callable[[Callable[[], Any]], Any] | None = None,
        glass_controller: GlassInkController | None = None,
        showrunner: LessonShowrunner | None = None,
        catalogue: list[dict[str, Any]] | None = None,
    ) -> None:
        if not isinstance(session, BoardSession):
            raise ValueError("session must be an instance of BoardSession.")
        self.session = session
        self.library = library
        self.lesson_media = lesson_media
        self.shortcut_controller = shortcut_controller
        self.staging_tray = staging_tray if staging_tray is not None else StagingTray()
        self.dispatch_fn = dispatch_fn
        self.thumbnail_cache = LRUThumbnailCache()
        self.glass_controller = (
            glass_controller if glass_controller is not None else GlassInkController()
        )
        self._catalogue = (
            list(catalogue) if catalogue is not None else load_classroom_catalogue()
        )
        self.showrunner = (
            showrunner
            if showrunner is not None
            else LessonShowrunner(catalogue=self._catalogue)
        )
        self._last_switched_target: str = "board"

    def dispatch(self, fn: Callable[[], Any]) -> Any:
        """Execute a callable via dispatch_fn if configured, otherwise invoke directly."""
        if self.dispatch_fn is not None:
            return self.dispatch_fn(fn)
        return fn()

    def _read_status_internal(self) -> dict[str, Any]:
        teacher_view = self.session.teacher_view()
        pupil_view = self.session.pupil_view()
        doc = teacher_view["document"]
        pages = [
            {
                "id": p["id"],
                "title": p.get("title", ""),
                "object_count": len(p.get("objects", [])),
            }
            for p in doc.get("pages", [])
        ]
        page_id = teacher_view["page_id"]
        page_index = next((idx for idx, p in enumerate(pages) if p["id"] == page_id), 0)

        disp_summary: dict[str, Any] = {"configured": False, "display": None}
        active_display_target = self._last_switched_target
        if self.shortcut_controller is not None:
            try:
                settings = self.shortcut_controller.load()
                profile = active_profile(settings)
                cd = profile.get("classroom_display")
                if cd:
                    disp_summary = {"configured": True, "display": cd}
                if hasattr(self.shortcut_controller, "detect_active_classroom_target"):
                    detected = self.shortcut_controller.detect_active_classroom_target()
                    if detected and detected != "none":
                        active_display_target = detected
            except Exception:
                pass

        staged_count = len(self.staging_tray.list_items())
        glass_state = self.glass_controller.get_state()
        lesson_title = doc.get("title", "") or "Untitled lesson"

        showrunner_cues = self.showrunner.compute_predictive_cues(
            lesson_title=lesson_title,
            active_target=active_display_target,
            staged_count=staged_count,
            glass_mode=glass_state.get("mode", "off"),
            catalogue=self._catalogue,
        )

        return {
            "ok": True,
            "title": doc.get("title", ""),
            "page_id": page_id,
            "page_index": page_index,
            "page_count": len(pages),
            "pages": pages,
            "frozen": teacher_view["frozen"],
            "revision": teacher_view["revision"],
            "token": teacher_view["token"],
            "pupil_revision": pupil_view["revision"],
            "staged_count": staged_count,
            "classroom_display": disp_summary,
            "active_display_target": active_display_target,
            "glass_ink": glass_state,
            "showrunner_cues": showrunner_cues,
            "catalogue_count": len(self._catalogue),
        }

    def get_status(self) -> dict[str, Any]:
        """Return the current glanceable teacher status snapshot (thread-safe via BoardSession RLock)."""
        return self._read_status_internal()

    def list_staged(self, series_id: str | None = None) -> list[dict[str, Any]]:
        """Return staged candidate images, optionally filtered by series_id."""
        return self.staging_tray.list_items(series_id=series_id)

    def search_library(self, query: str = "", limit: int = 8) -> list[dict[str, Any]]:
        """Search the reusable board resource library."""
        clamped_limit = max(1, min(32, int(limit)))
        if self.library is None:
            return []
        try:
            records = self.library.search(query, limit=clamped_limit)
        except Exception:
            return []

        formatted: list[dict[str, Any]] = []
        for rec in records:
            vid = rec.get("version_id", "")
            meta = rec.get("metadata", {})
            prov = rec.get("provenance", {})
            img_ref = rec.get("image_ref") or {}
            asset_id = img_ref.get("asset_id") or rec.get("resource_id", vid)
            formatted.append(
                {
                    "version_id": vid,
                    "asset_id": asset_id,
                    "title": rec.get("title", "Untitled"),
                    "review_state": rec.get("review_state", "approved"),
                    "origin": meta.get("origin", "library"),
                    "width": meta.get("width") or rec.get("width", 800),
                    "height": meta.get("height") or rec.get("height", 600),
                    "credit": prov.get("attribution", "") or rec.get("credit", ""),
                    "thumb_url": f"/api/v1/thumb/{vid}",
                }
            )
        return formatted

    def get_thumbnail(self, version_id: str) -> bytes | None:
        """Resolve raw image bytes and return a downscaled PNG thumbnail."""
        try:
            cleaned_vid = validate_uuid(version_id, "version_id")
        except ValueError:
            return None

        cached = self.thumbnail_cache.get(cleaned_vid)
        if cached is not None:
            return cached

        raw_bytes: bytes | None = None

        # 1. Check StagingTray for SHA-256 and look in lesson_media
        staged = self.staging_tray.get_version(cleaned_vid)
        if staged and self.lesson_media is not None:
            try:
                blob_p = self.lesson_media.blob_path(staged.sha256)
                if blob_p.is_file():
                    raw_bytes = blob_p.read_bytes()
            except Exception:
                pass

        # 2. Check lesson_media / media_store directly by version_id
        if raw_bytes is None and self.lesson_media is not None:
            try:
                v_record = self.lesson_media.get_version(cleaned_vid)
                if v_record:
                    blob_p = self.lesson_media.blob_path(v_record["sha256"])
                    if blob_p.is_file():
                        raw_bytes = blob_p.read_bytes()
            except Exception:
                pass

        # 3. Check BoardResourceLibrary
        if raw_bytes is None and self.library is not None:
            try:
                cat_rec = self.library.catalogue.get_resource_by_version(cleaned_vid)
                if cat_rec:
                    _, prepared = self.library.prepare_record(cat_rec)
                    raw_bytes = prepared.data
            except Exception:
                pass

        # 4. Check session image resolver as fallback
        if raw_bytes is None and getattr(self.session, "_image_resolver", None):
            try:
                sha = staged.sha256 if staged else ""
                aid = staged.asset_id if staged else cleaned_vid
                ref = {"asset_id": aid, "version_id": cleaned_vid, "sha256": sha}
                raw_bytes = self.session.resolve_image(ref)
            except Exception:
                pass

        if raw_bytes is None:
            return None

        try:
            thumb = make_thumbnail_png(raw_bytes)
            self.thumbnail_cache.put(cleaned_vid, thumb)
            return thumb
        except Exception:
            return None

    def stage_images(
        self,
        query: str | None = None,
        version_ids: list[str] | None = None,
        series_id: str | None = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Stage candidate images from query results or version IDs into StagingTray."""
        effective_series_id = (
            series_id.strip() if (series_id and series_id.strip()) else str(uuid.uuid4())
        )
        items_to_stage: list[StagedImageItem] = []

        if query and query.strip() and self.library is not None:
            try:
                matches = self.library.search(query.strip(), limit=16)
                for rec in matches:
                    vid = rec.get("version_id", "")
                    meta = rec.get("metadata", {})
                    prov = rec.get("provenance", {})
                    img_ref = rec.get("image_ref") or {}
                    asset_id = img_ref.get("asset_id") or rec.get("resource_id", vid)
                    sha = rec.get("content_hash") or img_ref.get("sha256", "0" * 64)
                    items_to_stage.append(
                        StagedImageItem(
                            stage_id=str(uuid.uuid4()),
                            series_id=effective_series_id,
                            asset_id=asset_id,
                            version_id=vid,
                            sha256=sha,
                            title=rec.get("title", "Image"),
                            width=meta.get("width") or rec.get("width", 800),
                            height=meta.get("height") or rec.get("height", 600),
                            origin=meta.get("origin", "library"),
                            review_state=rec.get("review_state", "approved"),
                            credit=prov.get("attribution", "") or rec.get("credit", ""),
                        )
                    )
            except Exception:
                pass

        if version_ids:
            for vid in version_ids:
                if not isinstance(vid, str):
                    continue
                cleaned_vid = vid.strip()
                item: StagedImageItem | None = None
                if self.library is not None:
                    try:
                        rec = self.library.catalogue.get_resource_by_version(cleaned_vid)
                        if rec:
                            meta = rec.get("metadata", {})
                            prov = rec.get("provenance", {})
                            img_ref = rec.get("image_ref") or {}
                            asset_id = img_ref.get("asset_id") or rec.get("resource_id", cleaned_vid)
                            sha = rec.get("content_hash") or img_ref.get("sha256", "0" * 64)
                            item = StagedImageItem(
                                stage_id=str(uuid.uuid4()),
                                series_id=effective_series_id,
                                asset_id=asset_id,
                                version_id=cleaned_vid,
                                sha256=sha,
                                title=rec.get("title", "Image"),
                                width=meta.get("width") or rec.get("width", 800),
                                height=meta.get("height") or rec.get("height", 600),
                                origin=meta.get("origin", "library"),
                                review_state=rec.get("review_state", "approved"),
                                credit=prov.get("attribution", "") or rec.get("credit", ""),
                            )
                    except Exception:
                        pass

                if item is None and self.lesson_media is not None:
                    try:
                        vr = self.lesson_media.get_version(cleaned_vid)
                        if vr:
                            item = StagedImageItem(
                                stage_id=str(uuid.uuid4()),
                                series_id=effective_series_id,
                                asset_id=vr["asset_id"],
                                version_id=vr["version_id"],
                                sha256=vr["sha256"],
                                title=vr.get("title", "Image"),
                                width=vr.get("width", 800),
                                height=vr.get("height", 600),
                                origin=vr.get("origin", "import"),
                                review_state="approved" if vr.get("canonical_version_id") == cleaned_vid else "draft",
                                credit=vr.get("source", {}).get("attribution", ""),
                            )
                    except Exception:
                        pass

                if item is not None:
                    items_to_stage.append(item)

        staged = self.staging_tray.stage_series(items_to_stage, series_id=effective_series_id)
        return effective_series_id, [s.as_dict() for s in staged]

    def present_image(
        self,
        version_id: str,
        target: str = "current_page",
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Present a staged or library image onto the board in clear space."""
        cleaned_target = validate_present_target(target)
        cleaned_vid = validate_uuid(version_id, "version_id")

        def _execute_present() -> dict[str, Any]:
            view = self.session.teacher_view()
            curr_rev = view["revision"]
            curr_tok = view["token"]

            if expected_revision is not None and expected_revision != curr_rev:
                raise ApiError(
                    409,
                    f"Lesson revision changed (expected {expected_revision}, current {curr_rev}).",
                )

            # 1. Resolve image metadata and durable storage
            staged = self.staging_tray.get_version(cleaned_vid)
            lib_rec = None
            if self.library is not None:
                try:
                    lib_rec = self.library.catalogue.get_resource_by_version(cleaned_vid)
                except Exception:
                    pass

            media_ver = None
            if self.lesson_media is not None:
                try:
                    media_ver = self.lesson_media.get_version(cleaned_vid)
                except Exception:
                    pass

            if staged is None and lib_rec is None and media_ver is None:
                raise ApiError(404, f"Image version '{cleaned_vid}' not found.")

            origin = "library"
            review_state = "approved"

            if staged is not None:
                image_ref = {
                    "asset_id": staged.asset_id,
                    "version_id": staged.version_id,
                    "sha256": staged.sha256,
                }
                width = staged.width
                height = staged.height
                credit = staged.credit
                origin = staged.origin
                review_state = staged.review_state
                # Ensure bytes are in lesson_media if library record exists
                if lib_rec is not None and self.lesson_media is not None:
                    try:
                        self.library.select(lib_rec, self.lesson_media)
                    except Exception:
                        pass
            elif lib_rec is not None and self.lesson_media is not None:
                selected = self.library.select(lib_rec, self.lesson_media)
                image_ref = selected["image_ref"]
                width = selected["width"]
                height = selected["height"]
                credit = selected.get("credit", "")
                origin = lib_rec.get("metadata", {}).get("origin", "library")
                review_state = lib_rec.get("review_state", "approved")
            elif media_ver is not None:
                image_ref = {
                    "asset_id": media_ver["asset_id"],
                    "version_id": media_ver["version_id"],
                    "sha256": media_ver["sha256"],
                }
                width = media_ver["width"]
                height = media_ver["height"]
                credit = media_ver.get("source", {}).get("attribution", "")
                origin = media_ver.get("origin", "import")
                review_state = (
                    "approved" if media_ver.get("canonical_version_id") == cleaned_vid else "draft"
                )
            else:
                raise ApiError(404, f"Image version '{cleaned_vid}' could not be resolved.")

            # 2. Determine target page without mutating session before layout validation
            if cleaned_target == "new_page":
                pages = view["document"]["pages"]
                target_page = new_page(f"Page {len(pages) + 1}")
            else:
                target_page = next(
                    (p for p in view["document"]["pages"] if p["id"] == view["page_id"]),
                    None,
                )
                if target_page is None:
                    raise ApiError(400, "Current page was not found in lesson.")

            # 3. Compute clear-space layout
            margin = 64 * min(target_page["width"] / 1600, target_page["height"] / 900)
            layouts = _compute_image_layout(target_page, width, height, credit, margin)
            if not layouts:
                raise ApiError(
                    409,
                    "Not enough clear space on the current page to place this image without covering existing content. "
                    "Choose 'new_page' to present on a fresh page. No existing objects were moved or deleted.",
                )

            _, x1, y1, x2, y2, w, h, available_height, credit_height = max(
                layouts, key=lambda item: item[0]
            )
            img_x = x1 + (x2 - x1 - w) / 2
            img_y = y1 + (available_height - h) / 2
            image_obj = new_object("image", image_ref=image_ref, x=img_x, y=img_y, width=w, height=h)
            objects_to_add = [image_obj]

            if credit.strip():
                credit_obj = new_object(
                    "text",
                    text=credit.strip(),
                    x=x1,
                    y=y2 - credit_height,
                    width=x2 - x1,
                    height=credit_height,
                    font_size=20,
                    colour="#374151",
                )
                objects_to_add.append(credit_obj)

            commands: list[dict[str, Any]] = []
            if cleaned_target == "new_page":
                commands.append({"op": "add_page", "page": target_page})
            commands.extend(
                {"op": "add_object", "page_id": target_page["id"], "object": obj}
                for obj in objects_to_add
            )
            final_view = self.session.teacher_apply(
                commands,
                expected_revision=curr_rev,
                expected_token=curr_tok,
            )
            if cleaned_target == "new_page":
                self.session.teacher_navigate(target_page["id"], expected_token=final_view["token"])
                final_view = self.session.teacher_view()

            # 4. Record approval only after successful presentation
            approved_version_id: str | None = None
            if origin == "generated" and review_state != "approved":
                approved_version_id = cleaned_vid
                if self.library is not None:
                    try:
                        self.library.approve(cleaned_vid)
                    except Exception:
                        pass
                if staged is not None:
                    self.staging_tray.stage_item(replace(staged, review_state="approved"))

            return {
                "ok": True,
                "page_id": target_page["id"],
                "revision": final_view["revision"],
                "added_object_ids": [obj["id"] for obj in objects_to_add],
                "approved_version_id": approved_version_id,
            }

        return self.dispatch(_execute_present)

    def board_control(self, action: str) -> dict[str, Any]:
        """Execute a board navigation or session control action."""
        cleaned_action = validate_control_action(action)

        def _execute_control() -> dict[str, Any]:
            view = self.session.teacher_view()
            curr_rev = view["revision"]
            curr_tok = view["token"]
            pages = view["document"]["pages"]
            curr_page_id = view["page_id"]
            curr_idx = next((i for i, p in enumerate(pages) if p["id"] == curr_page_id), 0)

            if cleaned_action == "freeze":
                self.session.freeze(expected_token=curr_tok)
            elif cleaned_action == "resume":
                self.session.resume(expected_token=curr_tok)
            elif cleaned_action == "prev_page":
                if curr_idx > 0:
                    target_id = pages[curr_idx - 1]["id"]
                    self.session.teacher_navigate(target_id, expected_token=curr_tok)
            elif cleaned_action == "next_page":
                if curr_idx < len(pages) - 1:
                    target_id = pages[curr_idx + 1]["id"]
                    self.session.teacher_navigate(target_id, expected_token=curr_tok)
            elif cleaned_action == "new_page":
                new_p = new_page(f"Page {len(pages) + 1}")
                self.session.teacher_apply(
                    [{"op": "add_page", "page": new_p}],
                    expected_revision=curr_rev,
                    expected_token=curr_tok,
                )
                new_tok = self.session.teacher_view()["token"]
                self.session.teacher_navigate(new_p["id"], expected_token=new_tok)
            elif cleaned_action == "undo":
                self.session.teacher_undo(expected_revision=curr_rev, expected_token=curr_tok)
            elif cleaned_action == "redo":
                self.session.teacher_redo(expected_revision=curr_rev, expected_token=curr_tok)

            return {
                "ok": True,
                "action": cleaned_action,
                "status": self._read_status_internal(),
            }

        return self.dispatch(_execute_control)

    def switch_display(self, target: str) -> dict[str, Any]:
        """Switch student display focus to Board, OneNote, Word, or Chrome."""
        cleaned_target = validate_display_target(target)
        if self.shortcut_controller is None:
            raise ApiError(503, "MonitorShortcutController is not configured.")

        if cleaned_target == "board":
            receipt = self.shortcut_controller.bring_board_to_classroom_display()
        else:
            receipt = self.shortcut_controller.open_app_on_classroom_display(cleaned_target)

        if receipt.kind == "ok":
            self._last_switched_target = cleaned_target
            self.showrunner.record_event("switch_display", {"target": cleaned_target})

        return {
            "ok": receipt.kind == "ok",
            "receipt": receipt.as_dict(),
        }

    def list_catalogue(self) -> list[dict[str, Any]]:
        """Return the curated MrSutherland.net classroom web lesson catalogue."""
        return [dict(item) for item in self._catalogue]

    def open_web_lesson(self, url: str, title: str = "") -> dict[str, Any]:
        """Launch an allowlisted MrSutherland.net web lesson onto the classroom display."""
        cleaned_url = str(url or "").strip()
        if not cleaned_url:
            raise ApiError(400, "Field 'url' is required.")
        if not is_allowlisted_web_url(cleaned_url):
            raise ApiError(400, "Web lesson URL is not allowlisted.")
        if self.shortcut_controller is None:
            raise ApiError(503, "MonitorShortcutController is not configured.")

        receipt = self.shortcut_controller.open_web_url_on_classroom_display(
            url=cleaned_url,
            title=str(title or "").strip(),
        )
        if receipt.kind == "ok":
            self._last_switched_target = "chrome"
            self.showrunner.update_context(
                active_display_target="chrome",
                active_web_url=cleaned_url,
            )
            self.showrunner.record_event(
                "open_web",
                {"url": cleaned_url, "title": str(title or "").strip()},
            )

        return {
            "ok": receipt.kind == "ok",
            "url": cleaned_url,
            "title": str(title or "").strip(),
            "receipt": receipt.as_dict(),
        }

    def glass_control(
        self,
        action: str,
        colour: str | None = None,
        width: float | None = None,
        target: str = "new_page",
    ) -> dict[str, Any]:
        """Control the Unified Glass Ink overlay or snap annotations onto the Teaching Board."""
        cleaned_action = str(action or "").strip().lower()
        if not cleaned_action:
            raise ApiError(400, "Field 'action' is required.")

        def _execute_glass() -> dict[str, Any]:
            if colour is not None or width is not None:
                try:
                    self.glass_controller.set_pen(colour=colour, width=width)
                except ValueError as exc:
                    raise ApiError(400, str(exc)) from exc

            if cleaned_action in {"off", "draw", "interact", "eraser"}:
                state = self.glass_controller.set_mode(cleaned_action)
                self.showrunner.update_context(glass_mode=state["mode"])
                self.showrunner.record_event("glass_mode", {"mode": state["mode"]})
                return {"ok": True, "action": cleaned_action, "glass_ink": state}

            if cleaned_action == "set_pen":
                state = self.glass_controller.get_state()
                return {"ok": True, "action": cleaned_action, "glass_ink": state}

            if cleaned_action == "clear":
                cleared = self.glass_controller.clear()
                state = self.glass_controller.get_state()
                self.showrunner.record_event("glass_clear", {"cleared": cleared})
                return {
                    "ok": True,
                    "action": cleaned_action,
                    "cleared": cleared,
                    "glass_ink": state,
                }

            if cleaned_action == "undo":
                undone = self.glass_controller.undo()
                return {
                    "ok": True,
                    "action": cleaned_action,
                    "undone": undone,
                    "glass_ink": self.glass_controller.get_state(),
                }

            if cleaned_action == "redo":
                redone = self.glass_controller.redo()
                return {
                    "ok": True,
                    "action": cleaned_action,
                    "redone": redone,
                    "glass_ink": self.glass_controller.get_state(),
                }

            if cleaned_action == "snap_to_board":
                cleaned_target = validate_present_target(target or "new_page")
                png_bytes = self.glass_controller.render_to_png(width=1600, height=900)
                snap_title = f"Annotated Screen Snapshot ({self._last_switched_target.title()})"
                if self.lesson_media is not None:
                    imported = self.lesson_media.import_bytes(
                        png_bytes,
                        title=snap_title,
                        origin="import",
                    )
                    vid = imported["version_id"]
                    aid = imported["asset_id"]
                    sha = imported["sha256"]
                    w = int(imported.get("width", 1600))
                    h = int(imported.get("height", 900))
                else:
                    import hashlib

                    vid = str(uuid.uuid4())
                    aid = str(uuid.uuid4())
                    sha = hashlib.sha256(png_bytes).hexdigest()
                    w, h = 1600, 900

                staged_item = StagedImageItem(
                    stage_id=str(uuid.uuid4()),
                    series_id="glass-snapshots",
                    asset_id=aid,
                    version_id=vid,
                    sha256=sha,
                    title=snap_title,
                    width=w,
                    height=h,
                    origin="import",
                    review_state="approved",
                    credit="Captured via JoshuaOS Glass Ink Overlay",
                )
                self.staging_tray.stage_item(staged_item)
                present_res: dict[str, Any] = {}
                if self.lesson_media is not None:
                    try:
                        present_res = self.present_image(
                            version_id=vid,
                            target=cleaned_target,
                        )
                    except ApiError as exc:
                        if exc.status == 409 and cleaned_target == "current_page":
                            present_res = self.present_image(
                                version_id=vid,
                                target="new_page",
                            )
                        else:
                            raise
                self.glass_controller.clear()
                self.glass_controller.set_mode("off")
                self.showrunner.update_context(glass_mode="off")
                self.showrunner.record_event("snap_to_board", {"version_id": vid})
                return {
                    "ok": True,
                    "action": cleaned_action,
                    "version_id": vid,
                    "staged_item": staged_item.as_dict(),
                    "presented": present_res,
                    "glass_ink": self.glass_controller.get_state(),
                }

            raise ApiError(
                400,
                f"Unsupported glass_control action '{cleaned_action}'. "
                "Allowed: off, draw, interact, eraser, set_pen, clear, undo, redo, snap_to_board.",
            )

        return self.dispatch(_execute_glass)


class TeacherDeckRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Teacher Deck API requests."""

    server: TeacherDeckHTTPServer
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        """Suppress stdout request logging to avoid token leakage."""
        return

    def _send(
        self,
        status: int,
        body: bytes = b"",
        content_type: str = "application/json",
    ) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if body:
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

    def _json(self, status: int, value: Any) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self._send(status, payload, "application/json")

    def _auth(self) -> bool:
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            self._json(401, {"ok": False, "error": "Authentication required. Provide Authorization: Bearer <token>"})
            return False
        token = auth_header[7:].strip().encode("utf-8")
        if not hmac.compare_digest(token, self.server.token.encode("utf-8")):
            self._json(401, {"ok": False, "error": "Invalid bearer token"})
            return False
        return True

    def _read_body(self) -> bytes:
        length_header = self.headers.get("Content-Length")
        if not length_header:
            return b""
        try:
            length = int(length_header)
        except ValueError:
            raise ApiError(400, "Invalid Content-Length header.")
        if length < 0:
            raise ApiError(400, "Negative Content-Length header.")
        if length > MAX_BODY_BYTES:
            # Drain body so Windows TCP stack does not reset connection before sending 413
            try:
                self.rfile.read(min(length, 1024 * 1024))
            except Exception:
                pass
            raise ApiError(413, f"Request body exceeds {MAX_BODY_BYTES} byte limit.")
        return self.rfile.read(length)

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path

        if path == "/health":
            self._json(200, {"ok": True, "status": "ok"})
            return

        if not self._auth():
            return

        try:
            if path == "/api/v1/status":
                status = self.server.bridge.get_status()
                self._json(200, status)
            elif path == "/api/v1/staged":
                q = parse_qs(parsed.query)
                series_id = q.get("series_id", [None])[0]
                items = self.server.bridge.list_staged(series_id=series_id)
                self._json(200, {"ok": True, "items": items})
            elif path == "/api/v1/library":
                q = parse_qs(parsed.query)
                query_str = q.get("q", [""])[0]
                try:
                    limit = int(q.get("limit", ["8"])[0])
                except ValueError:
                    limit = 8
                items = self.server.bridge.search_library(query=query_str, limit=limit)
                self._json(200, {"ok": True, "items": items})
            elif path == "/api/v1/catalogue":
                items = self.server.bridge.list_catalogue()
                self._json(200, {"ok": True, "items": items})
            elif path.startswith("/api/v1/thumb/"):
                version_id = path[len("/api/v1/thumb/") :].strip("/")
                thumb = self.server.bridge.get_thumbnail(version_id)
                if thumb is None:
                    self._json(404, {"ok": False, "error": "Thumbnail not found"})
                else:
                    self._send(200, thumb, "image/png")
            else:
                self._json(404, {"ok": False, "error": f"Endpoint not found: {path}"})
        except ApiError as exc:
            self._json(exc.status, {"ok": False, "error": exc.message, **exc.details})
        except Exception as exc:
            self._json(500, {"ok": False, "error": f"Internal server error: {exc}"})

    def do_POST(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path

        if not self._auth():
            return

        try:
            raw_body = self._read_body()
            body: dict[str, Any] = {}
            if raw_body:
                try:
                    body = _strict_json_loads(raw_body)
                except ValueError as exc:
                    raise ApiError(400, f"Invalid JSON payload: {exc}")
            if not isinstance(body, dict):
                raise ApiError(400, "Request body must be a JSON object.")

            if path == "/api/v1/board/stage":
                query = body.get("query")
                version_ids = body.get("version_ids")
                series_id = body.get("series_id")
                sid, items = self.server.bridge.stage_images(
                    query=query, version_ids=version_ids, series_id=series_id
                )
                self._json(200, {"ok": True, "series_id": sid, "items": items})
            elif path == "/api/v1/board/present-image":
                version_id = body.get("version_id")
                if not version_id:
                    raise ApiError(400, "Field 'version_id' is required.")
                target = body.get("target", "current_page")
                expected_revision = body.get("expected_revision")
                res = self.server.bridge.present_image(
                    version_id=version_id,
                    target=target,
                    expected_revision=expected_revision,
                )
                self._json(200, res)
            elif path == "/api/v1/board/control":
                action = body.get("action")
                if not action:
                    raise ApiError(400, "Field 'action' is required.")
                res = self.server.bridge.board_control(action)
                self._json(200, res)
            elif path == "/api/v1/display/switch":
                target = body.get("target")
                if not target:
                    raise ApiError(400, "Field 'target' is required.")
                res = self.server.bridge.switch_display(target)
                self._json(200, res)
            elif path == "/api/v1/display/open-url":
                url = body.get("url")
                if not url:
                    raise ApiError(400, "Field 'url' is required.")
                title = body.get("title", "")
                res = self.server.bridge.open_web_lesson(url=url, title=title)
                self._json(200, res)
            elif path == "/api/v1/glass/control":
                action = body.get("action") or body.get("mode")
                if not action:
                    raise ApiError(400, "Field 'action' is required.")
                colour = body.get("colour")
                width = body.get("width")
                target = body.get("target", "new_page")
                res = self.server.bridge.glass_control(
                    action=action,
                    colour=colour,
                    width=width,
                    target=target,
                )
                self._json(200, res)
            else:
                self._json(404, {"ok": False, "error": f"Endpoint not found: {path}"})
        except ApiError as exc:
            self._json(exc.status, {"ok": False, "error": exc.message, **exc.details})
        except BoardConflictError as exc:
            self._json(409, {"ok": False, "error": str(exc)})
        except BoardValidationError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:
            self._json(500, {"ok": False, "error": f"Internal server error: {exc}"})


class TeacherDeckHTTPServer(ThreadingHTTPServer):
    """Threaded HTTP server holding the Teacher Deck token and bridge."""

    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        bridge: TeacherDeckBridge,
        token: str,
    ) -> None:
        self.bridge = bridge
        self.token = token
        super().__init__(server_address, TeacherDeckRequestHandler)


class TeacherDeckServer:
    """Manages the background execution and lifecycle of the Teacher Deck service."""

    def __init__(
        self,
        bridge: TeacherDeckBridge,
        token: str,
        host: str = "127.0.0.1",
        port: int = 8790,
    ) -> None:
        if not token or not token.strip():
            raise ValueError("TEACHER_DECK_TOKEN must be a non-empty string.")
        self.bridge = bridge
        self.token = token.strip()
        self.host = host
        self.port = port
        self._server: TeacherDeckHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def server_port(self) -> int:
        if self._server is not None:
            return self._server.server_address[1]
        return self.port

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.server_port}"

    def start(self) -> None:
        if self._server is not None:
            return
        self._server = TeacherDeckHTTPServer((self.host, self.port), self.bridge, self.token)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="TeacherDeckServerThread",
        )
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None

    def __enter__(self) -> TeacherDeckServer:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()
