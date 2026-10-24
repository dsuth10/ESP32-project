from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "compose"))

import media_targets  # noqa: E402


def app_target(**overrides):
    result = {"hwnd": 100, "pid": 200, "executable": "WINWORD.EXE",
              "document": "C:/school/lesson.docx", "start": 14, "end": 14}
    result.update(overrides)
    return result


class Range:
    def __init__(self, start=14, end=14):
        self.Start = start
        self.End = end
        self.Duplicate = self

    @property
    def Duplicate(self):
        return self

    @Duplicate.setter
    def Duplicate(self, value):
        pass


def word_app(*, hwnd=100, document="C:/school/lesson.docx", start=14, end=14):
    selected = Range(start, end)
    picture = SimpleNamespace(Range=SimpleNamespace(Start=14))
    add_picture = Mock(return_value=picture)
    app = SimpleNamespace(
        ActiveWindow=SimpleNamespace(Hwnd=hwnd),
        ActiveDocument=SimpleNamespace(FullName=document, InlineShapes=SimpleNamespace(AddPicture=add_picture)),
        Selection=SimpleNamespace(Range=selected),
    )
    return app, add_picture, selected


@pytest.mark.parametrize("change", [
    {"hwnd": 101},
    {"pid": 201},
    {"executable": "ONENOTE.EXE"},
])
def test_insert_refuses_changed_foreground_window_identity(change, tmp_path):
    expected = app_target()
    changed = {**expected, **change}
    app, add_picture, _ = word_app()
    with patch.object(media_targets, "foreground_target", return_value=changed),          patch.object(media_targets, "_word", return_value=app):
        with pytest.raises(ValueError, match="Target changed"):
            media_targets.insert_image(tmp_path / "image.png", expected)
    add_picture.assert_not_called()


@pytest.mark.parametrize("state", [
    {"hwnd": 101},
    {"document": "C:/school/another.docx"},
    {"start": 15},
    {"end": 15},
])
def test_word_refuses_changed_window_document_or_caret(state, tmp_path):
    expected = app_target()
    app, add_picture, _ = word_app(**state)
    with patch.object(media_targets, "foreground_target", return_value=expected),          patch.object(media_targets, "_word", return_value=app):
        with pytest.raises(ValueError, match="document, caret or selection changed"):
            media_targets.insert_image(tmp_path / "image.png", expected)
    add_picture.assert_not_called()


def test_word_refuses_a_noncollapsed_selection_before_insertion(tmp_path):
    expected = app_target()
    app, add_picture, selected = word_app(start=14, end=19)
    with patch.object(media_targets, "foreground_target", return_value=expected),          patch.object(media_targets, "_word", return_value=app):
        with pytest.raises(ValueError, match="document, caret or selection changed"):
            media_targets.insert_image(tmp_path / "image.png", expected)
    add_picture.assert_not_called()
    assert (selected.Start, selected.End) == (14, 19)


def test_word_inserts_embedded_picture_at_duplicate_caret_without_replacing_selection(tmp_path):
    expected = app_target()
    app, add_picture, selected = word_app()
    image_path = tmp_path / "image.png"
    image_path.write_bytes(b"synthetic test placeholder")
    with patch.object(media_targets, "foreground_target", return_value=expected),          patch.object(media_targets, "_word", return_value=app):
        result = media_targets.insert_image(image_path, expected)
    kwargs = add_picture.call_args.kwargs
    assert kwargs["LinkToFile"] is False
    assert kwargs["SaveWithDocument"] is True
    assert kwargs["Range"] is selected.Duplicate
    assert kwargs["FileName"] == str(image_path.resolve())
    assert (selected.Start, selected.End) == (14, 14)
    assert result["transport"] == "word_com"
    assert result["verification"] == "office_object_returned"


def test_word_focus_change_between_selection_check_and_addpicture_aborts(tmp_path):
    expected = app_target()
    changed = {**expected, "pid": 999}
    app, add_picture, _ = word_app()
    with patch.object(media_targets, "foreground_target", side_effect=[expected, changed]),          patch.object(media_targets, "_word", return_value=app):
        with pytest.raises(ValueError, match="Target changed before insertion"):
            media_targets.insert_image(tmp_path / "image.png", expected)
    add_picture.assert_not_called()


def test_onenote_unknown_selection_fails_closed_during_capture():
    target = app_target(executable="ONENOTE.EXE")
    with patch.object(media_targets, "foreground_target", return_value=target),          patch.object(media_targets, "_onenote_selection_collapsed", return_value=None):
        with pytest.raises(ValueError, match="selection could not be verified"):
            media_targets.capture_target()


def test_explicit_onenote_paste_uses_native_canvas_when_selection_api_unavailable():
    target = app_target(executable="ONENOTE.EXE")
    context = {"focus_hwnd": 300, "window_title": "Synthetic page - OneNote"}
    with patch.object(media_targets, "foreground_target", return_value=target), \
         patch.object(media_targets, "_onenote_selection_collapsed", return_value=None), \
         patch.object(media_targets, "_onenote_keyboard_context", return_value=context, create=True):
        captured = media_targets.capture_target(allow_onenote_keyboard_paste=True)
    assert captured["explicit_keyboard_paste"] is True
    assert captured["selection_checked"] is False
    assert captured["keyboard_context"] == context


def test_explicit_onenote_paste_still_refuses_a_reported_selection():
    target=app_target(executable="ONENOTE.EXE")
    with patch.object(media_targets,"foreground_target",return_value=target), \
         patch.object(media_targets,"_onenote_selection_collapsed",return_value=False), \
         patch.object(media_targets,"_onenote_keyboard_context") as context:
        with pytest.raises(ValueError,match="Collapse the OneNote selection"):
            media_targets.capture_target(allow_onenote_keyboard_paste=True)
    context.assert_not_called()


def test_explicit_onenote_paste_refuses_noncanvas_focus():
    target=app_target(executable="ONENOTE.EXE")
    with patch.object(media_targets,"foreground_target",return_value=target), \
         patch.object(media_targets,"_onenote_selection_collapsed",return_value=None), \
         patch.object(media_targets,"_onenote_keyboard_context",side_effect=ValueError('Focus the OneNote page body')):
        with pytest.raises(ValueError,match="page body"):
            media_targets.capture_target(allow_onenote_keyboard_paste=True)


def keyboard_target():
    return app_target(executable="ONENOTE.EXE",selection_checked=False,
                      explicit_keyboard_paste=True,
                      keyboard_context={"focus_hwnd":300,"window_title":"Synthetic page - OneNote"})


def test_explicit_onenote_paste_sends_ctrl_v_once_with_unavailable_selection(tmp_path):
    target=keyboard_target()
    clipboard=SimpleNamespace(send_paste_shortcut=Mock())
    with patch.object(media_targets,"foreground_target",return_value=target), \
         patch.object(media_targets,"_onenote_selection_collapsed",return_value=None), \
         patch.object(media_targets,"_onenote_keyboard_context",return_value=target['keyboard_context']), \
         patch.object(media_targets,"copy_image") as copy, \
         patch.dict(sys.modules,{"clipboard_manager":clipboard}):
        receipt=media_targets.insert_image(tmp_path/'image.png',target)
    copy.assert_called_once_with(tmp_path/'image.png')
    clipboard.send_paste_shortcut.assert_called_once_with()
    assert receipt['verification']=='paste_requested'
    assert receipt['selection_verification']=='unavailable'


@pytest.mark.parametrize('change',[{'focus_hwnd':301},{'window_title':'Another page - OneNote'}])
def test_explicit_onenote_paste_rejects_changed_canvas_or_page_before_copy(tmp_path,change):
    target=keyboard_target()
    changed={**target['keyboard_context'],**change}
    with patch.object(media_targets,"foreground_target",return_value=target), \
         patch.object(media_targets,"_onenote_selection_collapsed",return_value=None), \
         patch.object(media_targets,"_onenote_keyboard_context",return_value=changed), \
         patch.object(media_targets,"copy_image") as copy:
        with pytest.raises(ValueError,match="page or focus changed"):
            media_targets.insert_image(tmp_path/'image.png',target)
    copy.assert_not_called()


def test_explicit_onenote_paste_rechecks_context_after_copy(tmp_path):
    target=keyboard_target()
    clipboard=SimpleNamespace(send_paste_shortcut=Mock())
    with patch.object(media_targets,"foreground_target",return_value=target), \
         patch.object(media_targets,"_onenote_selection_collapsed",return_value=None), \
         patch.object(media_targets,"_onenote_keyboard_context",side_effect=[target['keyboard_context'],{**target['keyboard_context'],'focus_hwnd':301}]), \
         patch.object(media_targets,"copy_image") as copy, \
         patch.dict(sys.modules,{"clipboard_manager":clipboard}):
        with pytest.raises(ValueError,match="copied but no paste"):
            media_targets.insert_image(tmp_path/'image.png',target)
    copy.assert_called_once()
    clipboard.send_paste_shortcut.assert_not_called()


def test_onenote_unknown_selection_never_copies_or_pastes(tmp_path):
    target = app_target(executable="ONENOTE.EXE", selection_checked=True)
    copy_image = Mock()
    with patch.object(media_targets, "foreground_target", return_value=target),          patch.object(media_targets, "_onenote_selection_collapsed", return_value=None),          patch.object(media_targets, "copy_image", copy_image):
        with pytest.raises(ValueError, match="selection could not be verified"):
            media_targets.insert_image(tmp_path / "image.png", target)
    copy_image.assert_not_called()


def test_onenote_focus_change_after_copy_never_sends_paste(tmp_path):
    target = app_target(executable="ONENOTE.EXE", selection_checked=True)
    changed = {**target, "hwnd": 101}
    copy_image = Mock()
    clipboard = SimpleNamespace(send_paste_shortcut=Mock())
    with patch.object(media_targets, "foreground_target", side_effect=[target, changed]),          patch.object(media_targets, "_onenote_selection_collapsed", return_value=True),          patch.object(media_targets, "copy_image", copy_image),          patch.dict(sys.modules, {"clipboard_manager": clipboard}):
        with pytest.raises(ValueError, match="Image was copied but no paste was sent"):
            media_targets.insert_image(tmp_path / "image.png", target)
    copy_image.assert_called_once_with(tmp_path / "image.png")
    clipboard.send_paste_shortcut.assert_not_called()
