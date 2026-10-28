"""Theme tokens, stylesheet and chrome — visual only, no lesson behaviour."""
import os
from pathlib import Path
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

import board_theme
from board_candidate import BoardCandidate, demo_model, image_resolver
from board_image_picker import ImagePicker
from board_session import BoardSession
from board_store import BoardStore
from media_store import MediaStore


def test_tokens_match_the_companionos_palette():
    palette = board_theme.tokens()
    assert palette['background'] == '#0b1326'
    assert palette['primary_container'] == '#22d3ee'
    assert palette['primary'] == '#8aebff'
    assert palette['secondary'] == '#cebdff'
    assert palette['tertiary'] == '#68f5b8'
    assert palette['freeze'] == '#dc2626'
    assert palette['page'] == '#ffffff'
    assert palette['viewport'] == '#131b2e'
    assert palette['page'] != palette['viewport']
    assert palette['selection'] == '#22d3ee'


def test_stylesheet_is_local_and_uses_tokens():
    sheet = board_theme.build_stylesheet()
    palette = board_theme.tokens()
    assert 'http://' not in sheet and 'https://' not in sheet
    assert 'backdrop-filter' not in sheet
    assert palette['background'] in sheet
    assert palette['primary_container'] in sheet
    assert palette['freeze'] in sheet
    assert '#boardFreeze' in sheet
    pupil = board_theme.build_stylesheet(pupil_scale=True)
    assert '18px' in pupil
    assert pupil.index('18px') > 0


def test_fonts_resolve_without_network():
    app = QApplication.instance() or QApplication([])
    board_theme._FONTS_READY = False
    board_theme._load_fonts()
    family = board_theme.ui_font_family()
    mono = board_theme.mono_font_family()
    assert family
    assert mono
    assert 'http' not in family.casefold()
    bundled = list(board_theme.FONT_DIR.glob('Inter-*.ttf'))
    assert bundled, 'Inter must be bundled for Windows machines without that family'
    assert 'Inter' in family


def test_apply_application_is_idempotent():
    app = QApplication.instance() or QApplication([])
    assert board_theme.apply_application(app) is True
    assert board_theme.apply_application(app) is True
    assert board_theme.tokens()['background'] in app.styleSheet()
    assert '#boardFreeze' in app.styleSheet()


def test_teacher_chrome_uses_real_controls_and_freeze_chip(tmp_path):
    app = QApplication.instance() or QApplication([])
    media = MediaStore(tmp_path / 'media')
    store = BoardStore(tmp_path)
    session = BoardSession(demo_model(media), store=store, image_resolver=image_resolver(media))
    window = BoardCandidate(session, store=store, resolver=image_resolver(media))
    try:
        assert window.objectName() == 'boardTeacher'
        assert window.pupil.objectName() == 'boardPupilDisplay'
        assert window.freeze_button.objectName() == 'boardFreeze'
        assert window.resume_button.objectName() == 'boardResume'
        assert window.add_image_button.objectName() == 'boardPrimary'
        chrome = window._theme_chrome
        assert chrome['tool_rail'].objectName() == 'boardToolRail'
        for button in window.teacher_tools.values():
            assert button.parent() is chrome['tool_rail']
        assert window.freeze_button.text() == 'Freeze'
        assert window.resume_button.text() == 'Resume'
        assert 'PUPIL LIVE' in chrome['live_chip'].text()
        assert 'Page 1 of 3' in chrome['page_chip'].text()
        assert 'Evaporation' in chrome['page_chip'].text()
        window.freeze()
        assert chrome['live_chip'].text() == 'PUPIL FROZEN'
        assert window.freeze_button.property('frozen') == 'true'
        assert chrome['pupil_freeze_chip'].text() == 'FROZEN BY TEACHER'
        assert window.pupil_nav[0].isEnabled() is False
        window.resume()
        assert chrome['live_chip'].text() == 'PUPIL LIVE'
        assert window.pupil_nav[0].isEnabled() is True
        window.navigate(1)
        assert 'Page 2 of 3' in chrome['page_chip'].text()
        assert 'Condensation' in chrome['page_chip'].text()
    finally:
        window.save_timer.stop(); window.property_timer.stop(); window.group_timer.stop()
        window.session.close(); window.pupil.hide(); window.hide(); window.deleteLater()
        app.processEvents()


def test_image_picker_uses_the_same_theme(tmp_path):
    app = QApplication.instance() or QApplication([])
    media = MediaStore(tmp_path / 'media')
    store = BoardStore(tmp_path)
    session = BoardSession(demo_model(media), store=store, image_resolver=image_resolver(media))
    window = BoardCandidate(session, store=store, resolver=image_resolver(media))
    try:
        picker = ImagePicker(window, library_root=tmp_path / 'media', decoder=__import__('board_candidate').decode_image)
        assert picker.objectName() == 'boardDialog'
        assert picker.insert_button.objectName() == 'boardPrimary'
        assert picker.insert_button.text() == 'Insert on this page'
        picker.close()
    finally:
        window.save_timer.stop(); window.property_timer.stop(); window.group_timer.stop()
        window.session.close(); window.pupil.hide(); window.hide(); window.deleteLater()
        app.processEvents()


def test_swapping_tokens_rebuilds_the_sheet():
    original = board_theme.tokens()
    variant = dict(original, background='#12081a', primary_container='#f59e0b')
    sheet = board_theme.build_stylesheet(variant)
    assert '#12081a' in sheet
    assert '#f59e0b' in sheet
    assert original['primary_container'] not in sheet
