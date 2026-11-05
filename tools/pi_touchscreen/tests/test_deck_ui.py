"""Unit and integration tests for the JoshuaOS Podium & Teacher Deck client and UI.

Verifies TeacherDeckClient API calls, multi-host Tailscale switching, thumbnail caching,
and TeacherDeckWindow touch operations (staging grid, clear-space image placement,
409 conflict handling, freeze/resume toggles, page navigation, display switching,
MrSutherland.net Launchpad tab, Glass Ink overlay controls, Hermes Showrunner
predictive cues, and offline resilience).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any
import uuid

import pytest
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "compose"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "compose" / "tests"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from board_model import new_object
from teacher_deck_models import StagedImageItem
from teacher_deck_server import TeacherDeckServer
from test_teacher_deck import TEST_TOKEN, create_png_bytes, setup_deck_fixtures

from tools.pi_touchscreen.deck_client import (
    DeckClientError,
    InProcessDeckClient,
    TeacherDeckClient,
    load_deck_config,
)
from tools.pi_touchscreen.deck_ui import TeacherDeckWindow


@pytest.fixture(scope="session")
def qapp():
    """Ensure a singleton QApplication exists for offscreen Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--platform", "offscreen"])
    return app


def test_deck_client_methods_and_auth_error(tmp_path):
    """TeacherDeckClient interacts correctly with server and caches thumbnails."""
    session, store, library, ctl, tray, bridge = setup_deck_fixtures(tmp_path)

    # Import an image into media store and stage it
    png_bytes = create_png_bytes(color="#2563eb", width=400, height=300)
    imported = store.import_bytes(png_bytes, title="Evaporation Cycle", origin="import")
    item = StagedImageItem(
        stage_id=str(uuid.uuid4()),
        series_id="test-series-1",
        asset_id=imported["asset_id"],
        version_id=imported["version_id"],
        sha256=imported["sha256"],
        title="Evaporation Cycle",
        width=400,
        height=300,
        origin="library",
        review_state="approved",
    )
    tray.stage_item(item)

    with TeacherDeckServer(bridge, token=TEST_TOKEN, host="127.0.0.1", port=0) as server:
        client = TeacherDeckClient(server.base_url, token=TEST_TOKEN, timeout=3.0)

        # Health probe
        h = client.health()
        assert h["ok"] is True

        # Status probe
        status = client.get_status()
        assert status["ok"] is True
        assert status["page_count"] == 1
        assert status["frozen"] is False

        # Staged images list
        staged = client.list_staged()
        assert len(staged) == 1
        assert staged[0]["version_id"] == imported["version_id"]

        # Search library (empty or returns list)
        lib = client.search_library(query="", limit=10)
        assert isinstance(lib, list)

        # Thumbnail retrieval and caching
        assert imported["version_id"] not in client._thumb_cache
        thumb = client.get_thumbnail(imported["version_id"])
        assert isinstance(thumb, bytes) and len(thumb) > 0
        assert imported["version_id"] in client._thumb_cache

        # Second call returns from in-memory cache
        cached_thumb = client.get_thumbnail(imported["version_id"])
        assert cached_thumb == thumb

        # Bad token authentication rejection
        bad_client = TeacherDeckClient(server.base_url, token="invalid-token", timeout=3.0)
        with pytest.raises(DeckClientError) as exc_info:
            bad_client.get_status()
        assert exc_info.value.status == 401


def test_deck_window_displays_staged_series_and_presents_on_current_page(tmp_path, qapp):
    """TeacherDeckWindow displays staged series, previews selection, and presents on current page."""
    session, store, library, ctl, tray, bridge = setup_deck_fixtures(tmp_path)

    # Place an existing text note on Page 1 (must be preserved!)
    view = session.teacher_view()
    p1_id = view["document"]["pages"][0]["id"]
    existing_note = new_object(
        "text",
        text="Essential Teacher Instructions: Do not erase!",
        x=50,
        y=50,
        width=400,
        height=100,
        colour="#111827",
    )
    session.teacher_apply(
        [{"op": "add_object", "page_id": p1_id, "object": existing_note}],
        expected_revision=view["revision"],
        expected_token=view["token"],
    )

    # Stage 3 candidate images (candidate #2 is a newly generated draft image)
    b1 = create_png_bytes(color="#10b981", width=300, height=200)
    imp1 = store.import_bytes(b1, title="Candidate 1 - Approved", origin="import")
    cand1 = StagedImageItem(
        stage_id=str(uuid.uuid4()),
        series_id="series-weather",
        asset_id=imp1["asset_id"],
        version_id=imp1["version_id"],
        sha256=imp1["sha256"],
        title="Candidate 1 - Approved",
        width=300,
        height=200,
        origin="library",
        review_state="approved",
    )

    b2 = create_png_bytes(color="#f59e0b", width=400, height=300)
    imp2 = store.import_bytes(b2, title="Candidate 2 - Generated Draft", origin="generated")
    cand2 = StagedImageItem(
        stage_id=str(uuid.uuid4()),
        series_id="series-weather",
        asset_id=imp2["asset_id"],
        version_id=imp2["version_id"],
        sha256=imp2["sha256"],
        title="Candidate 2 - Generated Draft",
        width=400,
        height=300,
        origin="generated",
        review_state="draft",
        credit="Prompt: Weather precipitation model",
    )

    b3 = create_png_bytes(color="#6366f1", width=350, height=250)
    imp3 = store.import_bytes(b3, title="Candidate 3 - Approved", origin="import")
    cand3 = StagedImageItem(
        stage_id=str(uuid.uuid4()),
        series_id="series-weather",
        asset_id=imp3["asset_id"],
        version_id=imp3["version_id"],
        sha256=imp3["sha256"],
        title="Candidate 3 - Approved",
        width=350,
        height=250,
        origin="library",
        review_state="approved",
    )

    # Stage so cand2 is the second candidate (index 1) in list
    tray.stage_item(cand3)
    tray.stage_item(cand2)
    tray.stage_item(cand1)

    with TeacherDeckServer(bridge, token=TEST_TOKEN, host="127.0.0.1", port=0) as server:
        client = TeacherDeckClient(server.base_url, token=TEST_TOKEN, timeout=3.0)
        window = TeacherDeckWindow(client, poll_ms=0)
        try:
            window.refresh_state()

            # Verifies 3 staged images appear in image_list with non-null icons
            assert window.image_list.count() == 3
            for i in range(3):
                assert not window.image_list.item(i).icon().isNull()

            # Select candidate #2 (index 1)
            window.image_list.setCurrentRow(1)
            assert window.current_selected_image is not None
            assert window.current_selected_image["version_id"] == cand2.version_id
            assert window.present_current_button.isEnabled()
            assert "Candidate 2 - Generated Draft" in window.preview_title_label.text()

            # Click present on current page
            window.present_current_button.click()

            # Verify image added to Page 1 in clear space while preserving existing note
            p1_objs = session.teacher_view()["document"]["pages"][0]["objects"]
            assert len(p1_objs) >= 2
            note_present = any(obj["id"] == existing_note["id"] for obj in p1_objs)
            assert note_present, "Existing text note must be preserved!"

            img_obj = next(
                (obj for obj in p1_objs if obj.get("type") == "image" and obj.get("image_ref", {}).get("version_id") == cand2.version_id),
                None,
            )
            assert img_obj is not None, "Candidate 2 image must be placed on Page 1!"

            # Verify draft generated image is marked approved
            staged_cand2 = tray.get_version(cand2.version_id)
            assert staged_cand2 is not None
            assert staged_cand2.review_state == "approved"

            # Clicking undo removes the placed image and leaves existing note intact
            window.control_buttons["undo"].click()
            p1_objs_after_undo = session.teacher_view()["document"]["pages"][0]["objects"]
            assert len(p1_objs_after_undo) == 1
            assert p1_objs_after_undo[0]["id"] == existing_note["id"]

        finally:
            window.close()


def test_deck_window_handles_full_page_409_and_presents_on_new_page(tmp_path, qapp):
    """Full page returns HTTP 409 conflict; UI warns teacher; presenting on new page succeeds."""
    session, store, library, ctl, tray, bridge = setup_deck_fixtures(tmp_path)

    # Completely fill Page 1 with a full-size rectangle so no free clear space remains
    view = session.teacher_view()
    p1_id = view["document"]["pages"][0]["id"]
    full_cover = new_object(
        "shape",
        shape="rectangle",
        x=0,
        y=0,
        width=1600,
        height=900,
    )
    session.teacher_apply(
        [{"op": "add_object", "page_id": p1_id, "object": full_cover}],
        expected_revision=view["revision"],
        expected_token=view["token"],
    )

    # Stage an image
    b = create_png_bytes(color="#3b82f6", width=400, height=300)
    imp = store.import_bytes(b, title="Full Page Test Image", origin="import")
    item = StagedImageItem(
        stage_id=str(uuid.uuid4()),
        series_id="test-series-full",
        asset_id=imp["asset_id"],
        version_id=imp["version_id"],
        sha256=imp["sha256"],
        title="Full Page Test Image",
        width=400,
        height=300,
        origin="library",
        review_state="approved",
    )
    tray.stage_item(item)

    with TeacherDeckServer(bridge, token=TEST_TOKEN, host="127.0.0.1", port=0) as server:
        client = TeacherDeckClient(server.base_url, token=TEST_TOKEN, timeout=3.0)
        window = TeacherDeckWindow(client, poll_ms=0)
        try:
            window.refresh_state()
            window.image_list.setCurrentRow(0)
            assert window.present_current_button.isEnabled()

            # Attempt to place on current page -> must trigger 409 warning without crashing
            window.present_current_button.click()

            feedback = window.feedback_label.text().lower()
            assert "full" in feedback or "clear space" in feedback
            assert "put on new page" in feedback

            # Ensure Page 1 content was preserved untouched
            p1_objs = session.teacher_view()["document"]["pages"][0]["objects"]
            assert len(p1_objs) == 1
            assert p1_objs[0]["id"] == full_cover["id"]

            # Tap Put on New Page -> succeeds and creates Page 2
            window.present_new_page_button.click()

            view = session.teacher_view()
            assert len(view["document"]["pages"]) == 2
            p2 = view["document"]["pages"][1]
            assert view["page_id"] == p2["id"]
            assert any(obj.get("type") == "image" for obj in p2["objects"])

        finally:
            window.close()


def test_deck_window_freeze_resume_navigation_and_display_switch(tmp_path, qapp):
    """TeacherDeckWindow controls freeze/resume, page navigation, and student display switching."""
    session, store, library, ctl, tray, bridge = setup_deck_fixtures(tmp_path)

    with TeacherDeckServer(bridge, token=TEST_TOKEN, host="127.0.0.1", port=0) as server:
        client = TeacherDeckClient(server.base_url, token=TEST_TOKEN, timeout=3.0)
        window = TeacherDeckWindow(client, poll_ms=0)
        try:
            window.refresh_state()

            # Freeze / Resume toggle
            assert session.pupil_view()["frozen"] is False
            window.freeze_button.click()
            assert session.pupil_view()["frozen"] is True
            assert "FROZEN" in window.freeze_button.text()

            window.freeze_button.click()
            assert session.pupil_view()["frozen"] is False
            assert "LIVE" in window.freeze_button.text()

            # Page navigation controls
            assert len(session.teacher_view()["document"]["pages"]) == 1
            window.control_buttons["new_page"].click()
            pages = session.teacher_view()["document"]["pages"]
            assert len(pages) == 2
            assert session.teacher_view()["page_id"] == pages[1]["id"]

            window.control_buttons["prev_page"].click()
            assert session.teacher_view()["page_id"] == pages[0]["id"]

            window.control_buttons["next_page"].click()
            assert session.teacher_view()["page_id"] == pages[1]["id"]

            # Classroom Display Switcher buttons
            for target in ["board", "onenote", "word", "chrome"]:
                btn = window.display_buttons[target]
                btn.click()
                assert target.lower() in window.feedback_label.text().lower()

        finally:
            window.close()


def test_deck_window_offline_resilience(qapp):
    """TeacherDeckWindow gracefully handles offline/unreachable server without crashing."""
    # Point at a closed local port
    offline_client = TeacherDeckClient("http://127.0.0.1:59999", token="dummy-token", timeout=0.2)
    window = TeacherDeckWindow(offline_client, poll_ms=0)
    try:
        window.refresh_state()
        assert window.connected is False
        assert "Waiting for Classroom PC" in window.connection_label.text()
    finally:
        window.close()


def test_multi_host_config_and_host_combo_switching(tmp_path, qapp):
    """JoshuaOS Podium supports multi-host Tailscale config and one-tap host switching."""
    cfg_file = tmp_path / "podium_config.json"
    cfg_data = {
        "active_host_id": "home-pc",
        "hosts": [
            {
                "id": "school-pc",
                "label": "School Classroom PC",
                "url": "http://school-pc.tailnet.ts.net:8790",
                "token": "school-secret",
            },
            {
                "id": "home-pc",
                "label": "Home Desktop PC",
                "url": "http://home-pc.tailnet.ts.net:8790",
                "token": "home-secret",
            },
        ],
        "width": 1920,
        "height": 1080,
        "kiosk": True,
    }
    cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

    cfg = load_deck_config(cfg_file)
    assert cfg["active_host_id"] == "home-pc"
    assert cfg["url"] == "http://home-pc.tailnet.ts.net:8790"
    assert cfg["token"] == "home-secret"
    assert len(cfg["hosts"]) == 2

    client = TeacherDeckClient(
        base_url=cfg["url"],
        token=cfg["token"],
        timeout=0.1,
        hosts=cfg["hosts"],
        active_host_id=cfg["active_host_id"],
    )
    client._thumb_cache["cached-v1"] = b"png-bytes"
    assert client.get_active_host()["id"] == "home-pc"

    window = TeacherDeckWindow(client, poll_ms=0)
    try:
        assert window.host_combo.count() == 2
        assert window.host_combo.currentIndex() == 1

        # Switch to School Classroom PC (index 0) via combo box
        window.host_combo.setCurrentIndex(0)
        assert client.active_host_id == "school-pc"
        assert client.base_url == "http://school-pc.tailnet.ts.net:8790"
        assert client.token == "school-secret"
        assert len(client._thumb_cache) == 0
        assert "School Classroom PC" in window.feedback_label.text()
    finally:
        window.close()


class _FakePodiumBridge:
    """In-process stub bridge exposing JoshuaOS Podium methods for UI testing."""

    def __init__(self) -> None:
        self.launched_urls: list[tuple[str, str]] = []
        self.glass_calls: list[dict[str, Any]] = []
        self.board_actions: list[str] = []
        self.display_targets: list[str] = []
        self.staged_queries: list[str] = []
        self.catalogue: list[dict[str, Any]] = [
            {
                "id": "cat-fractions",
                "title": "MrSutherland.net — Interactive Fractions Lab",
                "category": "Maths",
                "url": "https://mrsutherland.net/fractions",
                "description": "Visual fraction bars and equivalence challenges",
            },
            {
                "id": "cat-forces",
                "title": "MrSutherland.net — Forces & Motion Simulator",
                "category": "Science",
                "url": "https://mrsutherland.net/forces",
                "description": "Newtonian motion interactive sandbox",
            },
        ]
        self.cues: list[dict[str, Any]] = [
            {
                "id": "cue-1",
                "label": "🚀 Launch Fractions Lab",
                "kind": "open_web",
                "payload": {
                    "url": "https://mrsutherland.net/fractions",
                    "title": "Interactive Fractions Lab",
                },
            },
            {
                "id": "cue-2",
                "label": "✏️ Circle Denominator (Red Ink)",
                "kind": "glass_ink",
                "payload": {"action": "draw", "colour": "red"},
            },
            {
                "id": "cue-3",
                "label": "🖼️ Stage Fraction Diagrams",
                "kind": "stage_query",
                "payload": {"query": "equivalent fractions diagram"},
            },
        ]

    def get_status(self) -> dict[str, Any]:
        return {
            "ok": True,
            "title": "Year 7 Fractions",
            "page_id": "p1",
            "page_index": 0,
            "page_count": 1,
            "frozen": False,
            "active_display_target": self.display_targets[-1] if self.display_targets else "board",
            "pages": [{"id": "p1", "title": "Page 1", "object_count": 0}],
            "showrunner_cues": self.cues,
        }

    def list_staged(self, series_id: str | None = None) -> list[dict[str, Any]]:
        return []

    def list_catalogue(self) -> list[dict[str, Any]]:
        return list(self.catalogue)

    def open_web_lesson(self, url: str, title: str = "") -> dict[str, Any]:
        self.launched_urls.append((url, title))
        self.display_targets.append("chrome")
        return {"ok": True, "url": url, "title": title}

    def glass_control(
        self,
        action: str,
        colour: str | None = None,
        width: float | None = None,
        target: str = "new_page",
    ) -> dict[str, Any]:
        call = {"action": action, "colour": colour, "width": width, "target": target}
        self.glass_calls.append(call)
        return {"ok": True, **call}

    def stage_images(
        self,
        query: str | None = None,
        version_ids: list[str] | None = None,
        series_id: str | None = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        if query:
            self.staged_queries.append(query)
        return ("series-1", [])

    def board_control(self, action: str) -> dict[str, Any]:
        self.board_actions.append(action)
        return {"ok": True, "action": action}

    def switch_display(self, target: str) -> dict[str, Any]:
        self.display_targets.append(target)
        return {"ok": True, "target": target}


def test_podium_launchpad_glass_ink_and_showrunner_cues(qapp):
    """JoshuaOS Podium Launchpad, Glass Ink rail, and Hermes Showrunner cues operate end-to-end."""
    bridge = _FakePodiumBridge()
    client = InProcessDeckClient(bridge)
    window = TeacherDeckWindow(client, poll_ms=0)
    try:
        window.refresh_state()

        # 1. Verify MrSutherland.net Launchpad tab populated from bridge catalogue
        assert window.catalogue_list.count() == 2
        window.catalogue_list.setCurrentRow(1)
        assert window.web_url_input.text() == "https://mrsutherland.net/forces"

        window.launch_web_button.click()
        assert bridge.launched_urls[-1] == (
            "https://mrsutherland.net/forces",
            "MrSutherland.net — Forces & Motion Simulator",
        )
        assert window.active_display_target == "chrome"

        # 2. Verify Glass Ink rail buttons and colour swatches
        window.glass_colour_buttons["blue"].click()
        assert window.active_glass_colour == "blue"
        assert bridge.glass_calls[-1]["action"] == "colour"
        assert bridge.glass_calls[-1]["colour"] == "blue"

        window.glass_buttons["draw"].click()
        assert bridge.glass_calls[-1]["action"] == "draw"
        assert bridge.glass_calls[-1]["colour"] == "blue"
        assert "DRAWING ON SCREEN" in window.glass_status_label.text()

        window.glass_buttons["interact"].click()
        assert bridge.glass_calls[-1]["action"] == "interact"
        assert "CLICK-THROUGH" in window.glass_status_label.text()

        window.glass_buttons["clear"].click()
        assert bridge.glass_calls[-1]["action"] == "clear"

        window.glass_buttons["snap_to_board"].click()
        assert bridge.glass_calls[-1]["action"] == "snap_to_board"

        # 3. Verify Hermes Showrunner predictive cues rendered and execute on tap
        assert len(window.cue_buttons) == 3
        assert window.cue_buttons[0].text() == "🚀 Launch Fractions Lab"
        assert window.cue_buttons[1].text() == "✏️ Circle Denominator (Red Ink)"
        assert window.cue_buttons[2].text() == "🖼️ Stage Fraction Diagrams"

        window.cue_buttons[0].click()
        assert bridge.launched_urls[-1] == (
            "https://mrsutherland.net/fractions",
            "Interactive Fractions Lab",
        )

        window.cue_buttons[2].click()
        assert bridge.staged_queries[-1] == "equivalent fractions diagram"
    finally:
        window.close()
