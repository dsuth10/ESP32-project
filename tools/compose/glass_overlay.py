"""Unified Glass Ink Screen Annotation Overlay and Controller.

Australian English conventions.
Allows the teacher to draw over any application on the classroom display
(OneNote, MrSutherland.net interactive web apps in Chrome, Teaching Board,
or 3D apps), toggle between Draw Mode ('draw'), Interact / Click-Through Mode
('interact'), and Eraser Mode ('eraser'), change pen colour and width,
undo/redo/clear strokes, and composite screen + ink annotations into a PNG
for Snap & Keep to Board.
"""
from __future__ import annotations

import copy
import ctypes
from dataclasses import dataclass
import io
import math
import os
import re
import threading
from typing import Any
import uuid

ALLOWED_GLASS_MODES = frozenset({"off", "draw", "interact", "eraser"})
ALLOWED_GLASS_COLOURS: dict[str, str] = {
    "red": "#ef4444",
    "blue": "#38bdf8",
    "yellow": "#facc15",
    "green": "#22c55e",
    "white": "#f8fafc",
    "black": "#0f172a",
}

HEX_COLOUR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
MIN_PEN_WIDTH = 2.0
MAX_PEN_WIDTH = 32.0
DEFAULT_BOUNDS = (0, 0, 1920, 1080)

# Win32 extended window style constants for click-through transparency
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020


def normalise_glass_colour(colour: str) -> str:
    """Resolve a named colour or validate a #RRGGBB hex string."""
    if not isinstance(colour, str) or not colour.strip():
        raise ValueError("Glass ink colour must be a non-empty string.")
    cleaned = colour.strip().lower()
    if cleaned in ALLOWED_GLASS_COLOURS:
        return ALLOWED_GLASS_COLOURS[cleaned]
    if HEX_COLOUR_RE.fullmatch(cleaned):
        return cleaned
    allowed_names = ", ".join(sorted(ALLOWED_GLASS_COLOURS))
    raise ValueError(
        f"Unsupported glass ink colour '{colour}'. Use a #RRGGBB hex value or one of: {allowed_names}"
    )


def clamp_pen_width(width: float | int) -> float:
    """Clamp pen width to [MIN_PEN_WIDTH, MAX_PEN_WIDTH]."""
    if isinstance(width, bool) or not isinstance(width, (int, float)) or not math.isfinite(width):
        raise ValueError("Pen width must be a finite number.")
    return float(max(MIN_PEN_WIDTH, min(MAX_PEN_WIDTH, float(width))))


def apply_win32_click_through(hwnd: int, click_through: bool) -> bool:
    """Toggle Win32 WS_EX_TRANSPARENT | WS_EX_LAYERED on a native window handle.

    Safely returns False in non-Windows environments, offscreen test sessions,
    or if the window handle is not a live Win32 window.
    """
    if os.name != "nt" or not isinstance(hwnd, int) or hwnd <= 0:
        return False
    if os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen":
        return False
    try:
        user32 = getattr(ctypes, "windll", None)
        if user32 is None or not hasattr(user32, "user32"):
            return False
        u32 = user32.user32
        get_long = getattr(u32, "GetWindowLongPtrW", None) or getattr(u32, "GetWindowLongW", None)
        set_long = getattr(u32, "SetWindowLongPtrW", None) or getattr(u32, "SetWindowLongW", None)
        if get_long is None or set_long is None:
            return False
        current_style = int(get_long(hwnd, GWL_EXSTYLE))
        if click_through:
            new_style = current_style | WS_EX_LAYERED | WS_EX_TRANSPARENT
        else:
            new_style = (current_style | WS_EX_LAYERED) & ~WS_EX_TRANSPARENT
        set_long(hwnd, GWL_EXSTYLE, new_style)
        return True
    except Exception:
        return False


def _point_segment_distance(
    px: float, py: float, x1: float, y1: float, x2: float, y2: float
) -> float:
    """Return the Euclidean distance from (px, py) to segment (x1, y1)-(x2, y2)."""
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0.0 and dy == 0.0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


@dataclass
class GlassStroke:
    """A single freehand ink stroke drawn on the Glass Ink overlay."""

    stroke_id: str
    points: list[list[float]]
    colour: str = "#ef4444"
    width: float = 6.0
    is_highlighter: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.stroke_id, str) or not self.stroke_id.strip():
            self.stroke_id = str(uuid.uuid4())
        else:
            self.stroke_id = self.stroke_id.strip()

        if not isinstance(self.points, list) or len(self.points) == 0:
            raise ValueError("GlassStroke requires at least one [x, y] point.")
        cleaned_points: list[list[float]] = []
        for pt in self.points:
            if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                raise ValueError("Each stroke point must be a [x, y] coordinate pair.")
            x_val, y_val = float(pt[0]), float(pt[1])
            if not (math.isfinite(x_val) and math.isfinite(y_val)):
                raise ValueError("Stroke coordinates must be finite numbers.")
            cleaned_points.append([x_val, y_val])
        self.points = cleaned_points
        self.colour = normalise_glass_colour(self.colour)
        self.width = clamp_pen_width(self.width)
        self.is_highlighter = bool(self.is_highlighter)

    def as_dict(self) -> dict[str, Any]:
        """Serialise the stroke to a plain dictionary."""
        return {
            "stroke_id": self.stroke_id,
            "points": [list(pt) for pt in self.points],
            "colour": self.colour,
            "width": self.width,
            "is_highlighter": self.is_highlighter,
        }


class GlassInkController:
    """Thread-safe controller for the Unified Glass Ink Screen Annotation Overlay."""

    def __init__(
        self,
        bounds: tuple[int, int, int, int] = DEFAULT_BOUNDS,
        overlay: GlassInkOverlay | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self.mode: str = "off"
        self.active: bool = False
        self.click_through: bool = False
        self.colour: str = "#ef4444"
        self.pen_width: float = 6.0
        self.strokes: list[GlassStroke] = []
        self.undo_stack: list[list[GlassStroke]] = []
        self.redo_stack: list[list[GlassStroke]] = []
        self.bounds: tuple[int, int, int, int] = (
            int(bounds[0]),
            int(bounds[1]),
            int(bounds[2]),
            int(bounds[3]),
        )
        self._overlay: GlassInkOverlay | None = overlay

    def attach_overlay(self, overlay: GlassInkOverlay | None) -> None:
        """Attach or detach a live PySide6 GlassInkOverlay window."""
        with self._lock:
            self._overlay = overlay
            if overlay is not None:
                overlay.sync_from_controller()

    def get_state(self) -> dict[str, Any]:
        """Return a JSON-serialisable snapshot of the Glass Ink state."""
        with self._lock:
            return {
                "active": self.active,
                "mode": self.mode,
                "click_through": self.click_through,
                "colour": self.colour,
                "pen_width": self.pen_width,
                "stroke_count": len(self.strokes),
                "bounds": list(self.bounds),
            }

    def set_bounds(self, bounds: tuple[int, int, int, int] | list[int]) -> dict[str, Any]:
        """Update the target monitor bounds (x, y, width, height) for the overlay."""
        if not isinstance(bounds, (tuple, list)) or len(bounds) != 4:
            raise ValueError("bounds must be a 4-tuple (x, y, width, height).")
        x, y, w, h = (int(bounds[0]), int(bounds[1]), int(bounds[2]), int(bounds[3]))
        if w <= 0 or h <= 0:
            raise ValueError("bounds width and height must be positive integers.")
        with self._lock:
            self.bounds = (x, y, w, h)
            overlay = self._overlay
            state = self.get_state()
        if overlay is not None:
            overlay.sync_from_controller()
        return state

    def set_mode(self, mode: str) -> dict[str, Any]:
        """Set the overlay mode ('off', 'draw', 'interact', 'eraser')."""
        if not isinstance(mode, str):
            raise ValueError("Glass mode must be a string.")
        cleaned = mode.strip().lower()
        if cleaned not in ALLOWED_GLASS_MODES:
            allowed = ", ".join(sorted(ALLOWED_GLASS_MODES))
            raise ValueError(f"Unsupported glass mode '{mode}'. Allowed modes: {allowed}")
        with self._lock:
            self.mode = cleaned
            self.active = cleaned != "off"
            self.click_through = cleaned == "interact"
            overlay = self._overlay
            state = self.get_state()
        if overlay is not None:
            overlay.sync_from_controller()
        return state

    def set_pen(
        self,
        colour: str | None = None,
        width: float | int | None = None,
    ) -> dict[str, Any]:
        """Update the active pen colour and/or stroke width."""
        with self._lock:
            if colour is not None:
                self.colour = normalise_glass_colour(colour)
            if width is not None:
                self.pen_width = clamp_pen_width(width)
            overlay = self._overlay
            state = self.get_state()
        if overlay is not None:
            overlay.update()
        return state

    def add_stroke(
        self,
        points: list[list[float]],
        colour: str | None = None,
        width: float | int | None = None,
        *,
        is_highlighter: bool = False,
        stroke_id: str | None = None,
    ) -> GlassStroke:
        """Record a completed stroke on the overlay and push an undo snapshot."""
        with self._lock:
            effective_colour = (
                normalise_glass_colour(colour) if colour is not None else self.colour
            )
            effective_width = (
                clamp_pen_width(width) if width is not None else self.pen_width
            )
            stroke = GlassStroke(
                stroke_id=stroke_id or str(uuid.uuid4()),
                points=points,
                colour=effective_colour,
                width=effective_width,
                is_highlighter=is_highlighter,
            )
            self.undo_stack.append(copy.deepcopy(self.strokes))
            self.redo_stack.clear()
            self.strokes.append(stroke)
            overlay = self._overlay
        if overlay is not None:
            overlay.update()
        return stroke

    def erase_at(self, x: float, y: float, radius: float = 20.0) -> int:
        """Erase any strokes passing within radius pixels of (x, y)."""
        px, py = float(x), float(y)
        r = max(1.0, float(radius))
        with self._lock:
            if not self.strokes:
                return 0
            kept: list[GlassStroke] = []
            removed = 0
            for stroke in self.strokes:
                hit = False
                pts = stroke.points
                if len(pts) == 1:
                    if math.hypot(px - pts[0][0], py - pts[0][1]) <= r + stroke.width * 0.5:
                        hit = True
                else:
                    for idx in range(len(pts) - 1):
                        dist = _point_segment_distance(
                            px,
                            py,
                            pts[idx][0],
                            pts[idx][1],
                            pts[idx + 1][0],
                            pts[idx + 1][1],
                        )
                        if dist <= r + stroke.width * 0.5:
                            hit = True
                            break
                if hit:
                    removed += 1
                else:
                    kept.append(stroke)
            if removed > 0:
                self.undo_stack.append(copy.deepcopy(self.strokes))
                self.redo_stack.clear()
                self.strokes = kept
            overlay = self._overlay
        if removed > 0 and overlay is not None:
            overlay.update()
        return removed

    def undo(self) -> bool:
        """Undo the most recent stroke change."""
        with self._lock:
            if not self.undo_stack:
                return False
            self.redo_stack.append(copy.deepcopy(self.strokes))
            self.strokes = self.undo_stack.pop()
            overlay = self._overlay
        if overlay is not None:
            overlay.update()
        return True

    def redo(self) -> bool:
        """Redo the most recently undone stroke change."""
        with self._lock:
            if not self.redo_stack:
                return False
            self.undo_stack.append(copy.deepcopy(self.strokes))
            self.strokes = self.redo_stack.pop()
            overlay = self._overlay
        if overlay is not None:
            overlay.update()
        return True

    def clear(self) -> int:
        """Clear all strokes and return the number of strokes cleared."""
        with self._lock:
            count = len(self.strokes)
            if count > 0:
                self.undo_stack.append(copy.deepcopy(self.strokes))
                self.redo_stack.clear()
                self.strokes.clear()
            overlay = self._overlay
        if count > 0 and overlay is not None:
            overlay.update()
        return count

    def render_to_png(
        self,
        background_png: bytes | None = None,
        width: int = 1600,
        height: int = 900,
    ) -> bytes:
        """Composite background PNG (or clean classroom canvas) + all GlassStroke paths."""
        target_w = max(64, int(width))
        target_h = max(64, int(height))
        with self._lock:
            strokes_snapshot = copy.deepcopy(self.strokes)
            bounds_w = max(1, int(self.bounds[2]))
            bounds_h = max(1, int(self.bounds[3]))

        scale_x = target_w / float(bounds_w) if bounds_w != target_w else 1.0
        scale_y = target_h / float(bounds_h) if bounds_h != target_h else 1.0

        # Attempt high-quality Qt rendering first
        try:
            from PySide6.QtCore import QBuffer, QIODevice, QPointF, Qt
            from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen

            canvas = QImage(target_w, target_h, QImage.Format.Format_ARGB32)
            canvas.fill(QColor("#0f172a"))

            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

            if background_png:
                bg_img = QImage.fromData(background_png)
                if not bg_img.isNull():
                    scaled_bg = bg_img.scaled(
                        target_w,
                        target_h,
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    painter.drawImage(0, 0, scaled_bg)

            _paint_strokes_qt(
                painter,
                strokes_snapshot,
                scale_x=scale_x,
                scale_y=scale_y,
            )
            painter.end()

            buf = QBuffer()
            buf.open(QIODevice.OpenModeFlag.WriteOnly)
            canvas.save(buf, "PNG")
            png_bytes = bytes(buf.data())
            buf.close()
            if png_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
                return png_bytes
        except Exception:
            pass

        # Fallback to PIL ImageDraw if Qt is unavailable
        from PIL import Image, ImageDraw

        if background_png:
            with Image.open(io.BytesIO(background_png)) as bg:
                pil_canvas = bg.convert("RGBA").resize((target_w, target_h))
        else:
            pil_canvas = Image.new("RGBA", (target_w, target_h), (15, 23, 42, 255))

        draw = ImageDraw.Draw(pil_canvas, "RGBA")
        for stroke in strokes_snapshot:
            scaled_pts = [
                (pt[0] * scale_x, pt[1] * scale_y) for pt in stroke.points
            ]
            stroke_w = max(1, int(round(stroke.width * ((scale_x + scale_y) * 0.5))))
            col = stroke.colour
            if len(scaled_pts) == 1:
                x0, y0 = scaled_pts[0]
                r = stroke_w * 0.5
                draw.ellipse((x0 - r, y0 - r, x0 + r, y0 + r), fill=col)
            else:
                draw.line(scaled_pts, fill=col, width=stroke_w, joint="curve")

        out = io.BytesIO()
        pil_canvas.save(out, format="PNG")
        return out.getvalue()


def _paint_strokes_qt(
    painter: Any,
    strokes: list[GlassStroke],
    *,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
) -> None:
    """Render a list of GlassStroke objects onto an active QPainter."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QPainterPath, QPen

    avg_scale = (scale_x + scale_y) * 0.5
    for stroke in strokes:
        qcol = QColor(stroke.colour)
        if stroke.is_highlighter:
            qcol.setAlpha(140)
        pen = QPen(
            qcol,
            max(1.0, stroke.width * avg_scale),
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
        painter.setPen(pen)
        pts = stroke.points
        if len(pts) == 1:
            p0 = QPointF(pts[0][0] * scale_x, pts[0][1] * scale_y)
            painter.drawPoint(p0)
        else:
            path = QPainterPath()
            path.moveTo(pts[0][0] * scale_x, pts[0][1] * scale_y)
            for pt in pts[1:]:
                path.lineTo(pt[0] * scale_x, pt[1] * scale_y)
            painter.drawPath(path)


try:
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QPainter, QPen
    from PySide6.QtWidgets import QWidget

    class GlassInkOverlay(QWidget):
        """Frameless, translucent, stays-on-top screen annotation overlay."""

        def __init__(
            self,
            controller: GlassInkController | None = None,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self.controller = controller or GlassInkController()
            self._active_points: list[list[float]] = []
            self._is_drawing: bool = False

            self.setWindowTitle("JoshuaOS Glass Ink Overlay")
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.setMouseTracking(True)

            self.controller.attach_overlay(self)
            self.sync_from_controller()

        def sync_from_controller(self) -> None:
            """Synchronise window geometry, visibility, and click-through flags."""
            state = self.controller.get_state()
            bounds = state["bounds"]
            self.setGeometry(bounds[0], bounds[1], bounds[2], bounds[3])

            mode = state["mode"]
            click_through = bool(state["click_through"])
            self.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                click_through,
            )

            if mode == "off":
                self.hide()
            else:
                self.show()
                try:
                    hwnd = int(self.winId())
                except Exception:
                    hwnd = 0
                apply_win32_click_through(hwnd, click_through)
            self.update()

        def mousePressEvent(self, event: Any) -> None:  # noqa: N802
            if event.button() != Qt.MouseButton.LeftButton:
                super().mousePressEvent(event)
                return
            pos = event.position() if hasattr(event, "position") else event.pos()
            x, y = float(pos.x()), float(pos.y())
            mode = self.controller.mode
            if mode == "draw":
                self._is_drawing = True
                self._active_points = [[x, y]]
                self.update()
                event.accept()
            elif mode == "eraser":
                self._is_drawing = True
                self.controller.erase_at(x, y)
                event.accept()
            else:
                super().mousePressEvent(event)

        def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802
            if not self._is_drawing:
                super().mouseMoveEvent(event)
                return
            pos = event.position() if hasattr(event, "position") else event.pos()
            x, y = float(pos.x()), float(pos.y())
            mode = self.controller.mode
            if mode == "draw":
                self._active_points.append([x, y])
                self.update()
                event.accept()
            elif mode == "eraser":
                self.controller.erase_at(x, y)
                event.accept()
            else:
                super().mouseMoveEvent(event)

        def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802
            if event.button() == Qt.MouseButton.LeftButton and self._is_drawing:
                pos = event.position() if hasattr(event, "position") else event.pos()
                x, y = float(pos.x()), float(pos.y())
                mode = self.controller.mode
                self._is_drawing = False
                if mode == "draw" and self._active_points:
                    if len(self._active_points) == 1 or self._active_points[-1] != [x, y]:
                        self._active_points.append([x, y])
                    pts = list(self._active_points)
                    self._active_points.clear()
                    self.controller.add_stroke(pts)
                self.update()
                event.accept()
                return
            super().mouseReleaseEvent(event)

        def paintEvent(self, _event: Any) -> None:  # noqa: N802
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            mode = self.controller.mode
            if mode != "off":
                # Draw subtle glowing border indicator
                rect = QRectF(2.0, 2.0, max(1.0, self.width() - 4.0), max(1.0, self.height() - 4.0))
                if mode == "draw":
                    border_pen = QPen(QColor("#ef4444"), 3.0, Qt.PenStyle.SolidLine)
                elif mode == "interact":
                    border_pen = QPen(QColor("#38bdf8"), 2.5, Qt.PenStyle.DashLine)
                else:
                    border_pen = QPen(QColor("#facc15"), 3.0, Qt.PenStyle.DotLine)
                painter.setPen(border_pen)
                painter.drawRect(rect)

            with self.controller._lock:
                strokes = list(self.controller.strokes)
            _paint_strokes_qt(painter, strokes, scale_x=1.0, scale_y=1.0)

            if self._is_drawing and self._active_points:
                preview = GlassStroke(
                    stroke_id="preview",
                    points=self._active_points,
                    colour=self.controller.colour,
                    width=self.controller.pen_width,
                )
                _paint_strokes_qt(painter, [preview], scale_x=1.0, scale_y=1.0)

            painter.end()

        def simulate_stroke(
            self,
            points: list[list[float]],
            colour: str | None = None,
            width: float | None = None,
        ) -> GlassStroke:
            """Programmatically draw a stroke through the overlay."""
            stroke = self.controller.add_stroke(points, colour=colour, width=width)
            self.update()
            return stroke

except Exception:  # pragma: no cover

    class GlassInkOverlay:  # type: ignore[no-redef]
        """Headless fallback overlay when PySide6 is not installed in the active Python environment."""

        def __init__(
            self,
            controller: GlassInkController | None = None,
            parent: Any = None,
        ) -> None:
            self.controller = controller or GlassInkController()
            self.parent = parent
            self._visible: bool = False
            self._geometry: tuple[int, int, int, int] = DEFAULT_BOUNDS
            self._transparent_for_mouse: bool = False
            self._active_points: list[list[float]] = []
            self._is_drawing: bool = False
            self.controller.attach_overlay(self)
            self.sync_from_controller()

        def sync_from_controller(self) -> None:
            state = self.controller.get_state()
            b = state["bounds"]
            self._geometry = (int(b[0]), int(b[1]), int(b[2]), int(b[3]))
            self._transparent_for_mouse = bool(state["click_through"])
            self._visible = state["mode"] != "off"

        def isVisible(self) -> bool:  # noqa: N802
            return self._visible

        def show(self) -> None:
            self._visible = True

        def hide(self) -> None:
            self._visible = False

        def update(self) -> None:
            pass

        def repaint(self) -> None:
            pass

        def simulate_stroke(
            self,
            points: list[list[float]],
            colour: str | None = None,
            width: float | None = None,
        ) -> GlassStroke:
            """Programmatically draw a stroke through the overlay."""
            return self.controller.add_stroke(points, colour=colour, width=width)

