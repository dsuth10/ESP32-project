"""Touch-first Teacher Deck client and home simulator window.

Australian English spelling conventions and PySide6 Qt foundations.
Designed for 7"-10" touchscreens (800x480 to 1280x800) at school, and
windowed desktop simulation on Windows at home.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
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

PODIUM_STYLESHEET = """
QMainWindow {
    background-color: #0f172a;
}
QWidget {
    background-color: #0f172a;
    color: #f8fafc;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 14px;
}
QTabWidget::pane {
    border: 1px solid #334155;
    background-color: #1e293b;
    border-radius: 8px;
}
QTabBar::tab {
    background-color: #0f172a;
    color: #94a3b8;
    border: 1px solid #334155;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 10px 20px;
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
    min-height: 44px;
}
QLineEdit:focus {
    border: 2px solid #38bdf8;
}
QPushButton {
    background-color: #334155;
    color: #f8fafc;
    border: 1px solid #475569;
    border-radius: 8px;
    font-weight: bold;
    font-size: 14px;
    min-height: 48px;
    padding: 8px 14px;
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
    """Touchscreen teacher control surface and image staging deck."""

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
        self.current_selected_image: dict[str, Any] | None = None
        self.timer: QTimer | None = None

        self.setWindowTitle("Teacher Deck · Classroom Touch Surface")
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
        root_layout.setSpacing(10)

        # -------------------------------------------------------------
        # 1. Top Status & Display Bar
        # -------------------------------------------------------------
        top_bar = QFrame(self)
        top_bar.setStyleSheet(
            "background-color: #1e293b; border: 1px solid #334155; border-radius: 8px;"
        )
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(10, 6, 10, 6)
        top_layout.setSpacing(10)

        self.connection_label = QLabel("Waiting for Classroom PC…", self)
        self.connection_label.setStyleSheet("color: #f87171; font-weight: bold; font-size: 14px;")
        self.connection_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        top_layout.addWidget(self.connection_label)

        self.freeze_button = QPushButton("LIVE ON STUDENT SCREEN (Tap to Freeze)", self)
        self.freeze_button.setStyleSheet(
            "background-color: #059669; color: #ffffff; font-weight: bold; "
            "border: 2px solid #10b981; border-radius: 8px; min-height: 48px; padding: 8px 16px;"
        )
        self.freeze_button.clicked.connect(self._handle_freeze_toggle)
        top_layout.addWidget(self.freeze_button)

        # Classroom Display Switcher buttons
        self.display_buttons: dict[str, QPushButton] = {}
        for key, label in [
            ("board", "Board"),
            ("onenote", "OneNote"),
            ("word", "Word"),
            ("chrome", "Chrome"),
        ]:
            btn = QPushButton(label, self)
            btn.setStyleSheet(
                "background-color: #1e293b; color: #38bdf8; font-weight: bold; "
                "border: 1px solid #0284c7; border-radius: 8px; min-height: 48px; min-width: 72px;"
            )
            btn.clicked.connect(lambda checked=False, t=key: self._handle_display_switch(t))
            self.display_buttons[key] = btn
            top_layout.addWidget(btn)

        root_layout.addWidget(top_bar)

        # -------------------------------------------------------------
        # 2. Main Centre Area (QTabWidget)
        # -------------------------------------------------------------
        self.tabs = QTabWidget(self)

        # Tab 1: Image Staging & Series
        staging_tab = QWidget(self)
        staging_layout = QVBoxLayout(staging_tab)
        staging_layout.setContentsMargins(8, 8, 8, 8)
        staging_layout.setSpacing(8)

        # Filter / Search Row
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

        # Splitter / Columns for Staging Grid and Inspector
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

        # Right Inspector Panel
        inspector_frame = QFrame(self)
        inspector_frame.setStyleSheet(
            "background-color: #0f172a; border: 1px solid #334155; border-radius: 8px;"
        )
        inspector_layout = QVBoxLayout(inspector_frame)
        inspector_layout.setContentsMargins(12, 12, 12, 12)
        inspector_layout.setSpacing(10)

        self.preview_image_label = QLabel("No Image Selected", self)
        self.preview_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image_label.setMinimumSize(240, 160)
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
            "border: 1px solid #38bdf8; border-radius: 8px; min-height: 52px; font-size: 15px;"
        )
        self.present_current_button.clicked.connect(self._handle_present_current)
        inspector_layout.addWidget(self.present_current_button)

        self.present_new_page_button = QPushButton("Put on New Page", self)
        self.present_new_page_button.setEnabled(False)
        self.present_new_page_button.setStyleSheet(
            "background-color: #047857; color: #ffffff; font-weight: bold; "
            "border: 1px solid #34d399; border-radius: 8px; min-height: 52px; font-size: 15px;"
        )
        self.present_new_page_button.clicked.connect(self._handle_present_new_page)
        inspector_layout.addWidget(self.present_new_page_button)

        staging_splitter.addWidget(inspector_frame)
        staging_splitter.setStretchFactor(0, 3)
        staging_splitter.setStretchFactor(1, 2)

        staging_layout.addWidget(staging_splitter)
        self.tabs.addTab(staging_tab, "Image Staging & Series")

        # Tab 2: Lesson Pages
        pages_tab = QWidget(self)
        pages_layout = QVBoxLayout(pages_tab)
        pages_layout.setContentsMargins(12, 12, 12, 12)
        pages_layout.setSpacing(8)

        self.pages_list = QListWidget(self)
        self.pages_list.setStyleSheet("font-size: 15px;")
        pages_layout.addWidget(self.pages_list)

        self.tabs.addTab(pages_tab, "Lesson Pages")

        root_layout.addWidget(self.tabs, stretch=1)

        # -------------------------------------------------------------
        # 3. Bottom Control Strip
        # -------------------------------------------------------------
        bottom_bar = QFrame(self)
        bottom_bar.setStyleSheet(
            "background-color: #1e293b; border: 1px solid #334155; border-radius: 8px;"
        )
        bottom_layout = QVBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(10, 6, 10, 6)
        bottom_layout.setSpacing(6)

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
                "border: 1px solid #475569; border-radius: 8px; min-height: 48px; padding: 8px 14px;"
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

    def refresh_state(self) -> None:
        """Fetch latest status and staged images, updating UI state resiliently."""
        try:
            status = self.client.get_status()
            staged = self.client.list_staged()
            self.connected = True
            self.last_status = status
            self.last_staged = staged
            self._update_ui_from_state()
        except Exception:
            self.connected = False
            self.connection_label.setText("Waiting for Classroom PC…")
            self.connection_label.setStyleSheet("color: #f87171; font-weight: bold; font-size: 14px;")

    def _update_ui_from_state(self) -> None:
        title = self.last_status.get("title", "") or "Lesson"
        self.connection_label.setText(f"Connected · {title}")
        self.connection_label.setStyleSheet("color: #34d399; font-weight: bold; font-size: 14px;")

        # Freeze Button State
        frozen = bool(self.last_status.get("frozen", False))
        if frozen:
            self.freeze_button.setText("PUPIL SCREEN FROZEN (Tap to Resume)")
            self.freeze_button.setStyleSheet(
                "background-color: #d97706; color: #ffffff; font-weight: bold; "
                "border: 2px solid #f59e0b; border-radius: 8px; min-height: 48px; padding: 8px 16px;"
            )
        else:
            self.freeze_button.setText("LIVE ON STUDENT SCREEN (Tap to Freeze)")
            self.freeze_button.setStyleSheet(
                "background-color: #059669; color: #ffffff; font-weight: bold; "
                "border: 2px solid #10b981; border-radius: 8px; min-height: 48px; padding: 8px 16px;"
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

            # Fetch thumbnail bytes from client (cached in client._thumb_cache)
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
            # Current selection was removed or updated
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
    """CLI entry point for launching the Teacher Deck touch surface."""
    parser = argparse.ArgumentParser(description="Raspberry Pi Teacher Touchscreen Client")
    parser.add_argument("--url", help="Teacher Deck API URL (e.g. http://127.0.0.1:8790)")
    parser.add_argument("--token", help="Bearer token for Teacher Deck API")
    parser.add_argument("--config", help="Path to JSON configuration file")
    parser.add_argument(
        "--windowed", action="store_true", help="Launch in desktop windowed simulator mode"
    )
    parser.add_argument(
        "--kiosk", action="store_true", help="Launch fullscreen in kiosk appliance mode"
    )
    parser.add_argument("--width", type=int, help="Window width (default 1024)")
    parser.add_argument("--height", type=int, help="Window height (default 600)")
    parser.add_argument("--poll-ms", type=int, help="Polling interval in ms (default 1000)")

    args = parser.parse_args(argv)

    cfg = load_deck_config(args.config)
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
    )
    window = TeacherDeckWindow(client=client, poll_ms=cfg["poll_ms"])

    if cfg["kiosk"]:
        window.showFullScreen()
    else:
        window.resize(cfg["width"], cfg["height"])
        window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
