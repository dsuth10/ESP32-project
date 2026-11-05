"""Unit and integration tests for Teacher Deck models, staging tray, and HTTP API."""
from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import threading
import time
from typing import Any
import urllib.error
import urllib.request
import uuid

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from board_library import BoardResourceLibrary
from board_model import BoardModel, new_object, new_page
from board_session import BoardSession
from media_store import MediaStore
from monitor_shortcut import (
    APP_BOARD,
    APP_CHROME,
    APP_ONENOTE,
    APP_WORD,
    FakeBoardPupilTarget,
    MonitorShortcutController,
    active_profile,
)
from teacher_deck_models import (
    StagedImageItem,
    StagingTray,
    validate_control_action,
    validate_display_target,
    validate_present_target,
    validate_sha256,
    validate_uuid,
)
from teacher_deck_server import (
    ApiError,
    TeacherDeckBridge,
    TeacherDeckServer,
    make_thumbnail_png,
)
from window_monitor_manager import (
    AppWindow,
    FakeWindowMonitorBackend,
    MonitorInfo,
    Rect,
)

TEST_TOKEN = "teacher-deck-secret-test-token-2026"


def create_png_bytes(color: str = "#2563eb", width: int = 600, height: int = 400) -> bytes:
    """Generate in-memory PNG bytes."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, "PNG")
    return buf.getvalue()


def setup_deck_fixtures(tmp_path: Path):
    """Set up BoardSession, MediaStore, BoardResourceLibrary, and MonitorShortcutController."""
    store = MediaStore(tmp_path / "media")
    session = BoardSession(
        BoardModel(),
        image_resolver=lambda ref: store.blob_path(ref["sha256"]).read_bytes(),
    )
    library = BoardResourceLibrary(tmp_path / "library")

    primary = MonitorInfo(
        handle=1,
        friendly_name="Primary laptop display",
        device_name=r"\\.\DISPLAY1",
        device_path=r"\\?\DISPLAY#PRI",
        edid_manufacturer="PRM",
        edid_product="0001",
        bounds=Rect(0, 0, 1920, 1080),
        work_area=Rect(0, 0, 1920, 1080),
        dpi=96,
        is_primary=True,
    )
    classroom = MonitorInfo(
        handle=2,
        friendly_name="Classroom Promethean Panel",
        device_name=r"\\.\DISPLAY2",
        device_path=r"\\?\DISPLAY#SEC",
        edid_manufacturer="PRM",
        edid_product="0002",
        bounds=Rect(1920, 0, 3840, 1080),
        work_area=Rect(1920, 0, 3840, 1080),
        dpi=96,
        is_primary=False,
    )

    # Add mock open windows for classroom apps
    windows = [
        AppWindow(
            hwnd=101,
            pid=501,
            title="Class Notebook - OneNote",
            executable="ONENOTE.EXE",
            bounds=Rect(100, 100, 900, 700),
        ),
        AppWindow(
            hwnd=102,
            pid=502,
            title="Lesson Plan - Word",
            executable="WINWORD.EXE",
            bounds=Rect(100, 100, 900, 700),
        ),
        AppWindow(
            hwnd=103,
            pid=503,
            title="Google Chrome - Science Simulation",
            executable="chrome.exe",
            bounds=Rect(100, 100, 900, 700),
        ),
    ]

    backend = FakeWindowMonitorBackend([primary, classroom], windows)

    board_target = FakeBoardPupilTarget()
    ctl = MonitorShortcutController(
        backend=backend,
        root=tmp_path / "shortcuts",
        wait_timeout_s=0.1,
        board_target=board_target,
    )
    settings = ctl.load()
    profile = active_profile(settings)
    profile["classroom_display"] = classroom.identity_record()
    ctl.save(settings)

    tray = StagingTray(storage_path=tmp_path / "staging.json")
    bridge = TeacherDeckBridge(
        session=session,
        library=library,
        lesson_media=store,
        shortcut_controller=ctl,
        staging_tray=tray,
    )

    return session, store, library, ctl, tray, bridge


def make_request(
    base_url: str,
    path: str,
    method: str = "GET",
    body: dict[str, Any] | bytes | None = None,
    token: str | None = TEST_TOKEN,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any] | bytes]:
    """Helper to execute HTTP requests against the test server."""
    url = f"{base_url}{path}"
    req_headers = {"User-Agent": "TestClient/1.0"}
    if token is not None:
        req_headers["Authorization"] = f"Bearer {token}"
    if headers:
        req_headers.update(headers)

    req_data: bytes | None = None
    if body is not None:
        if isinstance(body, bytes):
            req_data = body
        else:
            req_data = json.dumps(body).encode("utf-8")
            req_headers.setdefault("Content-Type", "application/json")

    request = urllib.request.Request(url, data=req_data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=3.0) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()
            if "application/json" in content_type:
                return resp.status, json.loads(raw.decode("utf-8"))
            return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw.decode("utf-8"))
        except Exception:
            return exc.code, raw


# =========================================================================
# Model and Validation Unit Tests
# =========================================================================


def test_validation_helpers():
    """Verify validation functions enforce schemas and reject invalid inputs."""
    valid_u = str(uuid.uuid4())
    assert validate_uuid(valid_u) == valid_u
    with pytest.raises(ValueError):
        validate_uuid("invalid-uuid")

    valid_hex = "a" * 64
    assert validate_sha256(valid_hex) == valid_hex
    with pytest.raises(ValueError):
        validate_sha256("short-hex")
    with pytest.raises(ValueError):
        validate_sha256("z" * 64)

    for action in ["freeze", "resume", "prev_page", "next_page", "new_page", "undo", "redo"]:
        assert validate_control_action(action) == action
    with pytest.raises(ValueError):
        validate_control_action("explode")

    for target in ["current_page", "new_page"]:
        assert validate_present_target(target) == target
    with pytest.raises(ValueError):
        validate_present_target("random_page")

    for disp in ["board", "onenote", "word", "chrome"]:
        assert validate_display_target(disp) == disp
    with pytest.raises(ValueError):
        validate_display_target("notepad")


def test_staged_image_item_dataclass():
    """Verify StagedImageItem validates fields and generates serialisable dictionary."""
    vid = str(uuid.uuid4())
    aid = str(uuid.uuid4())
    stage_id = str(uuid.uuid4())
    sha = "b" * 64
    item = StagedImageItem(
        stage_id=stage_id,
        series_id="series-42",
        asset_id=aid,
        version_id=vid,
        sha256=sha,
        title="Plant cell diagram",
        width=800,
        height=600,
        origin="generated",
        review_state="draft",
        credit="Generated via local teacher brief",
    )
    d = item.as_dict()
    assert d["stage_id"] == stage_id
    assert d["series_id"] == "series-42"
    assert d["version_id"] == vid
    assert d["thumb_url"] == f"/api/v1/thumb/{vid}"
    assert d["origin"] == "generated"
    assert d["review_state"] == "draft"

    # Roundtrip from_dict
    restored = StagedImageItem.from_dict(d)
    assert restored.version_id == item.version_id
    assert restored.sha256 == item.sha256


def test_staging_tray_operations(tmp_path):
    """Test StagingTray deduplication, series grouping, persistence and bounds."""
    storage_file = tmp_path / "tray.json"
    tray = StagingTray(max_items=3, storage_path=storage_file)

    vid1, vid2, vid3, vid4 = (str(uuid.uuid4()) for _ in range(4))
    item1 = StagedImageItem(
        stage_id=str(uuid.uuid4()),
        series_id="batch-1",
        asset_id=str(uuid.uuid4()),
        version_id=vid1,
        sha256="1" * 64,
        title="Diagram 1",
        width=400,
        height=300,
        origin="generated",
        review_state="draft",
    )
    item2 = StagedImageItem(
        stage_id=str(uuid.uuid4()),
        series_id="batch-1",
        asset_id=str(uuid.uuid4()),
        version_id=vid2,
        sha256="2" * 64,
        title="Diagram 2",
        width=400,
        height=300,
        origin="generated",
        review_state="draft",
    )
    item3 = StagedImageItem(
        stage_id=str(uuid.uuid4()),
        series_id="batch-2",
        asset_id=str(uuid.uuid4()),
        version_id=vid3,
        sha256="3" * 64,
        title="Diagram 3",
        width=400,
        height=300,
        origin="library",
        review_state="approved",
    )

    tray.stage_series([item1, item2], series_id="batch-1")
    assert len(tray.list_items()) == 2
    assert len(tray.list_items(series_id="batch-1")) == 2

    # Deduplication test: updating item1 with approved status replaces it in place
    updated_item1 = StagedImageItem(
        stage_id=item1.stage_id,
        series_id="batch-1",
        asset_id=item1.asset_id,
        version_id=vid1,
        sha256=item1.sha256,
        title="Diagram 1 (Approved)",
        width=400,
        height=300,
        origin="generated",
        review_state="approved",
    )
    tray.stage_item(updated_item1)
    assert len(tray.list_items()) == 2
    assert tray.get_version(vid1).review_state == "approved"

    # Adding items up to and exceeding max_items bounds the tray
    tray.stage_item(item3)
    assert len(tray.list_items()) == 3

    item4 = StagedImageItem(
        stage_id=str(uuid.uuid4()),
        series_id="batch-3",
        asset_id=str(uuid.uuid4()),
        version_id=vid4,
        sha256="4" * 64,
        title="Diagram 4",
        width=400,
        height=300,
        origin="library",
        review_state="approved",
    )
    tray.stage_item(item4)
    assert len(tray.list_items()) == 3  # bounded to max_items=3
    assert tray.get_version(vid4) is not None

    # Verify JSON persistence
    reloaded_tray = StagingTray(max_items=3, storage_path=storage_file)
    assert len(reloaded_tray.list_items()) == 3

    # Removal and clear
    assert reloaded_tray.remove_version(vid4) is True
    assert reloaded_tray.remove_version(vid4) is False
    assert len(reloaded_tray.list_items()) == 2
    reloaded_tray.clear()
    assert len(reloaded_tray.list_items()) == 0


# =========================================================================
# HTTP Integration Tests
# =========================================================================


def test_bearer_token_authentication(tmp_path):
    """Verify bearer token verification, missing token rejection, and constant-time check."""
    _, _, _, _, _, bridge = setup_deck_fixtures(tmp_path)
    with TeacherDeckServer(bridge, token=TEST_TOKEN, host="127.0.0.1", port=0) as server:
        # 1. Missing header
        status, body = make_request(server.base_url, "/api/v1/status", token=None)
        assert status == 401
        assert body["ok"] is False

        # 2. Invalid token
        status, body = make_request(server.base_url, "/api/v1/status", token="wrong-token")
        assert status == 401
        assert body["ok"] is False

        # 3. Valid token
        status, body = make_request(server.base_url, "/api/v1/status", token=TEST_TOKEN)
        assert status == 200
        assert body["ok"] is True

        # 4. Health endpoint is public without token
        status, body = make_request(server.base_url, "/health", token=None)
        assert status == 200
        assert body["ok"] is True


def test_status_endpoint_reflects_live_board_and_display(tmp_path):
    """GET /api/v1/status reflects live BoardSession pages, revision, and freeze state."""
    session, _, _, _, _, bridge = setup_deck_fixtures(tmp_path)
    with TeacherDeckServer(bridge, token=TEST_TOKEN, host="127.0.0.1", port=0) as server:
        status, body = make_request(server.base_url, "/api/v1/status")
        assert status == 200
        assert body["ok"] is True
        assert body["page_count"] == 1
        assert body["page_index"] == 0
        assert body["frozen"] is False
        assert body["revision"] == 0
        assert body["classroom_display"]["configured"] is True

        # Mutate board session (add page) and verify status updates
        view = session.teacher_view()
        p2 = new_page("Page 2")
        session.teacher_apply(
            [{"op": "add_page", "page": p2}],
            expected_revision=view["revision"],
            expected_token=view["token"],
        )
        session.teacher_navigate(p2["id"], expected_token=session.teacher_view()["token"])

        status, body = make_request(server.base_url, "/api/v1/status")
        assert body["page_count"] == 2
        assert body["page_index"] == 1
        assert body["revision"] == 1


def test_staging_series_and_thumbnail_generation(tmp_path):
    """Test staging a series of candidate images and downloading downscaled thumbnails."""
    session, store, library, _, tray, bridge = setup_deck_fixtures(tmp_path)

    # Import 3 candidate images into MediaStore
    img1 = store.import_bytes(create_png_bytes("#e11d48", 1200, 900), title="Mitochondria A", origin="generated")
    img2 = store.import_bytes(create_png_bytes("#10b981", 1024, 768), title="Mitochondria B", origin="generated")
    img3 = store.import_bytes(create_png_bytes("#3b82f6", 800, 600), title="Mitochondria C", origin="generated")

    with TeacherDeckServer(bridge, token=TEST_TOKEN, host="127.0.0.1", port=0) as server:
        # Stage them via POST /api/v1/board/stage
        stage_payload = {
            "version_ids": [img1["version_id"], img2["version_id"], img3["version_id"]],
            "series_id": "biology-series-1",
        }
        status, body = make_request(server.base_url, "/api/v1/board/stage", method="POST", body=stage_payload)
        assert status == 200
        assert body["ok"] is True
        assert body["series_id"] == "biology-series-1"
        assert len(body["items"]) == 3

        # Verify GET /api/v1/staged filters by series
        status, staged_res = make_request(server.base_url, "/api/v1/staged?series_id=biology-series-1")
        assert status == 200
        assert len(staged_res["items"]) == 3

        # Verify GET /api/v1/thumb/<version_id> returns valid downscaled PNG <= 320x240
        for item in staged_res["items"]:
            vid = item["version_id"]
            thumb_status, thumb_data = make_request(server.base_url, f"/api/v1/thumb/{vid}")
            assert thumb_status == 200
            assert isinstance(thumb_data, bytes)
            # Inspect dimensions using PIL
            with Image.open(io.BytesIO(thumb_data)) as thumb_img:
                assert thumb_img.format == "PNG"
                assert thumb_img.width <= 320
                assert thumb_img.height <= 240


def test_present_image_preserves_existing_objects_approves_draft_and_undoes(tmp_path):
    """POST /api/v1/board/present-image on current_page adds image in clear space preserving existing work."""
    session, store, library, _, tray, bridge = setup_deck_fixtures(tmp_path)

    # 1. Populate current page with an existing text note
    view = session.teacher_view()
    existing_note = new_object(
        "text",
        text="Do not cover this essential teacher prompt!",
        x=80,
        y=80,
        width=500,
        height=100,
    )
    session.teacher_apply(
        [{"op": "add_object", "page_id": view["page_id"], "object": existing_note}],
        expected_revision=view["revision"],
        expected_token=view["token"],
    )
    view_with_note = session.teacher_view()
    assert len(view_with_note["document"]["pages"][0]["objects"]) == 1

    # 2. Stage a draft generated image
    raw_png = create_png_bytes("#f59e0b", 640, 480)
    img = store.import_bytes(raw_png, title="Digestive System", origin="generated")
    staged_item = StagedImageItem(
        stage_id=str(uuid.uuid4()),
        series_id="science-series",
        asset_id=img["asset_id"],
        version_id=img["version_id"],
        sha256=img["sha256"],
        title="Digestive System",
        width=640,
        height=480,
        origin="generated",
        review_state="draft",
        credit="Generated by Classroom Agent — CC BY 4.0",
    )
    tray.stage_item(staged_item)

    with TeacherDeckServer(bridge, token=TEST_TOKEN, host="127.0.0.1", port=0) as server:
        # 3. Present on current_page
        payload = {
            "version_id": img["version_id"],
            "target": "current_page",
            "expected_revision": view_with_note["revision"],
        }
        status, body = make_request(server.base_url, "/api/v1/board/present-image", method="POST", body=payload)
        assert status == 200
        assert body["ok"] is True
        assert body["approved_version_id"] == img["version_id"]
        assert tray.get_version(img["version_id"]).review_state == "approved"

        # 4. Verify existing object is preserved and placed image does not overlap
        page = session.teacher_view()["document"]["pages"][0]
        assert len(page["objects"]) == 3  # note + image + credit text
        assert any(o["id"] == existing_note["id"] and o["text"] == existing_note["text"] for o in page["objects"])

        placed_image = next(o for o in page["objects"] if o["type"] == "image")
        assert placed_image["image_ref"]["sha256"] == img["sha256"]

        # Check clear space non-overlap: placed image must not overlap existing_note bounds
        # existing note bounds: x in [80, 580], y in [80, 180]
        note_r = Rect(80, 80, 580, 180)
        img_r = Rect(
            placed_image["x"],
            placed_image["y"],
            placed_image["x"] + placed_image["width"],
            placed_image["y"] + placed_image["height"],
        )
        assert not (
            img_r.left < note_r.right
            and img_r.right > note_r.left
            and img_r.top < note_r.bottom
            and img_r.bottom > note_r.top
        ), "Placed image must not overlap existing teacher note"

        # 5. Undo via POST /api/v1/board/control cleanly removes placed image & credit
        status, undo_body = make_request(
            server.base_url,
            "/api/v1/board/control",
            method="POST",
            body={"action": "undo"},
        )
        assert status == 200
        assert undo_body["ok"] is True
        undone_page = session.teacher_view()["document"]["pages"][0]
        assert len(undone_page["objects"]) == 1
        assert undone_page["objects"][0]["id"] == existing_note["id"]


def test_full_page_conflict_and_new_page_presentation(tmp_path):
    """Full page returns 409 Conflict without deleting objects; new_page succeeds."""
    session, store, library, _, tray, bridge = setup_deck_fixtures(tmp_path)

    # Fill the entire canvas of page 1 with a giant background rectangle
    view = session.teacher_view()
    full_cover = new_object(
        "shape",
        shape="rectangle",
        x=0,
        y=0,
        width=1600,
        height=900,
        fill="#1e293b",
    )
    session.teacher_apply(
        [{"op": "add_object", "page_id": view["page_id"], "object": full_cover}],
        expected_revision=view["revision"],
        expected_token=view["token"],
    )

    img = store.import_bytes(create_png_bytes("#06b6d4", 800, 600), title="Glacier", origin="import")
    tray.stage_item(
        StagedImageItem(
            stage_id=str(uuid.uuid4()),
            series_id="geography",
            asset_id=img["asset_id"],
            version_id=img["version_id"],
            sha256=img["sha256"],
            title="Glacier",
            width=800,
            height=600,
            origin="library",
            review_state="approved",
        )
    )

    with TeacherDeckServer(bridge, token=TEST_TOKEN, host="127.0.0.1", port=0) as server:
        # Placing on current_page must return 409 Conflict
        status, body = make_request(
            server.base_url,
            "/api/v1/board/present-image",
            method="POST",
            body={"version_id": img["version_id"], "target": "current_page"},
        )
        assert status == 409
        assert body["ok"] is False
        assert "Not enough clear space" in body["error"]

        # Confirm nothing was removed or moved on the full page
        p1 = session.teacher_view()["document"]["pages"][0]
        assert len(p1["objects"]) == 1
        assert p1["objects"][0]["id"] == full_cover["id"]

        # Placing with target="new_page" creates a fresh page and succeeds
        status, body = make_request(
            server.base_url,
            "/api/v1/board/present-image",
            method="POST",
            body={"version_id": img["version_id"], "target": "new_page"},
        )
        assert status == 200
        assert body["ok"] is True
        assert session.teacher_view()["page_id"] != p1["id"]

        # Verify page 2 has the image
        p2 = session.teacher_view()["document"]["pages"][1]
        assert any(o["type"] == "image" for o in p2["objects"])

        # Single undo removes both the new page and the placed image atomically
        status, undo_body = make_request(
            server.base_url,
            "/api/v1/board/control",
            method="POST",
            body={"action": "undo"},
        )
        assert status == 200
        assert len(session.teacher_view()["document"]["pages"]) == 1


def test_freeze_resume_and_board_navigation_controls(tmp_path):
    """POST /api/v1/board/control tests freeze (pupil view stays pinned), resume, navigation, undo/redo."""
    session, store, library, _, tray, bridge = setup_deck_fixtures(tmp_path)

    img = store.import_bytes(create_png_bytes("#8b5cf6", 400, 400), title="Atom Model", origin="import")
    tray.stage_item(
        StagedImageItem(
            stage_id=str(uuid.uuid4()),
            series_id="physics",
            asset_id=img["asset_id"],
            version_id=img["version_id"],
            sha256=img["sha256"],
            title="Atom Model",
            width=400,
            height=400,
            origin="library",
            review_state="approved",
        )
    )

    with TeacherDeckServer(bridge, token=TEST_TOKEN, host="127.0.0.1", port=0) as server:
        # 1. Freeze session
        status, body = make_request(server.base_url, "/api/v1/board/control", method="POST", body={"action": "freeze"})
        assert status == 200
        assert body["status"]["frozen"] is True
        pupil_before = session.pupil_view()
        assert pupil_before["frozen"] is True

        # 2. Present image while frozen
        make_request(
            server.base_url,
            "/api/v1/board/present-image",
            method="POST",
            body={"version_id": img["version_id"], "target": "current_page"},
        )

        # Pupil view must remain frozen on the previous state without the placed image
        pupil_during = session.pupil_view()
        assert pupil_during["revision"] == pupil_before["revision"]
        assert len(pupil_during["document"]["pages"][0]["objects"]) == 0

        # Teacher view has the new image
        teacher_view = session.teacher_view()
        assert len(teacher_view["document"]["pages"][0]["objects"]) == 1

        # 3. Resume session
        status, body = make_request(server.base_url, "/api/v1/board/control", method="POST", body={"action": "resume"})
        assert status == 200
        assert body["status"]["frozen"] is False
        pupil_after = session.pupil_view()
        assert pupil_after["frozen"] is False
        assert len(pupil_after["document"]["pages"][0]["objects"]) == 1
        assert pupil_after["revision"] == session.teacher_view()["revision"]

        # 4. New page, Prev page, Next page controls
        make_request(server.base_url, "/api/v1/board/control", method="POST", body={"action": "new_page"})
        assert session.teacher_view()["page_id"] == session.teacher_view()["document"]["pages"][1]["id"]

        make_request(server.base_url, "/api/v1/board/control", method="POST", body={"action": "prev_page"})
        assert session.teacher_view()["page_id"] == session.teacher_view()["document"]["pages"][0]["id"]

        make_request(server.base_url, "/api/v1/board/control", method="POST", body={"action": "next_page"})
        assert session.teacher_view()["page_id"] == session.teacher_view()["document"]["pages"][1]["id"]

        # 5. Undo / Redo
        rev_before_undo = session.teacher_view()["revision"]
        make_request(server.base_url, "/api/v1/board/control", method="POST", body={"action": "undo"})
        assert session.teacher_view()["revision"] > rev_before_undo  # revision advances on undo

        rev_before_redo = session.teacher_view()["revision"]
        make_request(server.base_url, "/api/v1/board/control", method="POST", body={"action": "redo"})
        assert session.teacher_view()["revision"] > rev_before_redo


def test_classroom_display_switching_without_paste_permission(tmp_path):
    """POST /api/v1/display/switch brings board/apps to student display without paste permissions."""
    session, store, library, ctl, tray, bridge = setup_deck_fixtures(tmp_path)

    with TeacherDeckServer(bridge, token=TEST_TOKEN, host="127.0.0.1", port=0) as server:
        for app_target in ["board", "onenote", "word", "chrome"]:
            status, body = make_request(
                server.base_url,
                "/api/v1/display/switch",
                method="POST",
                body={"target": app_target},
            )
            assert status == 200
            assert body["ok"] is True
            receipt = body["receipt"]
            assert receipt["kind"] == "ok"
            assert receipt["app_id"] == (APP_BOARD if app_target == "board" else app_target)
            assert receipt["granted_paste_permission"] is False
            assert receipt["paste_ready_target"] is False


def test_strict_json_and_payload_size_guards(tmp_path):
    """Verify server rejects duplicate JSON keys, NaN constants, and oversized request bodies."""
    _, _, _, _, _, bridge = setup_deck_fixtures(tmp_path)
    with TeacherDeckServer(bridge, token=TEST_TOKEN, host="127.0.0.1", port=0) as server:
        # Duplicate keys in JSON payload
        dup_json = b'{"action": "freeze", "action": "resume"}'
        status, body = make_request(
            server.base_url,
            "/api/v1/board/control",
            method="POST",
            body=dup_json,
            headers={"Content-Type": "application/json"},
        )
        assert status == 400
        assert "Duplicate key" in body["error"]

        # NaN / Infinity rejection
        nan_json = b'{"action": "freeze", "extra": NaN}'
        status, body = make_request(
            server.base_url,
            "/api/v1/board/control",
            method="POST",
            body=nan_json,
            headers={"Content-Type": "application/json"},
        )
        assert status == 400

        # Oversized body (>64 KiB)
        huge_body = b"x" * (65 * 1024)
        status, body = make_request(
            server.base_url,
            "/api/v1/board/control",
            method="POST",
            body=huge_body,
            headers={"Content-Type": "application/json"},
        )
        assert status == 413


def make_request_qt_safe(app, base_url: str, path: str, **kwargs) -> tuple[int, dict[str, Any]]:
    """Execute HTTP request in worker thread while pumping Qt event loop on main thread."""
    result: dict[str, Any] = {}

    def _worker():
        try:
            result["res"] = make_request(base_url, path, **kwargs)
        except Exception as exc:
            result["error"] = exc

    t = threading.Thread(target=_worker)
    t.start()
    while t.is_alive():
        app.processEvents()
        time.sleep(0.01)
    t.join()
    if "error" in result:
        raise result["error"]
    return result["res"]


def test_board_candidate_teacher_deck_live_refresh_and_session_swap(tmp_path, monkeypatch):
    """Verify BoardCandidate main-thread dispatcher, live canvas refresh, and session swap."""
    from PySide6.QtWidgets import QApplication
    import board_candidate
    from board_candidate import BoardCandidate, demo_model, image_resolver
    from board_store import BoardStore
    from media_store import MediaStore

    monkeypatch.setattr(board_candidate, "CANDIDATE_ROOT", tmp_path)
    app = QApplication.instance() or QApplication([])

    lesson_dir = tmp_path / "lesson_a"
    lesson_dir.mkdir(parents=True, exist_ok=True)
    media = MediaStore(lesson_dir / "media")
    store = BoardStore(lesson_dir)
    resolver = image_resolver(media)
    session = BoardSession(demo_model(media), store=store, image_resolver=resolver)
    candidate = BoardCandidate(session, store=store, resolver=resolver)

    try:
        # Import test image
        png_bytes = create_png_bytes("#10b981", 600, 400)
        v_rec = media.import_bytes(png_bytes, "Live Refresh Test", origin="import")
        vid = v_rec["version_id"]

        # Start teacher deck on random port
        server = candidate.start_teacher_deck(port=0, token=TEST_TOKEN)
        assert candidate.teacher_deck_server is not None
        assert candidate.teacher_deck_bridge is not None
        base_url = server.base_url

        # Stage image in candidate staging tray
        candidate.teacher_deck_bridge.stage_images(version_ids=[vid])

        rev_before = candidate.session.teacher_view()["revision"]

        # Call present-image over HTTP
        status, body = make_request_qt_safe(
            app,
            base_url,
            "/api/v1/board/present-image",
            method="POST",
            body={"version_id": vid, "target": "current_page"},
        )
        assert status == 200
        assert body["ok"] is True

        # Verify session revision increased and canvas views were refreshed
        teacher_view = candidate.session.teacher_view()
        assert teacher_view["revision"] > rev_before
        curr_page = next(p for p in teacher_view["document"]["pages"] if p["id"] == teacher_view["page_id"])
        image_objs = [o for o in curr_page["objects"] if o.get("type") == "image" or o.get("kind") == "image"]
        assert len(image_objs) > 0

        # Verify teacher and pupil canvases rendered with matching revision
        assert candidate.teacher_canvas.view is not None
        assert candidate.pupil_canvas.view is not None

        # Test session swap via reopen
        candidate.autosave()
        old_session = candidate.session
        candidate.reopen()
        assert candidate.session is not old_session
        assert candidate.teacher_deck_bridge.session is candidate.session

    finally:
        candidate.finish_close()
        assert candidate.teacher_deck_server is None
        assert candidate.teacher_deck_bridge is None


def test_agent_panel_search_and_preparer_auto_stage_to_teacher_deck(tmp_path):
    """Verify AgentPanel search and BoardResourcePreparer auto-stage candidates to StagingTray."""
    from PySide6.QtWidgets import QApplication
    from board_agent_ui import AgentPanel
    from board_candidate import BoardCandidate, demo_model, image_resolver
    from board_runtime import BoardResourcePreparer
    from board_store import BoardStore
    from media_store import MediaStore

    app = QApplication.instance() or QApplication([])

    lesson_dir = tmp_path / "lesson_b"
    lesson_dir.mkdir(parents=True, exist_ok=True)
    media = MediaStore(lesson_dir / "media")
    store = BoardStore(lesson_dir)
    resolver = image_resolver(media)
    session = BoardSession(demo_model(media), store=store, image_resolver=resolver)
    candidate = BoardCandidate(session, store=store, resolver=resolver)

    try:
        candidate.start_teacher_deck(port=0, token=TEST_TOKEN)
        tray = candidate.staging_tray
        assert tray is not None
        assert len(tray.list_items()) == 0

        # Create AgentPanel
        shared_root = tmp_path / "shared-library"
        panel = AgentPanel(candidate, config={"LOCAL_ONLY": True}, resource_root=shared_root)
        candidate.agent_panel = panel

        # Add image to panel's library
        png_data = create_png_bytes("#3b82f6", 800, 600)
        v1 = panel.library.media.import_bytes(png_data, "Blue Ocean", origin="import")
        r1 = panel.library._index(v1, panel.library.media.root, approved=True)

        png_data2 = create_png_bytes("#ef4444", 800, 600)
        v2 = panel.library.media.import_bytes(png_data2, "Red Sunset", origin="import")
        r2 = panel.library._index(v2, panel.library.media.root, approved=True)

        # 1. Search in AgentPanel -> auto-stages matches into tray
        panel.query.setText("Blue")
        panel.search()
        staged_items = tray.list_items()
        assert len(staged_items) >= 1
        assert any(item["version_id"] == v1["version_id"] for item in staged_items)

        # 2. Stage selected button in AgentPanel
        panel.query.setText("Sunset")
        panel.search()
        panel.stage_selected_to_deck()
        staged_sunset = tray.list_items()
        assert any(item["version_id"] == v2["version_id"] for item in staged_sunset)

        # 3. BoardResourcePreparer auto-stage on multiple matches
        preparer = BoardResourcePreparer(
            panel.library,
            media,
            config={"LOCAL_ONLY": True},
            staging_tray=tray,
        )
        candidates = panel.library.search("")
        staged_by_prep = preparer._stage_candidates(candidates, series_title="Preparer Candidates")
        assert len(staged_by_prep) >= 2
        for prep_item in staged_by_prep:
            assert tray.get_version(prep_item.version_id) is not None

    finally:
        candidate.finish_close()


def test_joshuaos_podium_catalogue_open_url_and_glass_ink_endpoints(tmp_path):
    """Verify GET /api/v1/catalogue, POST /api/v1/display/open-url, POST /api/v1/glass/control, and showrunner cues."""
    session, store, library, ctl, tray, bridge = setup_deck_fixtures(tmp_path)

    with TeacherDeckServer(bridge, token=TEST_TOKEN, host="127.0.0.1", port=0) as server:
        # 1. GET /api/v1/status includes active_display_target, glass_ink, and showrunner_cues
        status_code, status_body = make_request(server.base_url, "/api/v1/status")
        assert status_code == 200
        assert status_body["ok"] is True
        assert "active_display_target" in status_body
        assert "glass_ink" in status_body
        assert status_body["glass_ink"]["mode"] == "off"
        assert isinstance(status_body["showrunner_cues"], list)
        assert len(status_body["showrunner_cues"]) == 3

        # 2. GET /api/v1/catalogue returns curated MrSutherland.net entries
        cat_code, cat_body = make_request(server.base_url, "/api/v1/catalogue")
        assert cat_code == 200
        assert cat_body["ok"] is True
        items = cat_body["items"]
        assert len(items) >= 5
        assert any("mrsutherland.net" in item["url"] for item in items)

        # 3. POST /api/v1/display/open-url launches allowlisted MrSutherland.net URL and rejects others
        open_code, open_body = make_request(
            server.base_url,
            "/api/v1/display/open-url",
            method="POST",
            body={"url": "https://mrsutherland.net/science/water-cycle/", "title": "Water Cycle Sim"},
        )
        assert open_code == 200
        assert open_body["ok"] is True
        assert open_body["receipt"]["app_id"] == APP_CHROME
        assert open_body["receipt"]["granted_paste_permission"] is False

        bad_code, bad_body = make_request(
            server.base_url,
            "/api/v1/display/open-url",
            method="POST",
            body={"url": "https://evil.example.com/phish"},
        )
        assert bad_code == 400
        assert bad_body["ok"] is False

        # 4. POST /api/v1/glass/control toggles draw, interact (click-through), colour, and snap_to_board
        draw_code, draw_body = make_request(
            server.base_url,
            "/api/v1/glass/control",
            method="POST",
            body={"action": "draw", "colour": "blue", "width": 8.0},
        )
        assert draw_code == 200
        assert draw_body["glass_ink"]["mode"] == "draw"
        assert draw_body["glass_ink"]["active"] is True
        assert draw_body["glass_ink"]["click_through"] is False

        interact_code, interact_body = make_request(
            server.base_url,
            "/api/v1/glass/control",
            method="POST",
            body={"action": "interact"},
        )
        assert interact_code == 200
        assert interact_body["glass_ink"]["mode"] == "interact"
        assert interact_body["glass_ink"]["click_through"] is True

        # Add a stroke and snap to board
        bridge.glass_controller.add_stroke([[100, 100], [300, 250], [500, 180]], colour="red", width=6.0)
        snap_code, snap_body = make_request(
            server.base_url,
            "/api/v1/glass/control",
            method="POST",
            body={"action": "snap_to_board", "target": "new_page"},
        )
        assert snap_code == 200
        assert snap_body["ok"] is True
        assert snap_body["version_id"]
        assert snap_body["glass_ink"]["mode"] == "off"
        assert snap_body["glass_ink"]["stroke_count"] == 0
        assert len(session.teacher_view()["document"]["pages"]) == 2

