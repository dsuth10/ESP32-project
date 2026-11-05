"""Hermes Lesson Showrunner and Predictive Cue Engine.

Australian English conventions.
Manages the active classroom lesson context (lesson title, active display target,
active web URL, freeze state, staged image count, and Glass Ink mode) and computes
3 context-aware Predictive Showrunner Cues for the bottom bar of JoshuaOS Podium.
Optionally coordinates bounded background assistance with Linux Hermes when configured.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
import re
import threading
from typing import Any
import uuid

VALID_CUE_KINDS = frozenset(
    {"open_web", "switch_display", "stage_query", "glass_ink", "board_control"}
)
MAX_SHOWRUNNER_EVENTS = 50

DEFAULT_MRSUTHERLAND_CATALOGUE: list[dict[str, Any]] = [
    {
        "id": "water-cycle-sim",
        "title": "Water Cycle Sim",
        "subject": "Science",
        "url": "https://mrsutherland.net/science/water-cycle/",
        "keywords": ["water", "cycle", "evaporation", "condensation", "precipitation", "weather", "hydrology"],
        "description": "Interactive water cycle and phase-change simulation for classroom projection.",
    },
    {
        "id": "fractions-visualiser",
        "title": "Fraction Wall & Visualiser",
        "subject": "Mathematics",
        "url": "https://mrsutherland.net/maths/fractions/",
        "keywords": ["fraction", "fractions", "numerator", "denominator", "decimal", "ratio", "maths", "math"],
        "description": "Interactive fraction bar wall and equivalent fraction explorer.",
    },
    {
        "id": "forces-motion-lab",
        "title": "Forces & Motion Lab",
        "subject": "Science",
        "url": "https://mrsutherland.net/science/forces-motion/",
        "keywords": ["force", "forces", "motion", "gravity", "friction", "newton", "velocity", "acceleration", "physics"],
        "description": "Interactive force vectors, friction, and Newton's laws simulator.",
    },
    {
        "id": "solar-system-3d",
        "title": "Solar System 3D Orrery",
        "subject": "Science",
        "url": "https://mrsutherland.net/science/solar-system/",
        "keywords": ["solar", "system", "planet", "planets", "orbit", "space", "astronomy", "earth", "moon"],
        "description": "Interactive 3D solar system orbital model with planetary scale comparison.",
    },
    {
        "id": "geometry-angles",
        "title": "Geometry & Protractor Studio",
        "subject": "Mathematics",
        "url": "https://mrsutherland.net/maths/geometry/",
        "keywords": ["geometry", "angle", "angles", "triangle", "polygon", "shape", "shapes", "protractor"],
        "description": "Interactive classroom protractor, polygon builder, and angle theorem explorer.",
    },
    {
        "id": "cells-microscope",
        "title": "Virtual Cell Microscope",
        "subject": "Science",
        "url": "https://mrsutherland.net/science/cells/",
        "keywords": ["cell", "cells", "biology", "microscope", "organelle", "nucleus", "plant", "animal", "mitosis"],
        "description": "Interactive plant and animal cell explorer with virtual microscope magnification.",
    },
    {
        "id": "classroom-timer-groups",
        "title": "Classroom Timer & Group Maker",
        "subject": "Classroom Tools",
        "url": "https://mrsutherland.net/tools/classroom-timer/",
        "keywords": ["timer", "countdown", "group", "groups", "random", "starter", "plenary", "activity"],
        "description": "Big-screen visual countdown timer, noise meter, and random group generator.",
    },
]


def _utc_now() -> str:
    """Return the current UTC timestamp formatted as ISO-8601."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _tokenise(text: str) -> list[str]:
    """Extract lowercase alphanumeric tokens from a string."""
    if not isinstance(text, str):
        return []
    return re.findall(r"[a-z0-9]+", text.lower())


def match_catalogue_item(
    lesson_title: str,
    catalogue: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Find the best-matching MrSutherland.net web app for the given lesson title."""
    items = catalogue if catalogue is not None else DEFAULT_MRSUTHERLAND_CATALOGUE
    if not items or not isinstance(lesson_title, str) or not lesson_title.strip():
        return None

    title_lower = lesson_title.strip().lower()
    title_tokens = set(_tokenise(title_lower))
    if not title_tokens:
        return None

    best_item: dict[str, Any] | None = None
    best_score = 0

    for entry in items:
        if not isinstance(entry, dict) or not entry.get("url") or not entry.get("title"):
            continue
        score = 0
        entry_title = str(entry.get("title", "")).lower()
        entry_subject = str(entry.get("subject", "")).lower()
        raw_keywords = entry.get("keywords") or entry.get("tags") or []
        keywords = [str(k).lower() for k in raw_keywords if k]

        # Exact phrase match in lesson title
        if entry_title and entry_title in title_lower:
            score += 10
        for kw in keywords:
            if len(kw) >= 3 and kw in title_lower:
                score += 5
            if kw in title_tokens:
                score += 6

        entry_tokens = set(_tokenise(entry_title)) | set(_tokenise(entry_subject))
        overlap = title_tokens & entry_tokens
        score += len(overlap) * 3

        if score > best_score:
            best_score = score
            best_item = entry

    return copy.deepcopy(best_item) if best_score > 0 and best_item is not None else None


class LessonShowrunner:
    """Tracks classroom lesson state and generates 3 Predictive Showrunner Cues."""

    def __init__(
        self,
        *,
        active_lesson_id: str = "",
        lesson_title: str = "Untitled lesson",
        active_display_target: str = "board",
        active_web_url: str = "",
        frozen: bool = False,
        staged_count: int = 0,
        glass_mode: str = "off",
        catalogue: list[dict[str, Any]] | None = None,
        hermes_service: Any | None = None,
        max_events: int = MAX_SHOWRUNNER_EVENTS,
    ) -> None:
        self._lock = threading.RLock()
        self.active_lesson_id = str(active_lesson_id or "")
        self.lesson_title = str(lesson_title or "Untitled lesson")
        self.active_display_target = str(active_display_target or "board").strip().lower()
        self.active_web_url = str(active_web_url or "")
        self.frozen = bool(frozen)
        self.staged_count = max(0, int(staged_count))
        self.glass_mode = str(glass_mode or "off").strip().lower()
        self.catalogue: list[dict[str, Any]] = (
            copy.deepcopy(catalogue)
            if catalogue is not None
            else copy.deepcopy(DEFAULT_MRSUTHERLAND_CATALOGUE)
        )
        self.hermes_service = hermes_service
        self.max_events = max(1, int(max_events))
        self._events: list[dict[str, Any]] = []

    def record_event(
        self,
        kind: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record a showrunner event in a bounded activity log (max 50 items)."""
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError("Event kind must be a non-empty string.")
        entry = {
            "event_id": str(uuid.uuid4()),
            "timestamp": _utc_now(),
            "kind": kind.strip(),
            "details": copy.deepcopy(details) if isinstance(details, dict) else {},
        }
        with self._lock:
            self._events.append(entry)
            if len(self._events) > self.max_events:
                self._events = self._events[-self.max_events :]
        return copy.deepcopy(entry)

    def get_events(self) -> list[dict[str, Any]]:
        """Return a copy of the bounded showrunner activity log."""
        with self._lock:
            return copy.deepcopy(self._events)

    def update_context(
        self,
        *,
        active_lesson_id: str | None = None,
        lesson_title: str | None = None,
        active_display_target: str | None = None,
        active_web_url: str | None = None,
        frozen: bool | None = None,
        staged_count: int | None = None,
        glass_mode: str | None = None,
    ) -> dict[str, Any]:
        """Update the active lesson state and return the updated context snapshot."""
        with self._lock:
            if active_lesson_id is not None:
                self.active_lesson_id = str(active_lesson_id)
            if lesson_title is not None:
                self.lesson_title = str(lesson_title).strip() or "Untitled lesson"
            if active_display_target is not None:
                self.active_display_target = str(active_display_target).strip().lower() or "board"
            if active_web_url is not None:
                self.active_web_url = str(active_web_url).strip()
            if frozen is not None:
                self.frozen = bool(frozen)
            if staged_count is not None:
                self.staged_count = max(0, int(staged_count))
            if glass_mode is not None:
                self.glass_mode = str(glass_mode).strip().lower() or "off"
            return self.get_context()

    def compute_predictive_cues(
        self,
        lesson_title: str | None = None,
        active_target: str | None = None,
        staged_count: int | None = None,
        glass_mode: str | None = None,
        catalogue: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Generate 3 context-aware one-tap Predictive Showrunner Cues."""
        with self._lock:
            effective_title = (
                str(lesson_title).strip()
                if lesson_title is not None
                else self.lesson_title
            ) or "Untitled lesson"
            effective_target = (
                str(active_target).strip().lower()
                if active_target is not None
                else self.active_display_target
            ) or "board"
            effective_staged = (
                max(0, int(staged_count))
                if staged_count is not None
                else self.staged_count
            )
            effective_glass = (
                str(glass_mode).strip().lower()
                if glass_mode is not None
                else self.glass_mode
            ) or "off"
            effective_catalogue = (
                catalogue if catalogue is not None else self.catalogue
            )

        candidates: list[dict[str, Any]] = []

        def add_candidate(
            label: str,
            kind: str,
            payload: dict[str, Any],
            reason: str,
        ) -> None:
            if kind not in VALID_CUE_KINDS:
                return
            key = (kind, json.dumps(payload, sort_keys=True))
            for existing in candidates:
                existing_key = (
                    existing["kind"],
                    json.dumps(existing["payload"], sort_keys=True),
                )
                if existing_key == key:
                    return
            candidates.append(
                {
                    "label": label,
                    "kind": kind,
                    "payload": payload,
                    "reason": reason,
                }
            )

        matched_app = match_catalogue_item(effective_title, effective_catalogue)

        # 1. If Glass Ink is currently active (draw, interact, or eraser), prioritise Snap & Mode toggle
        if effective_glass in ("draw", "interact", "eraser"):
            add_candidate(
                label="📸 Snap Annotation to Board",
                kind="glass_ink",
                payload={"action": "snap_to_board", "target": "current_page"},
                reason="Glass Ink is active; capture the annotated screen onto the Teaching Board",
            )
            if effective_glass == "draw":
                add_candidate(
                    label="👆 Interact Behind Ink (Click-Through)",
                    kind="glass_ink",
                    payload={"mode": "interact"},
                    reason="Switch Glass Ink to click-through mode so you can manipulate the app underneath",
                )
            else:
                add_candidate(
                    label="✏️ Resume Glass Ink Drawing",
                    kind="glass_ink",
                    payload={"mode": "draw"},
                    reason="Return from click-through interaction to active Glass Ink drawing",
                )

        # 2. Topic-matched MrSutherland.net simulation cue
        if matched_app is not None:
            add_candidate(
                label=f"🌐 Launch {matched_app['title']}",
                kind="open_web",
                payload={
                    "url": matched_app["url"],
                    "title": matched_app["title"],
                    "id": matched_app.get("id", ""),
                },
                reason=f"Matches current lesson topic '{effective_title}'",
            )

        # 3. Display target specific intelligence
        if effective_target == "chrome" and effective_glass == "off":
            add_candidate(
                label="✏️ Annotate Over Web App (Glass Ink)",
                kind="glass_ink",
                payload={"mode": "draw", "colour": "red"},
                reason="Interactive web app is on screen; enable Glass Ink to circle and annotate key features",
            )

        if effective_target == "onenote" and effective_glass == "off":
            add_candidate(
                label="✏️ Highlight Over OneNote (Glass Ink)",
                kind="glass_ink",
                payload={"mode": "draw", "colour": "yellow"},
                reason="OneNote is on the classroom display; enable Glass Ink for live screen callouts",
            )

        cleaned_topic = (
            effective_title
            if effective_title.lower() not in ("untitled", "untitled lesson", "")
            else "lesson"
        )
        if effective_target == "board" and effective_staged == 0:
            add_candidate(
                label="🖼️ Stage Lesson Diagrams",
                kind="stage_query",
                payload={"query": f"{cleaned_topic} diagram", "count": 3},
                reason=f"Staging tray is empty; pre-stage visual diagrams for '{effective_title}'",
            )

        if effective_target != "onenote":
            add_candidate(
                label="🟣 Switch to OneNote Notes",
                kind="switch_display",
                payload={"target": "onenote"},
                reason="Switch the classroom display to OneNote class notes",
            )
        else:
            add_candidate(
                label="🧑‍🏫 Return to Teaching Board",
                kind="switch_display",
                payload={"target": "board"},
                reason="Switch the classroom display back to the Teaching Board canvas",
            )

        # 4. High-value fallbacks to guarantee 3 distinct cues
        if matched_app is None and effective_catalogue:
            first_app = effective_catalogue[0]
            if isinstance(first_app, dict) and first_app.get("url") and first_app.get("title"):
                add_candidate(
                    label=f"🌐 Launch {first_app['title']}",
                    kind="open_web",
                    payload={
                        "url": first_app["url"],
                        "title": first_app["title"],
                        "id": first_app.get("id", ""),
                    },
                    reason="Quick-launch interactive MrSutherland.net classroom simulation",
                )

        if effective_glass == "off":
            add_candidate(
                label="✏️ Annotate Screen (Glass Ink)",
                kind="glass_ink",
                payload={"mode": "draw", "colour": "red"},
                reason="Draw directly over any application on the classroom display",
            )

        if effective_target != "board":
            add_candidate(
                label="🧑‍🏫 Switch to Teaching Board",
                kind="switch_display",
                payload={"target": "board"},
                reason="Bring the Teaching Board canvas to the classroom display",
            )

        add_candidate(
            label="🖼️ Stage Lesson Diagrams",
            kind="stage_query",
            payload={"query": f"{cleaned_topic} diagram", "count": 3},
            reason=f"Search and stage visual diagrams for '{effective_title}'",
        )

        add_candidate(
            label="➕ New Board Page",
            kind="board_control",
            payload={"action": "new_page"},
            reason="Add a clean Teaching Board page for the next phase of the lesson",
        )

        selected = candidates[:3]
        result: list[dict[str, Any]] = []
        for idx, item in enumerate(selected, start=1):
            result.append(
                {
                    "cue_id": f"cue-{idx}",
                    "label": item["label"],
                    "kind": item["kind"],
                    "payload": copy.deepcopy(item["payload"]),
                    "reason": item["reason"],
                }
            )
        return result

    def get_context(self) -> dict[str, Any]:
        """Return the complete showrunner state including 3 predictive cues."""
        with self._lock:
            cues = self.compute_predictive_cues()
            return {
                "active_lesson_id": self.active_lesson_id,
                "lesson_title": self.lesson_title,
                "active_display_target": self.active_display_target,
                "active_web_url": self.active_web_url,
                "frozen": self.frozen,
                "staged_count": self.staged_count,
                "glass_mode": self.glass_mode,
                "cues": cues,
                "recent_events": copy.deepcopy(self._events[-10:]),
            }
