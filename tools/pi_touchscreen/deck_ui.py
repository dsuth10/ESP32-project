"""JoshuaOS Podium — 14-inch Touchscreen Classroom Operating Surface.

Australian English spelling conventions and PySide6 Qt foundations.
Designed for the teacher's 14" touchscreen podium (1280x800 to 1920x1080)
at school and home over Tailscale, with backward-compatible 800x480+ scaling.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

if __package__:
    from .deck_client import DeckClientError, TeacherDeckClient, load_deck_config
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from deck_client import DeckClientError, TeacherDeckClient, load_deck_config

DEFAULT_CATALOGUE_ITEMS: list[dict[str, str]] = [
    {
        "id": "mrsutherland-home",
        "title": "MrSutherland.net — Classroom Hub",
        "category": "Portal",
        "url": "https://mrsutherland.net/",
        "description": "Primary interactive classroom launchpad and lesson hub",
    },
    {
        "id": "mrsutherland-timers",
        "title": "Classroom Timers & Warm-Ups",
        "category": "Routines",
        "url": "https://mrsutherland.net/#timers",
        "description": "Focus timers, bell-ringers, and transition countdowns",
    },
    {
        "id": "mrsutherland-literacy",
        "title": "Interactive Literacy & Modelling",
        "category": "English",
        "url": "https://mrsutherland.net/#literacy",
        "description": "Guided reading, sentence builders, and vocabulary scaffolds",
    },
    {
        "id": "mrsutherland-science",
        "title": "STEM & Science Visualisers",
        "category": "Science",
        "url": "https://mrsutherland.net/#science",
        "description": "Interactive cycles, simulations, and inquiry diagrams",
    },
]

DEFAULT_SHOWRUNNER_CUES: list[dict[str, Any]] = [
    {
        "id": "cue-default-web",
        "label": "🌐 Open MrSutherland.net",
        "kind": "open_web",
        "payload": {"url": "https://mrsutherland.net/", "title": "MrSutherland.net"},
    },
    {
        "id": "cue-default-draw",
        "label": "✏️ Annotate Screen",
        "kind": "glass_ink",
        "payload": {"action": "draw", "colour": "red"},
    },
    {
        "id": "cue-default-snap",
        "label": "📸 Snap Screen to Board",
        "kind": "glass_ink",
        "payload": {"action": "snap_to_board", "target": "new_page"},
    },
]

GLASS_COLOUR_SWATCHES: list[tuple[str, str, str]] = [
    ("red", "Red", "#ef4444"),
    ("blue", "Blue", "#3b82f6"),
    ("yellow", "Yellow", "#eab308"),
    ("green", "Green", "#22c55e"),
    ("white", "White", "#f8fafc"),
]

PODIUM_STYLESHEET = """
QMainWindow {
    background-color: #0b1120;
}
QWidget {
    background-color: #0b1120;
    color: #f8fafc;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 14px;
}
QTabWidget::pane {
    border: 1px solid #334155;
    background-color: #1e293b;
    border-radius: 10px;
}
QTabBar::tab {
    background-color: #0f172a;
    color: #94a3b8;
    border: 1px solid #334155;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 10px 18px;
    font-size: 14px;
    font-weight: bold;
    min-height: 38px;
}
QTabBar::tab:selected {
    background-color: #1e293b;
    color: #38bdf8;
    border-color: #38bdf8;
}
QListWidget {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    color: #f8fafc;
    padding: 6px;
}
QListWidget::item {
    background-color: #334155;
    border-radius: 8px;
    margin: 4px;
    padding: 8px;
    color: #f8fafc;
}
QListWidget::item:selected {
    background-color: #0284c7;
    border: 2px solid #38bdf8;
    color: #ffffff;
}
QLineEdit {
    background-color: #1e293b;
    border: 1px solid #475569;
    border-radius: 8px;
    padding: 8px 12px;
    color: #f8fafc;
    font-size: 14px;
    min-height: 42px;
}
QLineEdit:focus {
    border: 2px solid #38bdf8;
}
QComboBox {
    background-color: #0f172a;
    color: #38bdf8;
    border: 1px solid #0284c7;
    border-radius: 8px;
    padding: 6px 12px;
    font-weight: bold;
    font-size: 13px;
    min-height: 40px;
}
QComboBox QAbstractItemView {
    background-color: #1e293b;
    color: #f8fafc;
    selection-background-color: #0284c7;
}
QPushButton {
    background-color: #334155;
    color: #f8fafc;
    border: 1px solid #475569;
    border-radius: 8px;
    font-weight: bold;
    font-size: 14px;
    min-height: 44px;
    padding: 8px 12px;
}
QPushButton:hover {
    background-color: #475569;
}
QPushButton:pressed {
    background-color: #1e293b;
}
QPushButton:disabled {
    background-color: #1e293b;
    color: #64748b;
    border-color: #334155;
}
"""


class TeacherDeckWindow(QMainWindow):
    """JoshuaOS Podium 14-inch touchscreen operating surface and teacher deck."""

    def __init__(
        self,
        client: TeacherDeckClient,
        poll_ms: int = 1000,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.client = client
        self.poll_ms = max(0, int(poll_ms))
        self.connected: bool = False
        self.last_status: dict[str, Any] = {}
        self.last_staged: list[dict[str, Any]] = []
        self.catalogue_items: list[dict[str, Any]] = list(DEFAULT_CATALOGUE_ITEMS)
        self.catalogue_loaded_from_server: bool = False
        self.current_selected_image: dict[str, Any] | None = None
        self.selected_catalogue_item: dict[str, Any] | None = None
        self.active_display_target: str = "board"
        self.active_glass_colour: str = "red"
        self.current_cues: list[dict[str, Any]] = list(DEFAULT_SHOWRUNNER_CUES)
        self.timer: QTimer | None = None

        self.setWindowTitle("JoshuaOS Podium · Classroom Operating Surface")
        self.setStyleSheet(PODIUM_STYLESHEET)
        self.setMinimumSize(800, 480)

        self._build_ui()

        if self.poll_ms > 0:
            self.timer = QTimer(self)
            self.timer.setInterval(self.poll_ms)
            self.timer.timeout.connect(self.refresh_state)
            self.timer.start()

        # Initial refresh attempt
        self.refresh_state()

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(8)

        # -------------------------------------------------------------
        # Zone 1: Top Podium Bar (Brand, Host Selector, Connection, Freeze)
        # -------------------------------------------------------------
        top_bar = QFrame(self)
        top_bar.setStyleSheet(
            "background-color: #1e293b; border: 1px solid #334155; border-radius: 10px;"
        )
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 6, 12, 6)
        top_layout.setSpacing(10)

        self.brand_label = QLabel("JOSHUA OS · PODIUM", self)
        self.brand_label.setStyleSheet(
            "background-color: #0284c7; color: #ffffff; font-weight: 900; "
            "font-size: 13px; letter-spacing: 1px; padding: 6px 12px; border-radius: 6px;"
        )
        top_layout.addWidget(self.brand_label)

        self.connection_label = QLabel("Waiting for Classroom PC…", self)
        self.connection_label.setStyleSheet("color: #f87171; font-weight: bold; font-size: 14px;")
        self.connection_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        top_layout.addWidget(self.connection_label)

        self.host_combo = QComboBox(self)
        self.host_combo.setMinimumWidth(190)
        self._populate_host_combo()
        self.host_combo.currentIndexChanged.connect(self._handle_host_combo_changed)
        top_layout.addWidget(self.host_combo)

        self.freeze_button = QPushButton("LIVE ON STUDENT SCREEN (Tap to Freeze)", self)
        self.freeze_button.setStyleSheet(
            "background-color: #059669; color: #ffffff; font-weight: bold; "
            "border: 2px solid #10b981; border-radius: 8px; min-height: 46px; padding: 8px 16px;"
        )
        self.freeze_button.clicked.connect(self._handle_freeze_toggle)
        top_layout.addWidget(self.freeze_button)

        root_layout.addWidget(top_bar)

        # -------------------------------------------------------------
        # Zone 2: Main 3-Column Podium Workspace
        #   Left Rail: Stage Switcher
        #   Centre: QTabWidget (Image Staging, MrSutherland.net Launchpad, Lesson Pages)
        #   Right Rail: Glass Ink & Overlay Controls
        # -------------------------------------------------------------
        middle_row = QHBoxLayout()
        middle_row.setSpacing(8)

        # --- Left Rail: Stage Switcher ---
        left_rail = QFrame(self)
        left_rail.setMinimumWidth(155)
        left_rail.setMaximumWidth(195)
        left_rail.setStyleSheet(
            "background-color: #1e293b; border: 1px solid #334155; border-radius: 10px;"
        )
        left_layout = QVBoxLayout(left_rail)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        stage_header = QLabel("STAGE SWITCHER", self)
        stage_header.setStyleSheet(
            "color: #94a3b8; font-size: 11px; font-weight: bold; letter-spacing: 1px;"
        )
        left_layout.addWidget(stage_header)

        self.display_buttons: dict[str, QPushButton] = {}
        for key, label in [
            ("board", "📋 Board"),
            ("chrome", "🌐 Web / Chrome"),
            ("onenote", "📓 OneNote"),
            ("word", "📄 Word"),
        ]:
            btn = QPushButton(label, self)
            btn.setMinimumHeight(52)
            btn.clicked.connect(lambda checked=False, t=key: self._handle_display_switch(t))
            self.display_buttons[key] = btn
            left_layout.addWidget(btn)

        left_layout.addStretch()
        self._update_display_button_styles()
        middle_row.addWidget(left_rail)

        # --- Centre: QTabWidget ---
        self.tabs = QTabWidget(self)

        # Tab 0: Image Staging & Series
        staging_tab = QWidget(self)
        staging_layout = QVBoxLayout(staging_tab)
        staging_layout.setContentsMargins(8, 8, 8, 8)
        staging_layout.setSpacing(8)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search or stage library images…")
        self.search_input.returnPressed.connect(self._handle_search_library)
        filter_row.addWidget(self.search_input)

        self.search_button = QPushButton("Search Library", self)
        self.search_button.clicked.connect(self._handle_search_library)
        filter_row.addWidget(self.search_button)

        self.stage_search_button = QPushButton("Stage Series", self)
        self.stage_search_button.clicked.connect(self._handle_stage_series)
        filter_row.addWidget(self.stage_search_button)

        self.show_staged_button = QPushButton("Show Staged Tray", self)
        self.show_staged_button.clicked.connect(self._handle_show_staged)
        filter_row.addWidget(self.show_staged_button)

        staging_layout.addLayout(filter_row)

        staging_splitter = QSplitter(Qt.Orientation.Horizontal, self)

        self.image_list = QListWidget(self)
        self.image_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.image_list.setIconSize(QSize(140, 105))
        self.image_list.setGridSize(QSize(160, 160))
        self.image_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.image_list.setWordWrap(True)
        self.image_list.currentItemChanged.connect(self._on_image_selected)
        self.image_list.itemSelectionChanged.connect(self._on_image_selection_changed)
        staging_splitter.addWidget(self.image_list)

        inspector_frame = QFrame(self)
        inspector_frame.setStyleSheet(
            "background-color: #0f172a; border: 1px solid #334155; border-radius: 8px;"
        )
        inspector_layout = QVBoxLayout(inspector_frame)
        inspector_layout.setContentsMargins(12, 12, 12, 12)
        inspector_layout.setSpacing(10)

        self.preview_image_label = QLabel("No Image Selected", self)
        self.preview_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image_label.setMinimumSize(220, 150)
        self.preview_image_label.setStyleSheet(
            "background-color: #1e293b; border: 1px solid #334155; border-radius: 6px;"
        )
        inspector_layout.addWidget(self.preview_image_label)

        self.preview_title_label = QLabel("Select an image to preview", self)
        self.preview_title_label.setStyleSheet("font-weight: bold; font-size: 15px; color: #f8fafc;")
        self.preview_title_label.setWordWrap(True)
        inspector_layout.addWidget(self.preview_title_label)

        self.preview_meta_label = QLabel("", self)
        self.preview_meta_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self.preview_meta_label.setWordWrap(True)
        inspector_layout.addWidget(self.preview_meta_label)

        inspector_layout.addStretch()

        self.present_current_button = QPushButton("Put on Current Page", self)
        self.present_current_button.setEnabled(False)
        self.present_current_button.setStyleSheet(
            "background-color: #0284c7; color: #ffffff; font-weight: bold; "
            "border: 1px solid #38bdf8; border-radius: 8px; min-height: 48px; font-size: 15px;"
        )
        self.present_current_button.clicked.connect(self._handle_present_current)
        inspector_layout.addWidget(self.present_current_button)

        self.present_new_page_button = QPushButton("Put on New Page", self)
        self.present_new_page_button.setEnabled(False)
        self.present_new_page_button.setStyleSheet(
            "background-color: #047857; color: #ffffff; font-weight: bold; "
            "border: 1px solid #34d399; border-radius: 8px; min-height: 48px; font-size: 15px;"
        )
        self.present_new_page_button.clicked.connect(self._handle_present_new_page)
        inspector_layout.addWidget(self.present_new_page_button)

        staging_splitter.addWidget(inspector_frame)
        staging_splitter.setStretchFactor(0, 3)
        staging_splitter.setStretchFactor(1, 2)

        staging_layout.addWidget(staging_splitter)
        self.tabs.addTab(staging_tab, "Image Staging & Series")

        # Tab 1: MrSutherland.net Launchpad
        launchpad_tab = QWidget(self)
        launchpad_layout = QVBoxLayout(launchpad_tab)
        launchpad_layout.setContentsMargins(10, 10, 10, 10)
        launchpad_layout.setSpacing(8)

        launchpad_top = QHBoxLayout()
        launchpad_top.setSpacing(8)

        self.catalogue_filter_input = QLineEdit(self)
        self.catalogue_filter_input.setPlaceholderText("Filter MrSutherland.net interactive lessons…")
        self.catalogue_filter_input.textChanged.connect(self._filter_catalogue_list)
        launchpad_top.addWidget(self.catalogue_filter_input)

        self.refresh_catalogue_button = QPushButton("↻ Reload Catalogue", self)
        self.refresh_catalogue_button.clicked.connect(self._handle_reload_catalogue)
        launchpad_top.addWidget(self.refresh_catalogue_button)

        launchpad_layout.addLayout(launchpad_top)

        self.catalogue_list = QListWidget(self)
        self.catalogue_list.setStyleSheet("font-size: 15px;")
        self.catalogue_list.currentItemChanged.connect(self._on_catalogue_item_selected)
        self.catalogue_list.itemDoubleClicked.connect(lambda _item: self._handle_launch_web_lesson())
        launchpad_layout.addWidget(self.catalogue_list, stretch=1)

        launch_bar = QHBoxLayout()
        launch_bar.setSpacing(8)

        self.web_url_input = QLineEdit(self)
        self.web_url_input.setPlaceholderText("https://mrsutherland.net/…")
        self.web_url_input.setText("https://mrsutherland.net/")
        self.web_url_input.returnPressed.connect(self._handle_launch_web_lesson)
        launch_bar.addWidget(self.web_url_input, stretch=1)

        self.launch_web_button = QPushButton("🚀 Launch on Student Display", self)
        self.launch_web_button.setStyleSheet(
            "background-color: #0284c7; color: #ffffff; font-weight: bold; "
            "border: 1px solid #38bdf8; border-radius: 8px; min-height: 48px; padding: 8px 18px;"
        )
        self.launch_web_button.clicked.connect(self._handle_launch_web_lesson)
        launch_bar.addWidget(self.launch_web_button)

        launchpad_layout.addLayout(launch_bar)
        self.tabs.addTab(launchpad_tab, "MrSutherland.net Launchpad")
        self._populate_catalogue_list(self.catalogue_items)

        # Tab 2: Lesson Pages
        pages_tab = QWidget(self)
        pages_layout = QVBoxLayout(pages_tab)
        pages_layout.setContentsMargins(12, 12, 12, 12)
        pages_layout.setSpacing(8)

        self.pages_list = QListWidget(self)
        self.pages_list.setStyleSheet("font-size: 15px;")
        pages_layout.addWidget(self.pages_list)

        self.tabs.addTab(pages_tab, "Lesson Pages")

        middle_row.addWidget(self.tabs, stretch=1)

        # --- Right Rail: Glass Ink & Overlay ---
        right_rail = QFrame(self)
        right_rail.setMinimumWidth(200)
        right_rail.setMaximumWidth(235)
        right_rail.setStyleSheet(
            "background-color: #1e293b; border: 1px solid #334155; border-radius: 10px;"
        )
        right_layout = QVBoxLayout(right_rail)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(8)

        glass_header = QLabel("GLASS INK & OVERLAY", self)
        glass_header.setStyleSheet(
            "color: #94a3b8; font-size: 11px; font-weight: bold; letter-spacing: 1px;"
        )
        right_layout.addWidget(glass_header)

        self.glass_status_label = QLabel("Glass Overlay: OFF", self)
        self.glass_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.glass_status_label.setStyleSheet(
            "background-color: #0f172a; color: #94a3b8; font-weight: bold; "
            "font-size: 12px; padding: 6px; border-radius: 6px; border: 1px solid #334155;"
        )
        right_layout.addWidget(self.glass_status_label)

        self.glass_buttons: dict[str, QPushButton] = {}
        glass_defs = [
            ("draw", "✏️ Draw Over Screen"),
            ("interact", "👆 Interact (Click-Through)"),
            ("off", "👁️ Hide Overlay"),
            ("clear", "🧽 Clear Ink"),
            ("snap_to_board", "📸 Snap & Keep to Board"),
        ]
        for g_key, g_label in glass_defs:
            g_btn = QPushButton(g_label, self)
            if g_key == "snap_to_board":
                g_btn.setStyleSheet(
                    "background-color: #047857; color: #ffffff; font-weight: bold; "
                    "border: 1px solid #34d399; border-radius: 8px; min-height: 46px;"
                )
            elif g_key == "draw":
                g_btn.setStyleSheet(
                    "background-color: #0284c7; color: #ffffff; font-weight: bold; "
                    "border: 1px solid #38bdf8; border-radius: 8px; min-height: 46px;"
                )
            g_btn.clicked.connect(lambda checked=False, a=g_key: self._handle_glass_action(a))
            self.glass_buttons[g_key] = g_btn
            right_layout.addWidget(g_btn)

        colour_row = QHBoxLayout()
        colour_row.setSpacing(4)
        self.glass_colour_buttons: dict[str, QPushButton] = {}
        for c_key, c_label, c_hex in GLASS_COLOUR_SWATCHES:
            c_btn = QPushButton("", self)
            c_btn.setToolTip(f"Ink Colour: {c_label}")
            c_btn.setFixedSize(34, 34)
            c_btn.clicked.connect(lambda checked=False, ck=c_key: self._handle_glass_colour(ck))
            self.glass_colour_buttons[c_key] = c_btn
            colour_row.addWidget(c_btn)
        right_layout.addLayout(colour_row)
        self._update_glass_colour_styles()

        right_layout.addStretch()
        middle_row.addWidget(right_rail)

        root_layout.addLayout(middle_row, stretch=1)

        # -------------------------------------------------------------
        # Zone 4: Bottom Bar (Hermes Showrunner Cues + Board Controls)
        # -------------------------------------------------------------
        bottom_bar = QFrame(self)
        bottom_bar.setStyleSheet(
            "background-color: #1e293b; border: 1px solid #334155; border-radius: 10px;"
        )
        bottom_layout = QVBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(10, 6, 10, 6)
        bottom_layout.setSpacing(6)

        # Hermes Showrunner Predictive Cue Strip
        cue_row = QHBoxLayout()
        cue_row.setSpacing(8)

        self.showrunner_label = QLabel("🧠 HERMES SHOWRUNNER:", self)
        self.showrunner_label.setStyleSheet(
            "color: #c084fc; font-weight: bold; font-size: 12px; letter-spacing: 0.5px;"
        )
        cue_row.addWidget(self.showrunner_label)

        self.cue_buttons: list[QPushButton] = []
        for idx in range(3):
            c_btn = QPushButton("", self)
            c_btn.setStyleSheet(
                "background-color: #2e1065; color: #f3e8ff; font-weight: bold; "
                "border: 1px solid #9333ea; border-radius: 8px; min-height: 40px; padding: 6px 12px;"
            )
            c_btn.clicked.connect(lambda checked=False, i=idx: self._handle_cue_clicked(i))
            self.cue_buttons.append(c_btn)
            cue_row.addWidget(c_btn, stretch=1)

        self._update_showrunner_cues(self.current_cues)
        bottom_layout.addLayout(cue_row)

        # Board Navigation & Undo/Redo Strip
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(8)

        self.control_buttons: dict[str, QPushButton] = {}
        button_defs = [
            ("prev_page", "◀ Prev Page"),
            ("next_page", "Next Page ▶"),
            ("new_page", "+ New Page"),
            ("undo", "↶ Undo"),
            ("redo", "↷ Redo"),
            ("refresh", "⟳ Refresh"),
        ]
        for key, text in button_defs:
            btn = QPushButton(text, self)
            btn.setStyleSheet(
                "background-color: #334155; color: #f8fafc; font-weight: bold; "
                "border: 1px solid #475569; border-radius: 8px; min-height: 44px; padding: 6px 14px;"
            )
            btn.clicked.connect(lambda checked=False, k=key: self._handle_control_action(k))
            self.control_buttons[key] = btn
            ctrl_row.addWidget(btn)

        ctrl_row.addStretch()

        self.page_indicator_label = QLabel("Page 1 of 1", self)
        self.page_indicator_label.setStyleSheet("font-weight: bold; font-size: 15px; color: #38bdf8;")
        ctrl_row.addWidget(self.page_indicator_label)

        bottom_layout.addLayout(ctrl_row)

        self.feedback_label = QLabel("Ready.", self)
        self.feedback_label.setStyleSheet("color: #94a3b8; font-size: 13px;")
        bottom_layout.addWidget(self.feedback_label)

        root_layout.addWidget(bottom_bar)

    def _populate_host_combo(self) -> None:
        self.host_combo.blockSignals(True)
        self.host_combo.clear()
        hosts = self.client.list_hosts() if hasattr(self.client, "list_hosts") else []
        active_id = getattr(self.client, "active_host_id", "default")
        active_idx = 0
        for idx, h in enumerate(hosts):
            label = h.get("label", h.get("id", "Classroom PC"))
            h_id = h.get("id", "default")
            self.host_combo.addItem(f"🖥️ {label}", h_id)
            if h_id == active_id:
                active_idx = idx
        if self.host_combo.count() > 0:
            self.host_combo.setCurrentIndex(active_idx)
        self.host_combo.blockSignals(False)

    def _handle_host_combo_changed(self, index: int) -> None:
        if index < 0:
            return
        host_id = self.host_combo.itemData(index)
        if not host_id or not hasattr(self.client, "switch_host"):
            return
        try:
            target = self.client.switch_host(str(host_id))
            self.catalogue_loaded_from_server = False
            self.feedback_label.setText(
                f"Switched active host to {target.get('label', host_id)} ({target.get('url', '')})."
            )
            self.refresh_state()
        except Exception as exc:
            self.feedback_label.setText(f"Host switch error: {exc}")

    def _update_display_button_styles(self) -> None:
        active = str(self.active_display_target or "board").strip().lower()
        for key, btn in self.display_buttons.items():
            if key == active:
                btn.setStyleSheet(
                    "background-color: #0284c7; color: #ffffff; font-weight: bold; "
                    "border: 2px solid #34d399; border-radius: 8px; min-height: 52px;"
                )
            else:
                btn.setStyleSheet(
                    "background-color: #0f172a; color: #38bdf8; font-weight: bold; "
                    "border: 1px solid #0284c7; border-radius: 8px; min-height: 52px;"
                )

    def _update_glass_colour_styles(self) -> None:
        for c_key, _c_label, c_hex in GLASS_COLOUR_SWATCHES:
            btn = self.glass_colour_buttons.get(c_key)
            if btn is None:
                continue
            border = "3px solid #38bdf8" if c_key == self.active_glass_colour else "1px solid #475569"
            btn.setStyleSheet(
                f"background-color: {c_hex}; border: {border}; border-radius: 17px; min-height: 34px; max-height: 34px;"
            )

    def _update_showrunner_cues(self, cues: list[dict[str, Any]] | None) -> None:
        resolved: list[dict[str, Any]] = []
        if isinstance(cues, list) and cues:
            for item in cues[:3]:
                if isinstance(item, dict) and item.get("label"):
                    resolved.append(item)
        if not resolved:
            resolved = list(DEFAULT_SHOWRUNNER_CUES)
        while len(resolved) < 3:
            resolved.append(DEFAULT_SHOWRUNNER_CUES[len(resolved) % len(DEFAULT_SHOWRUNNER_CUES)])
        self.current_cues = resolved[:3]
        for idx, btn in enumerate(self.cue_buttons):
            cue = self.current_cues[idx]
            btn.setText(str(cue.get("label", f"Cue {idx + 1}")))
            btn.setEnabled(True)

    def refresh_state(self) -> None:
        """Fetch latest status and staged images, updating UI state resiliently."""
        try:
            status = self.client.get_status()
            staged = self.client.list_staged()
            self.connected = True
            self.last_status = status
            self.last_staged = staged
            if not self.catalogue_loaded_from_server and hasattr(self.client, "list_catalogue"):
                try:
                    remote_cat = self.client.list_catalogue()
                    if isinstance(remote_cat, list) and remote_cat:
                        self.catalogue_items = remote_cat
                        self._populate_catalogue_list(self.catalogue_items)
                    self.catalogue_loaded_from_server = True
                except Exception:
                    pass
            self._update_ui_from_state()
        except Exception:
            self.connected = False
            self.connection_label.setText("Waiting for Classroom PC…")
            self.connection_label.setStyleSheet("color: #f87171; font-weight: bold; font-size: 14px;")

    def _update_ui_from_state(self) -> None:
        title = self.last_status.get("title", "") or "Lesson"
        self.connection_label.setText(f"Connected · {title}")
        self.connection_label.setStyleSheet("color: #34d399; font-weight: bold; font-size: 14px;")

        # Active Display Target Highlight
        disp = (
            self.last_status.get("active_display_target")
            or self.last_status.get("display_target")
            or self.active_display_target
            or "board"
        )
        self.active_display_target = str(disp).lower()
        self._update_display_button_styles()

        # Glass Ink Status
        glass_state = self.last_status.get("glass")
        if isinstance(glass_state, dict):
            mode = str(glass_state.get("mode") or ("draw" if glass_state.get("enabled") else "off")).lower()
            self._apply_glass_mode_badge(mode)

        # Hermes Showrunner Predictive Cues
        if "showrunner_cues" in self.last_status:
            self._update_showrunner_cues(self.last_status.get("showrunner_cues"))

        # Freeze Button State
        frozen = bool(self.last_status.get("frozen", False))
        if frozen:
            self.freeze_button.setText("PUPIL SCREEN FROZEN (Tap to Resume)")
            self.freeze_button.setStyleSheet(
                "background-color: #d97706; color: #ffffff; font-weight: bold; "
                "border: 2px solid #f59e0b; border-radius: 8px; min-height: 46px; padding: 8px 16px;"
            )
        else:
            self.freeze_button.setText("LIVE ON STUDENT SCREEN (Tap to Freeze)")
            self.freeze_button.setStyleSheet(
                "background-color: #059669; color: #ffffff; font-weight: bold; "
                "border: 2px solid #10b981; border-radius: 8px; min-height: 46px; padding: 8px 16px;"
            )

        # Page Indicator
        page_idx = self.last_status.get("page_index", 0)
        page_count = self.last_status.get("page_count", 1)
        self.page_indicator_label.setText(f"Page {page_idx + 1} of {max(1, page_count)}")

        # Pages Tab List
        self.pages_list.clear()
        pages = self.last_status.get("pages", [])
        curr_page_id = self.last_status.get("page_id")
        for idx, page in enumerate(pages):
            p_title = page.get("title") or f"Page {idx + 1}"
            count = page.get("object_count", 0)
            is_curr = (page.get("id") == curr_page_id)
            suffix = " [Current]" if is_curr else ""
            if p_title.lower().startswith("page "):
                label_text = f"{p_title} ({count} items){suffix}"
            else:
                label_text = f"Page {idx + 1}: {p_title} ({count} items){suffix}"
            self.pages_list.addItem(QListWidgetItem(label_text))

        # Staged Image List
        self._populate_image_list(self.last_staged)

    def _apply_glass_mode_badge(self, mode: str) -> None:
        cleaned = str(mode or "off").lower()
        if cleaned == "draw":
            self.glass_status_label.setText("DRAWING ON SCREEN")
            self.glass_status_label.setStyleSheet(
                "background-color: #0284c7; color: #ffffff; font-weight: bold; "
                "font-size: 12px; padding: 6px; border-radius: 6px; border: 1px solid #38bdf8;"
            )
        elif cleaned in {"interact", "passthrough", "click_through"}:
            self.glass_status_label.setText("CLICK-THROUGH LIVE")
            self.glass_status_label.setStyleSheet(
                "background-color: #047857; color: #ffffff; font-weight: bold; "
                "font-size: 12px; padding: 6px; border-radius: 6px; border: 1px solid #34d399;"
            )
        else:
            self.glass_status_label.setText("Glass Overlay: OFF")
            self.glass_status_label.setStyleSheet(
                "background-color: #0f172a; color: #94a3b8; font-weight: bold; "
                "font-size: 12px; padding: 6px; border-radius: 6px; border: 1px solid #334155;"
            )

    def _populate_catalogue_list(self, items: list[dict[str, Any]]) -> None:
        self.catalogue_list.blockSignals(True)
        self.catalogue_list.clear()
        for entry in items:
            if not isinstance(entry, dict):
                continue
            title = entry.get("title") or entry.get("name") or "Interactive Lesson"
            category = entry.get("category") or "Web"
            desc = entry.get("description") or entry.get("url") or ""
            label = f"🌐 [{category}] {title}\n    {desc}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.catalogue_list.addItem(item)
        self.catalogue_list.blockSignals(False)
        if self.catalogue_list.count() > 0:
            self.catalogue_list.setCurrentRow(0)
            self._on_catalogue_item_selected(self.catalogue_list.currentItem(), None)

    def _filter_catalogue_list(self, query: str) -> None:
        q = str(query or "").strip().lower()
        if not q:
            self._populate_catalogue_list(self.catalogue_items)
            return
        filtered = [
            item
            for item in self.catalogue_items
            if q in str(item.get("title", "")).lower()
            or q in str(item.get("category", "")).lower()
            or q in str(item.get("description", "")).lower()
        ]
        self._populate_catalogue_list(filtered)

    def _on_catalogue_item_selected(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            self.selected_catalogue_item = None
            return
        data = current.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, dict):
            self.selected_catalogue_item = data
            url = str(data.get("url") or "").strip()
            if url:
                self.web_url_input.setText(url)

    def _handle_reload_catalogue(self) -> None:
        try:
            items = self.client.list_catalogue()
            if items:
                self.catalogue_items = items
                self.catalogue_loaded_from_server = True
            else:
                self.catalogue_items = list(DEFAULT_CATALOGUE_ITEMS)
            self._populate_catalogue_list(self.catalogue_items)
            self.feedback_label.setText(f"Loaded {len(self.catalogue_items)} launchpad lessons.")
        except Exception as exc:
            self.feedback_label.setText(f"Catalogue reload fallback: {exc}")

    def _handle_launch_web_lesson(self) -> None:
        url = self.web_url_input.text().strip()
        title = ""
        if self.selected_catalogue_item and self.selected_catalogue_item.get("url") == url:
            title = str(self.selected_catalogue_item.get("title") or "").strip()
        if not url and self.selected_catalogue_item:
            url = str(self.selected_catalogue_item.get("url") or "").strip()
            title = str(self.selected_catalogue_item.get("title") or "").strip()
        if not url:
            self.feedback_label.setText("Select a lesson or enter a URL to launch.")
            return
        try:
            self.client.open_web_lesson(url=url, title=title or url)
            self.active_display_target = "chrome"
            self._update_display_button_styles()
            self.feedback_label.setText(f"Launched '{title or url}' on student display.")
            self.refresh_state()
        except Exception as exc:
            self.feedback_label.setText(f"Web launch error: {exc}")

    def _handle_glass_action(self, action: str) -> None:
        try:
            self.client.glass_control(
                action=action,
                colour=self.active_glass_colour if action == "draw" else None,
            )
            if action in {"draw", "interact", "off"}:
                self._apply_glass_mode_badge(action)
            action_labels = {
                "draw": f"Glass Ink active ({self.active_glass_colour}).",
                "interact": "Glass overlay set to click-through interaction.",
                "off": "Glass overlay hidden.",
                "clear": "Cleared Glass Ink annotations.",
                "snap_to_board": "Snapped screen + Glass Ink onto new Board page.",
            }
            self.feedback_label.setText(action_labels.get(action, f"Glass action: {action}"))
            self.refresh_state()
        except Exception as exc:
            self.feedback_label.setText(f"Glass control error: {exc}")

    def _handle_glass_colour(self, colour_key: str) -> None:
        self.active_glass_colour = colour_key
        self._update_glass_colour_styles()
        try:
            self.client.glass_control(action="colour", colour=colour_key)
            self.feedback_label.setText(f"Selected {colour_key} Glass Ink.")
        except Exception as exc:
            self.feedback_label.setText(f"Glass colour error: {exc}")

    def _handle_cue_clicked(self, index: int) -> None:
        if index < 0 or index >= len(self.current_cues):
            return
        cue = self.current_cues[index]
        label = str(cue.get("label") or f"Cue {index + 1}")
        try:
            self.client.execute_showrunner_cue(cue)
            self.feedback_label.setText(f"Showrunner executed: {label}")
            self.refresh_state()
        except Exception as exc:
            self.feedback_label.setText(f"Showrunner cue error: {exc}")

    def _populate_image_list(self, items: list[dict[str, Any]]) -> None:
        previously_selected_vid = (
            self.current_selected_image.get("version_id")
            if self.current_selected_image
            else None
        )
        self.image_list.blockSignals(True)
        self.image_list.clear()

        selected_row: int | None = None
        for idx, item_data in enumerate(items):
            vid = item_data.get("version_id", "")
            title = item_data.get("title", "Image")
            origin = item_data.get("origin", "library")
            review = item_data.get("review_state", "draft")

            if origin == "generated" and review == "draft":
                badge = "[Generated · Draft]"
            elif review == "approved":
                badge = "[Approved]"
            else:
                badge = f"[{origin.title()} · {review.title()}]"

            display_text = f"{title}\n{badge}"

            icon = QIcon()
            if vid:
                try:
                    raw_thumb = self.client.get_thumbnail(vid)
                    pix = QPixmap()
                    if raw_thumb and pix.loadFromData(raw_thumb):
                        scaled = pix.scaled(
                            140,
                            105,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        icon = QIcon(scaled)
                except Exception:
                    pass

            item = QListWidgetItem(icon, display_text) if not icon.isNull() else QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, item_data)
            self.image_list.addItem(item)

            if previously_selected_vid and vid == previously_selected_vid:
                selected_row = idx

        self.image_list.blockSignals(False)

        if selected_row is not None:
            self.image_list.setCurrentRow(selected_row)
        elif self.image_list.count() > 0 and self.current_selected_image is not None:
            self._on_image_selected(self.image_list.currentItem(), None)
        elif self.image_list.count() == 0:
            self._on_image_selected(None, None)

    def _on_image_selection_changed(self) -> None:
        self._on_image_selected(self.image_list.currentItem(), None)

    def _on_image_selected(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            self.current_selected_image = None
            self.preview_image_label.setPixmap(QPixmap())
            self.preview_image_label.setText("No Image Selected")
            self.preview_title_label.setText("Select an image to preview")
            self.preview_meta_label.setText("")
            self.present_current_button.setEnabled(False)
            self.present_new_page_button.setEnabled(False)
            return

        data = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            return

        self.current_selected_image = data
        self.present_current_button.setEnabled(True)
        self.present_new_page_button.setEnabled(True)

        title = data.get("title", "Untitled")
        self.preview_title_label.setText(title)

        meta_lines = [
            f"Dimensions: {data.get('width', 0)} × {data.get('height', 0)} px",
            f"Origin: {data.get('origin', 'unknown').title()} · Status: {data.get('review_state', 'draft').title()}",
        ]
        credit = str(data.get("credit", "")).strip()
        if credit:
            meta_lines.append(f"Credit: {credit}")
        self.preview_meta_label.setText("\n".join(meta_lines))

        vid = data.get("version_id")
        if vid:
            try:
                thumb_bytes = self.client.get_thumbnail(vid)
                pix = QPixmap()
                if thumb_bytes and pix.loadFromData(thumb_bytes):
                    scaled = pix.scaled(
                        280,
                        200,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self.preview_image_label.setPixmap(scaled)
                else:
                    self.preview_image_label.setText("No Thumbnail Available")
            except Exception:
                self.preview_image_label.setText("Thumbnail Unavailable")

    def _handle_freeze_toggle(self) -> None:
        is_frozen = bool(self.last_status.get("frozen", False))
        action = "resume" if is_frozen else "freeze"
        try:
            self.client.board_control(action)
            self.feedback_label.setText(f"Board {'resumed' if is_frozen else 'frozen'}.")
            self.refresh_state()
        except Exception as exc:
            self.feedback_label.setText(f"Control error: {exc}")

    def _handle_display_switch(self, target: str) -> None:
        try:
            self.client.switch_display(target)
            self.active_display_target = target.lower()
            self._update_display_button_styles()
            self.feedback_label.setText(f"Student display switched to {target.title()}.")
            self.refresh_state()
        except Exception as exc:
            self.feedback_label.setText(f"Display switch error: {exc}")

    def _handle_control_action(self, action: str) -> None:
        if action == "refresh":
            self.refresh_state()
            self.feedback_label.setText("Refreshed state.")
            return

        try:
            self.client.board_control(action)
            action_names = {
                "prev_page": "Navigated to previous page.",
                "next_page": "Navigated to next page.",
                "new_page": "Created new page.",
                "undo": "Undone last action.",
                "redo": "Redone action.",
            }
            self.feedback_label.setText(action_names.get(action, f"Executed {action}."))
            self.refresh_state()
        except Exception as exc:
            self.feedback_label.setText(f"Action error: {exc}")

    def _handle_present_current(self) -> None:
        if not self.current_selected_image:
            return
        vid = self.current_selected_image.get("version_id")
        if not vid:
            return
        try:
            self.client.present_image(vid, target="current_page")
            self.feedback_label.setText("Image placed on current page.")
            self.refresh_state()
        except DeckClientError as exc:
            if exc.status == 409:
                self.feedback_label.setText(
                    "Current page is full. Tap 'Put on New Page' to present on a fresh page without deleting content."
                )
            else:
                self.feedback_label.setText(f"Presentation error: {exc.message}")
        except Exception as exc:
            self.feedback_label.setText(f"Presentation error: {exc}")

    def _handle_present_new_page(self) -> None:
        if not self.current_selected_image:
            return
        vid = self.current_selected_image.get("version_id")
        if not vid:
            return
        try:
            self.client.present_image(vid, target="new_page")
            self.feedback_label.setText("Image placed on new page.")
            self.refresh_state()
        except DeckClientError as exc:
            self.feedback_label.setText(f"Presentation error: {exc.message}")
        except Exception as exc:
            self.feedback_label.setText(f"Presentation error: {exc}")

    def _handle_search_library(self) -> None:
        query = self.search_input.text().strip()
        try:
            results = self.client.search_library(query=query, limit=16)
            self._populate_image_list(results)
            self.feedback_label.setText(f"Found {len(results)} images in library.")
        except Exception as exc:
            self.feedback_label.setText(f"Library search error: {exc}")

    def _handle_stage_series(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            self.feedback_label.setText("Enter a prompt or topic to stage.")
            return
        try:
            res = self.client.stage_images(query=query)
            items = res.get("items", [])
            self.refresh_state()
            self.feedback_label.setText(f"Staged series with {len(items)} candidates.")
        except Exception as exc:
            self.feedback_label.setText(f"Stage series error: {exc}")

    def _handle_show_staged(self) -> None:
        try:
            staged = self.client.list_staged()
            self.last_staged = staged
            self._populate_image_list(staged)
            self.feedback_label.setText(f"Displaying {len(staged)} staged candidate items.")
        except Exception as exc:
            self.feedback_label.setText(f"Staged list error: {exc}")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for launching the JoshuaOS Podium touch surface."""
    parser = argparse.ArgumentParser(description="JoshuaOS Podium — 14-inch Teacher Touchscreen Client")
    parser.add_argument("--url", help="Teacher Deck API URL (e.g. http://127.0.0.1:8790)")
    parser.add_argument("--token", help="Bearer token for Teacher Deck API")
    parser.add_argument("--host-id", help="Active Tailscale host ID from config (e.g. school-pc or home-pc)")
    parser.add_argument("--config", help="Path to JSON configuration file")
    parser.add_argument(
        "--windowed", action="store_true", help="Launch in desktop windowed simulator mode"
    )
    parser.add_argument(
        "--kiosk", action="store_true", help="Launch fullscreen in kiosk appliance mode"
    )
    parser.add_argument("--width", type=int, help="Window width (default 1280)")
    parser.add_argument("--height", type=int, help="Window height (default 800)")
    parser.add_argument("--poll-ms", type=int, help="Polling interval in ms (default 1000)")

    args = parser.parse_args(argv)

    cfg = load_deck_config(args.config)
    if args.host_id:
        cfg["active_host_id"] = args.host_id
        for h in cfg.get("hosts", []):
            if h.get("id") == args.host_id:
                cfg["url"] = h.get("url", cfg["url"])
                if h.get("token"):
                    cfg["token"] = h["token"]
    if args.url:
        cfg["url"] = args.url
    if args.token:
        cfg["token"] = args.token
    if args.poll_ms is not None:
        cfg["poll_ms"] = args.poll_ms
    if args.windowed:
        cfg["windowed"] = True
    if args.kiosk:
        cfg["kiosk"] = True
    if args.width is not None:
        cfg["width"] = args.width
    if args.height is not None:
        cfg["height"] = args.height

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv if argv is None else [sys.argv[0]] + argv)

    client = TeacherDeckClient(
        base_url=cfg["url"],
        token=cfg["token"],
        timeout=3.0,
        hosts=cfg.get("hosts"),
        active_host_id=cfg.get("active_host_id"),
    )
    window = TeacherDeckWindow(client=client, poll_ms=cfg["poll_ms"])

    if cfg["kiosk"] and not cfg["windowed"]:
        window.showFullScreen()
    else:
        window.resize(cfg["width"], cfg["height"])
        window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
