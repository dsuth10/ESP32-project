"""Teaching Board visual theme: colour tokens, fonts and Qt stylesheets.

This module is a style layer only. It does not create lessons, send requests,
change Freeze/Resume behaviour, or add presentation features. Douglas can try
another look later by swapping TOKENS / BoardTheme and rebuilding the sheet.

Glass/blur from the original mock-ups is not used. Qt stylesheets have no
backdrop-filter, and the pupil display is a classroom projector: solids with
high contrast are the supported look.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QStyleFactory, QVBoxLayout, QWidget,
)

FONT_DIR = Path(__file__).resolve().parent / 'board_theme_fonts'

# CompanionOS glassmorphism tokens from DESIGN.md, plus projector-safe solids.
TOKENS = {
    'background': '#0b1326',
    'surface': '#0b1326',
    'surface_dim': '#0b1326',
    'surface_lowest': '#060e20',
    'surface_low': '#131b2e',
    'surface_container': '#171f33',
    'surface_high': '#222a3d',
    'surface_highest': '#2d3449',
    'on_surface': '#dae2fd',
    'on_surface_variant': '#bbc9cd',
    'outline': '#859397',
    'outline_variant': '#3c494c',
    'primary': '#8aebff',
    'primary_container': '#22d3ee',
    'on_primary': '#00363e',
    'on_primary_container': '#005763',
    'secondary': '#cebdff',
    'secondary_container': '#4f319c',
    'on_secondary_container': '#bea8ff',
    'tertiary': '#68f5b8',
    'tertiary_container': '#46d89d',
    'on_tertiary': '#003824',
    'error': '#ffb4ab',
    'error_container': '#93000a',
    'on_error_container': '#ffdad6',
    'freeze': '#dc2626',
    'freeze_fill': '#93000a',
    'live': '#68f5b8',
    'live_fill': '#005a3d',
    'page': '#ffffff',
    'viewport': '#131b2e',
    'selection': '#22d3ee',
    'input_fill': '#060e20',
    'placeholder': '#859397',
}

_UI_FAMILY = 'Segoe UI'
_MONO_FAMILY = 'Consolas'
_FONTS_READY = False
_APPLIED = False
_FALLBACK_UI = ('Inter', 'Segoe UI', 'Noto Sans', 'Liberation Sans', 'DejaVu Sans', 'Arial')
_FALLBACK_MONO = ('JetBrains Mono', 'Cascadia Mono', 'Consolas', 'DejaVu Sans Mono', 'Liberation Mono', 'Courier New')


def tokens():
    """Copy of the active colour tokens."""
    return dict(TOKENS)


def color(name):
    return QColor(TOKENS[name])


def ui_font_family():
    _load_fonts()
    return _UI_FAMILY


def mono_font_family():
    _load_fonts()
    return _MONO_FAMILY


def _load_fonts():
    """Register bundled OFL/Apache fonts. Never downloads."""
    global _FONTS_READY, _UI_FAMILY, _MONO_FAMILY
    if _FONTS_READY:
        return
    if QApplication.instance() is None:
        _UI_FAMILY, _MONO_FAMILY = 'Inter', 'JetBrains Mono'
        return
    _FONTS_READY = True
    loaded_ui, loaded_mono = [], []
    if FONT_DIR.is_dir():
        for path in sorted(FONT_DIR.glob('*.ttf')):
            handle = QFontDatabase.addApplicationFont(str(path))
            if handle < 0:
                continue
            families = list(QFontDatabase.applicationFontFamilies(handle))
            if path.name.startswith('Inter'):
                loaded_ui.extend(families)
            elif path.name.startswith('JetBrainsMono'):
                loaded_mono.extend(families)
    families = set(QFontDatabase.families())
    if loaded_ui:
        _UI_FAMILY = loaded_ui[0]
    else:
        _UI_FAMILY = next((name for name in _FALLBACK_UI if name in families), 'sans-serif')
    if loaded_mono:
        _MONO_FAMILY = loaded_mono[0]
    else:
        _MONO_FAMILY = next((name for name in _FALLBACK_MONO if name in families), 'monospace')


def build_stylesheet(palette=None, *, pupil_scale=False):
    """One Qt stylesheet. pupil_scale enlarges audience controls for projectors."""
    _load_fonts()
    t = palette or TOKENS
    ui, mono = _UI_FAMILY, _MONO_FAMILY
    control_pad = '10px 16px' if pupil_scale else '6px 12px'
    control_min = '48px' if pupil_scale else '32px'
    body = '18px' if pupil_scale else '13px'
    title = '22px' if pupil_scale else '13px'
    return f"""
    * {{
        font-family: "{ui}";
        color: {t['on_surface']};
    }}
    QWidget {{
        background-color: {t['background']};
        color: {t['on_surface']};
        font-size: {body};
    }}
    QMainWindow, QDialog, QTabWidget, QScrollArea, QSplitter {{
        background-color: {t['background']};
    }}
    QLabel {{
        background: transparent;
        color: {t['on_surface']};
    }}
    QLabel#boardNotice {{
        color: {t['primary']};
        font-family: "{mono}";
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1px;
    }}
    QLabel#boardLocation {{
        color: {t['on_surface_variant']};
        font-size: 12px;
    }}
    QLabel#boardStatus {{
        color: {t['on_surface']};
        font-size: 13px;
        padding: 6px 10px;
        border-radius: 8px;
        background-color: {t['surface_container']};
        border: 1px solid {t['outline_variant']};
    }}
    QLabel#boardChipLive, QLabel#boardChipFrozen, QLabel#boardChipSaved,
    QLabel#boardPageChip, QLabel#boardPupilFreezeChip, QLabel#boardRailCaption {{
        font-family: "{mono}";
        font-weight: 700;
        letter-spacing: 1px;
        padding: 4px 10px;
        border-radius: 999px;
        background: transparent;
    }}
    QLabel#boardChipLive {{
        color: {t['tertiary']};
        background-color: {t['live_fill']};
        border: 1px solid {t['tertiary']};
    }}
    QLabel#boardChipFrozen, QLabel#boardPupilFreezeChip {{
        color: {t['on_error_container']};
        background-color: {t['error_container']};
        border: 1px solid {t['error']};
        font-size: {title};
    }}
    QLabel#boardChipSaved {{
        color: {t['primary']};
        background-color: {t['surface_highest']};
        border: 1px solid {t['outline_variant']};
    }}
    QLabel#boardPageChip, QLabel#boardPupilPage {{
        color: {t['on_surface']};
        background-color: {t['surface_highest']};
        border: 1px solid {t['outline_variant']};
        border-radius: 8px;
        font-size: {title};
        font-weight: 600;
        padding: 6px 12px;
        font-family: "{ui}";
        letter-spacing: 0;
    }}
    QLabel#boardRailCaption {{
        color: {t['outline']};
        font-size: 10px;
        padding: 0;
        border: none;
    }}
    QWidget#boardCommandDeck, QWidget#boardFilesBar, QWidget#boardPageStrip,
    QWidget#boardToolRail, QWidget#boardStage, QWidget#boardPupilHud,
    QWidget#boardInspector, QScrollArea#boardInspector, QWidget#boardDialog {{
        background-color: {t['surface_low']};
        border: 1px solid {t['outline_variant']};
        border-radius: 12px;
    }}
    QWidget#boardToolRail {{
        min-width: 108px;
        max-width: 124px;
        border-top: 1px solid rgba(255, 255, 255, 40);
    }}
    QWidget#boardTeacherCanvas, QGraphicsView#boardTeacherCanvas,
    QGraphicsView#boardPupilCanvas {{
        background-color: {t['viewport']};
        border: 1px solid {t['outline_variant']};
        border-radius: 16px;
    }}
    QPushButton {{
        background-color: {t['surface_highest']};
        color: {t['on_surface']};
        border: 1px solid {t['outline_variant']};
        border-radius: 8px;
        padding: {control_pad};
        min-height: {control_min};
        font-size: {body};
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: {t['surface_high']};
        border-color: {t['primary']};
        color: {t['primary']};
    }}
    QPushButton:pressed {{
        background-color: {t['surface_container']};
    }}
    QPushButton:checked {{
        background-color: {t['primary_container']};
        color: {t['on_primary']};
        border: 1px solid {t['primary']};
        font-weight: 600;
    }}
    QPushButton:disabled, QPushButton:checked:disabled {{
        color: {t['outline']};
        background-color: {t['surface_container']};
        border-color: {t['outline_variant']};
    }}
    QPushButton#boardPrimary, QDialogButtonBox QPushButton#boardPrimary {{
        background-color: {t['primary_container']};
        color: {t['on_primary']};
        border: 1px solid {t['primary']};
        font-weight: 600;
    }}
    QPushButton#boardPrimary:hover, QDialogButtonBox QPushButton#boardPrimary:hover {{
        background-color: {t['primary']};
        color: {t['on_primary']};
    }}
    QPushButton#boardPrimary:disabled {{
        color: {t['on_primary']};
        background-color: {t['surface_highest']};
        border-color: {t['outline_variant']};
    }}
    QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
        background-color: {t['surface_high']};
        border: none;
        width: 18px;
    }}
    QPushButton#boardFreeze {{
        background-color: {t['surface_highest']};
        color: {t['error']};
        border: 1px solid {t['error']};
        font-family: "{mono}";
        font-weight: 700;
        letter-spacing: 1px;
    }}
    QPushButton#boardFreeze[frozen="true"] {{
        background-color: {t['freeze']};
        color: {t['on_error_container']};
        border: 1px solid {t['error']};
    }}
    QPushButton#boardResume {{
        background-color: {t['surface_highest']};
        color: {t['tertiary']};
        border: 1px solid {t['tertiary']};
        font-family: "{mono}";
        font-weight: 700;
        letter-spacing: 1px;
    }}
    QPushButton#boardResume[frozen="true"] {{
        background-color: {t['tertiary_container']};
        color: {t['on_tertiary']};
        border: 1px solid {t['tertiary']};
    }}
    QWidget#boardToolRail QPushButton {{
        min-height: 52px;
        padding: 8px 6px;
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {t['input_fill']};
        color: {t['on_surface']};
        border: 1px solid {t['outline_variant']};
        border-radius: 8px;
        padding: 6px 8px;
        selection-background-color: {t['primary_container']};
        selection-color: {t['on_primary']};
    }}
    QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border: 1px solid {t['primary_container']};
    }}
    QComboBox QAbstractItemView {{
        background-color: {t['surface_high']};
        color: {t['on_surface']};
        selection-background-color: {t['primary_container']};
        selection-color: {t['on_primary']};
        border: 1px solid {t['outline_variant']};
    }}
    QListWidget, QListView {{
        background-color: {t['input_fill']};
        color: {t['on_surface']};
        border: 1px solid {t['outline_variant']};
        border-radius: 8px;
        outline: none;
    }}
    QListWidget::item:selected, QListView::item:selected {{
        background-color: {t['primary_container']};
        color: {t['on_primary']};
    }}
    QTabWidget::pane {{
        border: 1px solid {t['outline_variant']};
        border-radius: 8px;
        background-color: {t['surface_low']};
        top: -1px;
    }}
    QTabBar::tab {{
        background-color: {t['surface_container']};
        color: {t['on_surface_variant']};
        padding: 8px 14px;
        border: 1px solid {t['outline_variant']};
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        margin-right: 4px;
    }}
    QTabBar::tab:selected {{
        background-color: {t['primary_container']};
        color: {t['on_primary']};
    }}
    QCheckBox {{
        color: {t['on_surface']};
        spacing: 8px;
        background: transparent;
    }}
    QCheckBox::indicator {{
        width: 16px; height: 16px;
        border-radius: 4px;
        border: 1px solid {t['outline']};
        background-color: {t['input_fill']};
    }}
    QCheckBox::indicator:checked {{
        background-color: {t['primary_container']};
        border-color: {t['primary']};
    }}
    QScrollBar:vertical, QScrollBar:horizontal {{
        background: {t['surface_lowest']};
        border: none;
        width: 10px;
        height: 10px;
        margin: 0;
    }}
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
        background: {t['surface_highest']};
        border-radius: 5px;
        min-height: 24px;
        min-width: 24px;
    }}
    QSplitter::handle {{
        background-color: {t['outline_variant']};
        width: 2px;
    }}
    QMenuBar {{
        background-color: {t['surface_lowest']};
        color: {t['on_surface']};
    }}
    QMenuBar::item:selected {{
        background-color: {t['surface_high']};
    }}
    QMenu {{
        background-color: {t['surface_high']};
        color: {t['on_surface']};
        border: 1px solid {t['outline_variant']};
    }}
    QMenu::item:selected {{
        background-color: {t['primary_container']};
        color: {t['on_primary']};
    }}
    QStatusBar {{
        background-color: {t['surface_lowest']};
        color: {t['on_surface_variant']};
    }}
    QHeaderView::section {{
        background-color: {t['surface_high']};
        color: {t['on_surface']};
        border: none;
        padding: 4px;
    }}
    QMessageBox {{
        background-color: {t['surface_low']};
    }}
    QToolTip {{
        background-color: {t['surface_high']};
        color: {t['on_surface']};
        border: 1px solid {t['primary']};
        padding: 4px 8px;
    }}
    """


def application_palette():
    _load_fonts()
    pal = QPalette()
    bg, fg = color('background'), color('on_surface')
    pal.setColor(QPalette.ColorRole.Window, bg)
    pal.setColor(QPalette.ColorRole.WindowText, fg)
    pal.setColor(QPalette.ColorRole.Base, color('input_fill'))
    pal.setColor(QPalette.ColorRole.AlternateBase, color('surface_container'))
    pal.setColor(QPalette.ColorRole.Text, fg)
    pal.setColor(QPalette.ColorRole.Button, color('surface_highest'))
    pal.setColor(QPalette.ColorRole.ButtonText, fg)
    pal.setColor(QPalette.ColorRole.Highlight, color('primary_container'))
    pal.setColor(QPalette.ColorRole.HighlightedText, color('on_primary'))
    pal.setColor(QPalette.ColorRole.ToolTipBase, color('surface_high'))
    pal.setColor(QPalette.ColorRole.ToolTipText, fg)
    pal.setColor(QPalette.ColorRole.PlaceholderText, color('placeholder'))
    pal.setColor(QPalette.ColorRole.BrightText, color('primary'))
    pal.setColor(QPalette.ColorRole.Link, color('primary_container'))
    return pal


def apply_application(app=None):
    """Idempotent application-wide Fusion + stylesheet. Safe to call from tests."""
    global _APPLIED
    app = app or QApplication.instance()
    if app is None:
        return False
    _load_fonts()
    if not _APPLIED:
        available = {name.casefold() for name in QStyleFactory.keys()}
        if 'fusion' in available:
            app.setStyle('Fusion')
        app.setPalette(application_palette())
        app.setFont(QFont(_UI_FAMILY, 10))
        _APPLIED = True
    app.setStyleSheet(build_stylesheet())
    return True


def _panel(name):
    widget = QFrame()
    widget.setObjectName(name)
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    widget.setFrameShape(QFrame.Shape.NoFrame)
    return widget


def _chip(name, text=''):
    label = QLabel(text)
    label.setObjectName(name)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


def _repolish(widget):
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def install(candidate):
    """Arrange existing teacher/pupil controls into cockpit chrome and apply the sheet.

    Widget identity, labels and slots stay the same. New widgets are display-only
    chips that mirror Frozen/Live, Saved/Unsaved and the current page title.
    """
    apply_application()
    candidate.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    candidate.pupil.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    candidate.setObjectName('boardTeacher')
    candidate.pupil.setObjectName('boardPupilDisplay')
    candidate.teacher_canvas.setObjectName('boardTeacherCanvas')
    candidate.pupil_canvas.setObjectName('boardPupilCanvas')
    candidate.status.setObjectName('boardStatus')
    candidate.location.setObjectName('boardLocation')
    candidate.side_scroll.setObjectName('boardInspector')
    candidate.pupil_page.setObjectName('boardPupilPage')
    candidate.add_image_button.setObjectName('boardPrimary')
    if getattr(candidate, 'freeze_button', None):
        candidate.freeze_button.setObjectName('boardFreeze')
    if getattr(candidate, 'resume_button', None):
        candidate.resume_button.setObjectName('boardResume')
    if getattr(candidate, 'notice', None):
        candidate.notice.setObjectName('boardNotice')
    panel = getattr(candidate, 'agent_panel', None)
    if panel is not None and getattr(panel, 'send_button', None):
        panel.send_button.setObjectName('boardPrimary')
    if getattr(candidate, '_board_theme_installed', False):
        sync(candidate)
        return candidate
    _install_teacher_chrome(candidate)
    _install_pupil_chrome(candidate)
    apply_application()
    candidate.pupil.setStyleSheet(build_stylesheet(pupil_scale=True))
    for widget in (candidate.freeze_button, candidate.resume_button, candidate.add_image_button):
        if widget is not None:
            _repolish(widget)
    if panel is not None and getattr(panel, 'send_button', None):
        _repolish(panel.send_button)
    candidate._board_theme_installed = True
    sync(candidate)
    return candidate


def _install_teacher_chrome(candidate):
    layout = candidate.layout()
    if layout is None:
        return
    chrome = {}
    deck = _panel('boardCommandDeck')
    deck_row = QHBoxLayout(deck)
    deck_row.setContentsMargins(10, 8, 10, 8)
    deck_row.setSpacing(8)
    if getattr(candidate, 'notice', None):
        deck_row.addWidget(candidate.notice)
    deck_row.addWidget(candidate.name, 1)
    rename = next((b for b in candidate.findChildren(QPushButton) if b.text() == 'Rename lesson'), None)
    if rename is not None:
        deck_row.addWidget(rename)
    live = _chip('boardChipLive', 'PUPIL LIVE')
    saved = _chip('boardChipSaved', 'SAVED')
    deck_row.addWidget(saved)
    deck_row.addWidget(live)
    if getattr(candidate, 'freeze_button', None):
        deck_row.addWidget(candidate.freeze_button)
    if getattr(candidate, 'resume_button', None):
        deck_row.addWidget(candidate.resume_button)
    chrome['live_chip'] = live
    chrome['saved_chip'] = saved

    files = _panel('boardFilesBar')
    files_row = QHBoxLayout(files)
    files_row.setContentsMargins(10, 6, 10, 6)
    files_row.setSpacing(8)
    for button in candidate.file_buttons.values():
        files_row.addWidget(button)

    strip = _panel('boardPageStrip')
    strip_row = QHBoxLayout(strip)
    strip_row.setContentsMargins(10, 6, 10, 6)
    strip_row.setSpacing(8)
    page_chip = _chip('boardPageChip', 'Page')
    chrome['page_chip'] = page_chip
    for key in ('Previous', 'Next', 'New page'):
        button = (getattr(candidate, 'page_nav', {}) or {}).get(key)
        if button is not None:
            strip_row.addWidget(button)
        if key == 'Previous':
            strip_row.addWidget(page_chip, 1)
    for key in ('Undo', 'Redo'):
        button = (getattr(candidate, 'history_buttons', {}) or {}).get(key)
        if button is not None:
            strip_row.addWidget(button)
    strip_row.addWidget(candidate.zoom)

    rail = _panel('boardToolRail')
    rail_col = QVBoxLayout(rail)
    rail_col.setContentsMargins(8, 10, 8, 10)
    rail_col.setSpacing(6)
    caption = QLabel('TOOLS')
    caption.setObjectName('boardRailCaption')
    caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
    rail_col.addWidget(caption)
    for button in candidate.teacher_tools.values():
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        rail_col.addWidget(button)
    toolbar_image = getattr(candidate, 'add_image_toolbar', None)
    if toolbar_image is not None:
        toolbar_image.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        toolbar_image.setObjectName('boardPrimary')
        rail_col.addWidget(toolbar_image)
    rail_col.addStretch(1)
    chrome['tool_rail'] = rail

    candidate.mode.setParent(candidate)
    candidate.mode.hide()
    splitter = candidate.teacher_canvas.parentWidget()
    stage = _panel('boardStage')
    stage_row = QHBoxLayout(stage)
    stage_row.setContentsMargins(8, 8, 8, 8)
    stage_row.setSpacing(8)
    stage_row.addWidget(rail)
    stage_row.addWidget(candidate.teacher_canvas, 1)
    if splitter is not None:
        splitter.insertWidget(0, stage)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
    chrome['stage'] = stage

    exports = QWidget()
    exports.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    export_row = QHBoxLayout(exports)
    export_row.setContentsMargins(0, 0, 0, 0)
    export_row.setSpacing(8)
    for button in candidate.findChildren(QPushButton):
        if button.text().startswith(('Export ', 'Import ')) and button.parent() is candidate:
            export_row.addWidget(button)

    while layout.count():
        item = layout.takeAt(0)
        if item.widget() in (deck, files, strip, splitter, candidate.location, candidate.status, exports):
            continue
        # Nested layouts from the original construction are discarded once
        # their widgets have been reparented into chrome containers.
        del item
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(10)
    layout.addWidget(deck)
    layout.addWidget(files)
    layout.addWidget(strip)
    layout.addWidget(candidate.location)
    if splitter is not None:
        layout.addWidget(splitter, 1)
    layout.addWidget(candidate.status)
    layout.addWidget(exports)
    candidate._theme_chrome = chrome


def _install_pupil_chrome(candidate):
    pupil = candidate.pupil
    layout = pupil.layout()
    if layout is None:
        return
    hud = _panel('boardPupilHud')
    row = QHBoxLayout(hud)
    row.setContentsMargins(12, 10, 12, 10)
    row.setSpacing(12)
    row.addWidget(candidate.pupil_page, 1)
    freeze_chip = _chip('boardPupilFreezeChip', 'LIVE')
    freeze_chip.setObjectName('boardChipLive')
    row.addWidget(freeze_chip)
    layout.insertWidget(0, hud)
    chrome = getattr(candidate, '_theme_chrome', {})
    chrome['pupil_hud'] = hud
    chrome['pupil_freeze_chip'] = freeze_chip
    candidate._theme_chrome = chrome
    pupil.layout().setContentsMargins(12, 12, 12, 12)
    pupil.layout().setSpacing(10)


def install_dialog(dialog):
    """Style a teacher dialog (Add image, settings, previews) without new actions."""
    apply_application()
    dialog.setObjectName('boardDialog')
    dialog.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    for button in dialog.findChildren(QPushButton):
        text = button.text().casefold()
        if 'insert' in text or text in {'save', 'present this page', 'use image and present'}:
            button.setObjectName('boardPrimary')
            _repolish(button)
    return dialog


def sync(candidate):
    """Refresh chrome chips from the existing teacher/pupil views. No commands."""
    chrome = getattr(candidate, '_theme_chrome', None)
    if not chrome:
        return
    teacher = candidate.session.teacher_view()
    pupil = candidate.session.pupil_view()
    frozen = bool(teacher.get('frozen'))
    pages = teacher['document']['pages']
    index = next(i for i, page in enumerate(pages) if page['id'] == teacher['page_id'])
    title = pages[index].get('title') or f'Page {index + 1}'
    page_chip = chrome.get('page_chip')
    if page_chip is not None:
        page_chip.setText(f'Page {index + 1} of {len(pages)}  ·  {title}')
    live = chrome.get('live_chip')
    if live is not None:
        live.setText('PUPIL FROZEN' if frozen else 'PUPIL LIVE')
        live.setObjectName('boardChipFrozen' if frozen else 'boardChipLive')
        _repolish(live)
    saved = chrome.get('saved_chip')
    if saved is not None:
        if teacher.get('save_error'):
            saved.setText('SAVE FAILED')
        elif teacher.get('dirty'):
            saved.setText('UNSAVED')
        else:
            saved.setText('SAVED')
        _repolish(saved)
    freeze = getattr(candidate, 'freeze_button', None)
    resume = getattr(candidate, 'resume_button', None)
    for button, flag in ((freeze, frozen), (resume, frozen)):
        if button is None:
            continue
        button.setProperty('frozen', 'true' if flag else 'false')
        _repolish(button)
    pupil_chip = chrome.get('pupil_freeze_chip')
    if pupil_chip is not None:
        pupil_frozen = bool(pupil.get('frozen'))
        pupil_chip.setText('FROZEN BY TEACHER' if pupil_frozen else 'LIVE')
        pupil_chip.setObjectName('boardChipFrozen' if pupil_frozen else 'boardChipLive')
        _repolish(pupil_chip)
