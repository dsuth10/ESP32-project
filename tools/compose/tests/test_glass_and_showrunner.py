"""Unit tests for the Unified Glass Ink Overlay and Lesson Showrunner Engine."""
from __future__ import annotations

import io
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

COMPOSE_DIR = Path(__file__).resolve().parents[1]
if str(COMPOSE_DIR) not in sys.path:
    sys.path.insert(0, str(COMPOSE_DIR))

from PIL import Image
import pytest

from glass_overlay import (
    ALLOWED_GLASS_COLOURS,
    ALLOWED_GLASS_MODES,
    GlassInkController,
    GlassInkOverlay,
    GlassStroke,
    apply_win32_click_through,
    clamp_pen_width,
    normalise_glass_colour,
)
from lesson_showrunner import (
    DEFAULT_MRSUTHERLAND_CATALOGUE,
    VALID_CUE_KINDS,
    LessonShowrunner,
    match_catalogue_item,
)


def _ensure_qapp():
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app
    except ImportError:
        return None


class TestGlassInkController:
    """Tests for GlassStroke and GlassInkController state, strokes, undo/redo, and PNG rendering."""

    def test_initial_state_and_mode_transitions(self) -> None:
        ctrl = GlassInkController(bounds=(0, 0, 1920, 1080))
        state = ctrl.get_state()
        assert state["active"] is False
        assert state["mode"] == "off"
        assert state["click_through"] is False
        assert state["colour"] == "#ef4444"
        assert state["pen_width"] == 6.0
        assert state["stroke_count"] == 0
        assert state["bounds"] == [0, 0, 1920, 1080]

        # Transition: off -> draw
        s_draw = ctrl.set_mode("draw")
        assert s_draw["active"] is True
        assert s_draw["mode"] == "draw"
        assert s_draw["click_through"] is False

        # Transition: draw -> interact (click-through enabled)
        s_interact = ctrl.set_mode("interact")
        assert s_interact["active"] is True
        assert s_interact["mode"] == "interact"
        assert s_interact["click_through"] is True

        # Transition: interact -> eraser
        s_eraser = ctrl.set_mode("eraser")
        assert s_eraser["active"] is True
        assert s_eraser["mode"] == "eraser"
        assert s_eraser["click_through"] is False

        # Transition: eraser -> off
        s_off = ctrl.set_mode("off")
        assert s_off["active"] is False
        assert s_off["mode"] == "off"
        assert s_off["click_through"] is False

        with pytest.raises(ValueError, match="Unsupported glass mode"):
            ctrl.set_mode("invalid_mode")

    def test_pen_colour_and_width_validation(self) -> None:
        ctrl = GlassInkController()
        for name, expected_hex in ALLOWED_GLASS_COLOURS.items():
            st = ctrl.set_pen(colour=name)
            assert st["colour"] == expected_hex

        st_custom = ctrl.set_pen(colour="#12abef", width=14.5)
        assert st_custom["colour"] == "#12abef"
        assert st_custom["pen_width"] == 14.5

        # Width clamping to 2.0..32.0
        assert ctrl.set_pen(width=0.5)["pen_width"] == 2.0
        assert ctrl.set_pen(width=99.0)["pen_width"] == 32.0

        with pytest.raises(ValueError, match="Unsupported glass ink colour"):
            ctrl.set_pen(colour="neon-orange")

        with pytest.raises(ValueError, match="Pen width must be a finite number"):
            ctrl.set_pen(width=float("nan"))

    def test_stroke_addition_undo_redo_erase_and_clear(self) -> None:
        ctrl = GlassInkController()
        ctrl.set_mode("draw")

        s1 = ctrl.add_stroke([[100, 100], [300, 300]], colour="red", width=8.0)
        assert isinstance(s1, GlassStroke)
        assert s1.colour == ALLOWED_GLASS_COLOURS["red"]
        assert s1.width == 8.0
        assert ctrl.get_state()["stroke_count"] == 1

        s2 = ctrl.add_stroke([[400, 100], [400, 500]], colour="blue", width=10.0)
        assert s2.colour == ALLOWED_GLASS_COLOURS["blue"]
        assert ctrl.get_state()["stroke_count"] == 2

        # Undo second stroke
        assert ctrl.undo() is True
        assert ctrl.get_state()["stroke_count"] == 1
        assert ctrl.strokes[0].stroke_id == s1.stroke_id

        # Redo second stroke
        assert ctrl.redo() is True
        assert ctrl.get_state()["stroke_count"] == 2

        # Erase near first stroke midpoint (200, 200)
        erased = ctrl.erase_at(200.0, 200.0, radius=15.0)
        assert erased == 1
        assert ctrl.get_state()["stroke_count"] == 1
        assert ctrl.strokes[0].stroke_id == s2.stroke_id

        # Undo the erase
        assert ctrl.undo() is True
        assert ctrl.get_state()["stroke_count"] == 2

        # Clear all strokes
        cleared = ctrl.clear()
        assert cleared == 2
        assert ctrl.get_state()["stroke_count"] == 0

        # Undo the clear restores both strokes
        assert ctrl.undo() is True
        assert ctrl.get_state()["stroke_count"] == 2

    def test_render_to_png_produces_valid_annotated_png(self) -> None:
        _ensure_qapp()
        ctrl = GlassInkController(bounds=(0, 0, 800, 450))
        blank_png = ctrl.render_to_png(width=800, height=450)
        assert blank_png.startswith(b"\x89PNG\r\n\x1a\n")

        ctrl.add_stroke(
            [[50, 50], [400, 225], [750, 400]],
            colour="yellow",
            width=16.0,
        )
        drawn_png = ctrl.render_to_png(width=800, height=450)
        assert drawn_png.startswith(b"\x89PNG\r\n\x1a\n")
        assert drawn_png != blank_png

        with Image.open(io.BytesIO(drawn_png)) as img:
            assert img.size == (800, 450)
            # Sample pixel at centre (400, 225) where yellow stroke passes
            r, g, b, *_ = img.convert("RGBA").getpixel((400, 225))
            assert r > 200 and g > 150


class TestGlassInkOverlayWidget:
    """Tests for PySide6 GlassInkOverlay under offscreen Qt."""

    def test_overlay_widget_creation_and_mouse_drawing(self) -> None:
        app = _ensure_qapp()
        ctrl = GlassInkController(bounds=(0, 0, 640, 360))
        overlay = GlassInkOverlay(controller=ctrl)

        assert overlay.isVisible() is False

        ctrl.set_mode("draw")
        assert overlay.isVisible() is True

        if app is not None:
            from PySide6.QtCore import QEvent, QPointF, Qt
            from PySide6.QtGui import QMouseEvent

            assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) is False
            press = QMouseEvent(
                QEvent.Type.MouseButtonPress,
                QPointF(80.0, 80.0),
                QPointF(80.0, 80.0),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            move = QMouseEvent(
                QEvent.Type.MouseMove,
                QPointF(240.0, 180.0),
                QPointF(240.0, 180.0),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            release = QMouseEvent(
                QEvent.Type.MouseButtonRelease,
                QPointF(320.0, 220.0),
                QPointF(320.0, 220.0),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            )
            overlay.mousePressEvent(press)
            overlay.mouseMoveEvent(move)
            overlay.mouseReleaseEvent(release)
            overlay.repaint()
        else:
            overlay.simulate_stroke([[80.0, 80.0], [240.0, 180.0], [320.0, 220.0]])

        assert ctrl.get_state()["stroke_count"] == 1
        png_bytes = ctrl.render_to_png(width=640, height=360)
        assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")

        # Switch to interact mode and verify click-through attribute
        ctrl.set_mode("interact")
        if app is not None:
            from PySide6.QtCore import Qt

            assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) is True
        else:
            assert ctrl.get_state()["click_through"] is True

        # Switch to off and verify hidden
        ctrl.set_mode("off")
        assert overlay.isVisible() is False
        assert apply_win32_click_through(0, True) is False


class TestLessonShowrunner:
    """Tests for LessonShowrunner predictive cues and context management."""

    def test_water_cycle_cues_on_board(self) -> None:
        showrunner = LessonShowrunner(
            lesson_title="Year 7 Science: The Water Cycle",
            active_display_target="board",
            staged_count=0,
            glass_mode="off",
        )
        cues = showrunner.compute_predictive_cues()
        assert len(cues) == 3
        for idx, cue in enumerate(cues, start=1):
            assert cue["cue_id"] == f"cue-{idx}"
            assert cue["kind"] in VALID_CUE_KINDS
            assert isinstance(cue["payload"], dict)
            assert cue["label"]
            assert cue["reason"]

        # Cue 1 should launch the matching Water Cycle Sim from MrSutherland.net
        assert cues[0]["kind"] == "open_web"
        assert "water-cycle" in cues[0]["payload"]["url"]
        assert "Water Cycle" in cues[0]["label"]

        # Since active_target == 'board' and staged_count == 0, a stage_query cue should be present
        kinds = [c["kind"] for c in cues]
        assert "stage_query" in kinds
        assert "switch_display" in kinds

    def test_fractions_lesson_and_chrome_target_offers_glass_ink(self) -> None:
        showrunner = LessonShowrunner()
        cues = showrunner.compute_predictive_cues(
            lesson_title="Equivalent Fractions and Decimals",
            active_target="chrome",
            staged_count=2,
            glass_mode="off",
        )
        assert len(cues) == 3
        # Matches Fractions app in catalogue
        assert any(
            c["kind"] == "open_web" and "fractions" in c["payload"]["url"]
            for c in cues
        )
        # Since Chrome is active and glass_mode == 'off', offers Glass Ink annotation
        assert any(
            c["kind"] == "glass_ink" and c["payload"].get("mode") == "draw"
            for c in cues
        )

    def test_glass_ink_active_offers_snap_to_board_and_interact_toggle(self) -> None:
        showrunner = LessonShowrunner()
        cues = showrunner.compute_predictive_cues(
            lesson_title="Forces and Motion",
            active_target="chrome",
            staged_count=1,
            glass_mode="draw",
        )
        assert len(cues) == 3
        assert cues[0]["kind"] == "glass_ink"
        assert cues[0]["payload"].get("action") == "snap_to_board"
        assert "Snap Annotation to Board" in cues[0]["label"]

        assert cues[1]["kind"] == "glass_ink"
        assert cues[1]["payload"].get("mode") == "interact"

    def test_onenote_target_offers_return_to_board_and_highlight(self) -> None:
        showrunner = LessonShowrunner()
        cues = showrunner.compute_predictive_cues(
            lesson_title="Plant and Animal Cells",
            active_target="onenote",
            staged_count=3,
            glass_mode="off",
        )
        assert len(cues) == 3
        assert any(
            c["kind"] == "switch_display" and c["payload"].get("target") == "board"
            for c in cues
        )
        assert any(
            c["kind"] == "glass_ink" and c["payload"].get("mode") == "draw"
            for c in cues
        )

    def test_bounded_event_recording_and_context_snapshot(self) -> None:
        showrunner = LessonShowrunner(max_events=50)
        for i in range(65):
            showrunner.record_event("cue_triggered", {"index": i})

        events = showrunner.get_events()
        assert len(events) == 50
        assert events[0]["details"]["index"] == 15
        assert events[-1]["details"]["index"] == 64

        ctx = showrunner.update_context(
            lesson_title="Solar System Orbits",
            active_display_target="chrome",
            glass_mode="interact",
            staged_count=4,
        )
        assert ctx["lesson_title"] == "Solar System Orbits"
        assert ctx["active_display_target"] == "chrome"
        assert ctx["glass_mode"] == "interact"
        assert ctx["staged_count"] == 4
        assert len(ctx["cues"]) == 3
        assert match_catalogue_item("Solar System Orbits", DEFAULT_MRSUTHERLAND_CATALOGUE) is not None
