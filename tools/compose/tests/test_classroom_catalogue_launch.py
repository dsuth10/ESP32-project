"""Unit tests for the MrSutherland.net classroom catalogue and allowlisted web launcher."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from classroom_catalogue import (
    ALLOWED_WEB_HOSTS,
    CatalogueItem,
    get_catalogue_item,
    is_allowlisted_web_url,
    load_classroom_catalogue,
)
from monitor_shortcut import (
    APP_BOARD,
    APP_CHROME,
    APP_ONENOTE,
    APP_WORD,
    KIND_LAUNCH_FAILED,
    KIND_MISSING_DISPLAY,
    KIND_OK,
    MISSING_DISPLAY_MESSAGE,
    WINDOW_MOST_RECENT,
    MonitorShortcutController,
)
from window_monitor_manager import (
    BOARD_PUPIL_TITLE,
    CHROME_EXECUTABLE,
    ONENOTE_EXECUTABLE,
    WORD_EXECUTABLE,
    AppWindow,
    FakeWindowMonitorBackend,
    MonitorInfo,
    Rect,
    Win32WindowMonitorBackend,
    is_allowlisted_launch,
)


def make_monitor(
    *,
    handle: int = 1,
    name: str = "Classroom panel",
    path: str = "\\\\?\\DISPLAY#ABC123",
    left: int = 1920,
    top: int = 0,
    right: int = 3840,
    bottom: int = 1080,
) -> MonitorInfo:
    bounds = Rect(left, top, right, bottom)
    return MonitorInfo(
        handle=handle,
        friendly_name=name,
        device_name="\\\\.\\DISPLAY2",
        device_path=path,
        edid_manufacturer="PRM",
        edid_product="0001",
        bounds=bounds,
        work_area=bounds,
        dpi=96,
        is_primary=False,
    )


def make_window(
    *,
    hwnd: int = 10,
    pid: int = 400,
    title: str = "MrSutherland.net",
    left: int = 0,
    top: int = 0,
    right: int = 800,
    bottom: int = 600,
    last: float | None = None,
    executable: str = CHROME_EXECUTABLE,
    show_state: str = "normal",
) -> AppWindow:
    return AppWindow(
        hwnd=hwnd,
        pid=pid,
        title=title,
        executable=executable,
        bounds=Rect(left, top, right, bottom),
        last_foreground_at=last,
        show_state=show_state,
    )


def make_controller(tmp_path: Path, backend: FakeWindowMonitorBackend, **profile_fields):
    popups: list[str] = []
    ctl = MonitorShortcutController(
        backend=backend,
        root=tmp_path,
        popup=popups.append,
        wait_timeout_s=0.1,
    )
    settings = ctl.load()
    settings["profiles"]["Home"].update(profile_fields)
    ctl.save(settings)
    return ctl, popups


def test_is_allowlisted_web_url_accepts_valid_mrsutherland_urls():
    assert ALLOWED_WEB_HOSTS == frozenset({"mrsutherland.net", "www.mrsutherland.net"})
    assert is_allowlisted_web_url("https://mrsutherland.net/")
    assert is_allowlisted_web_url("https://mrsutherland.net")
    assert is_allowlisted_web_url("https://www.mrsutherland.net/maths/fractions/")
    assert is_allowlisted_web_url("https://MRSUTHERLAND.NET/science/water-cycle/?mode=quiz#step1")
    assert is_allowlisted_web_url("https://mrsutherland.net:443/tools/timer/")


@pytest.mark.parametrize(
    "bad_url",
    [
        "",
        "   ",
        "http://mrsutherland.net/",
        "http://www.mrsutherland.net/maths/",
        "https://evil.com/",
        "https://mrsutherland.net.evil.com/",
        "https://sub.mrsutherland.net/",
        "https://user:pass@mrsutherland.net/",
        "https://user@mrsutherland.net/",
        "https://mrsutherland.net:8080/",
        "file:///C:/Windows/System32/calc.exe",
        "javascript:alert(1)",
        "https://mrsutherland.net/maths/ --remote-debugging-port=9222",
        "https://mrsutherland.net/maths/;calc.exe",
        "https://mrsutherland.net/maths/|calc",
        "https://mrsutherland.net/maths/&calc",
        "https://mrsutherland.net/maths/`id`",
        'https://mrsutherland.net/maths/"quote"',
        "https://mrsutherland.net/maths/\nhttps://evil.com",
        "https://mrsutherland.net/" + ("a" * 520),
    ],
)
def test_is_allowlisted_web_url_rejects_unsafe_or_foreign_urls(bad_url: str):
    assert not is_allowlisted_web_url(bad_url)


def test_catalogue_item_validation_and_serialisation():
    item = CatalogueItem(
        id="maths-command-station",
        title="Maths Command Station",
        category="Mathematics",
        url="https://mrsutherland.net/maths/",
        description="Interactive manipulatives.",
        tags=("maths", "numeracy"),
    )
    as_dict = item.as_dict()
    assert as_dict["id"] == "maths-command-station"
    assert as_dict["display_target"] == "chrome"
    assert as_dict["tags"] == ["maths", "numeracy"]

    with pytest.raises(ValueError, match="not allowlisted"):
        CatalogueItem(
            id="bad",
            title="Bad",
            category="Core",
            url="https://example.com/",
        )


def test_load_classroom_catalogue_default_and_local_overrides(tmp_path: Path):
    default_items = load_classroom_catalogue(local_override_path=tmp_path / "nonexistent.json")
    assert 6 <= len(default_items) <= 8
    ids = [item["id"] for item in default_items]
    assert "mrsutherland-home" in ids
    assert "maths-command-station" in ids
    for entry in default_items:
        assert is_allowlisted_web_url(entry["url"])
        assert entry["display_target"] == "chrome"

    override_path = tmp_path / "local_catalogue.json"
    override_payload = {
        "items": [
            {
                "id": "maths-command-station",
                "title": "Year 8 Maths Hub (Custom)",
                "category": "Mathematics",
                "url": "https://www.mrsutherland.net/maths/year8/",
                "description": "Custom local override for Year 8.",
                "display_target": "chrome",
                "tags": ["year8", "maths"],
            },
            {
                "id": "custom-robotics-lab",
                "title": "Robotics Challenge Board",
                "category": "Technologies",
                "url": "https://mrsutherland.net/technologies/robotics/",
                "description": "Added via local override.",
                "display_target": "chrome",
                "tags": ["robotics"],
            },
            {
                "id": "rejected-evil-entry",
                "title": "Untrusted Site",
                "category": "Other",
                "url": "https://evil.example.org/phish",
                "description": "Must be ignored safely.",
            },
        ]
    }
    override_path.write_text(json.dumps(override_payload), encoding="utf-8")

    merged = load_classroom_catalogue(local_override_path=override_path)
    merged_by_id = {item["id"]: item for item in merged}
    assert merged_by_id["maths-command-station"]["title"] == "Year 8 Maths Hub (Custom)"
    assert merged_by_id["maths-command-station"]["url"] == "https://www.mrsutherland.net/maths/year8/"
    assert "custom-robotics-lab" in merged_by_id
    assert "rejected-evil-entry" not in merged_by_id

    found = get_catalogue_item("custom-robotics-lab", local_override_path=override_path)
    assert found is not None
    assert found["title"] == "Robotics Challenge Board"
    assert get_catalogue_item("unknown-id", local_override_path=override_path) is None


def test_is_allowlisted_launch_accepts_chrome_with_mrsutherland_urls_and_profiles():
    assert is_allowlisted_launch("chrome.exe https://mrsutherland.net/maths/")
    assert is_allowlisted_launch("chrome.exe https://www.mrsutherland.net/science/water-cycle/", APP_CHROME)
    assert is_allowlisted_launch("chrome.exe --app=https://mrsutherland.net/tools/timer/")
    assert is_allowlisted_launch('chrome.exe --profile-directory="Default" https://mrsutherland.net/maths/')
    assert is_allowlisted_launch('chrome.exe --profile-directory="Profile 1" https://mrsutherland.net/maths/')
    assert is_allowlisted_launch("chrome.exe --profile-directory=Profile 1 https://mrsutherland.net/maths/")
    assert is_allowlisted_launch(
        'chrome.exe --profile-directory="Profile 1" --app=https://mrsutherland.net/tools/timer/'
    )
    assert is_allowlisted_launch(
        r'C:\Program Files\Google\Chrome\Application\chrome.exe --profile-directory="Default" https://mrsutherland.net/'
    )


@pytest.mark.parametrize(
    "bad_command",
    [
        "chrome.exe http://mrsutherland.net/maths/",
        "chrome.exe https://evil.com/",
        "chrome.exe --app=https://evil.com/",
        "chrome.exe --app=http://mrsutherland.net/",
        "chrome.exe file:///C:/Windows/win.ini",
        "chrome.exe javascript:alert(1)",
        "chrome.exe --remote-debugging-port=9222 https://mrsutherland.net/",
        'chrome.exe --profile-directory="Default" --remote-debugging-port=9222 https://mrsutherland.net/',
        'chrome.exe --profile-directory="Default" https://evil.com/',
        "WINWORD.EXE https://mrsutherland.net/",
        "ONENOTE.EXE https://mrsutherland.net/",
    ],
)
def test_is_allowlisted_launch_rejects_unapproved_urls_and_flags(bad_command: str):
    assert not is_allowlisted_launch(bad_command)
    assert not is_allowlisted_launch(bad_command, APP_CHROME)


def test_win32_backend_launch_application_preserves_profile_and_url():
    backend = Win32WindowMonitorBackend.__new__(Win32WindowMonitorBackend)
    with patch("window_monitor_manager._resolve_app_path", return_value=r"C:\Chrome\chrome.exe"), \
            patch("window_monitor_manager.os.path.isfile", side_effect=lambda p: p == r"C:\Chrome\chrome.exe"), \
            patch("subprocess.Popen") as popen:
        backend.launch_application('chrome.exe --profile-directory="Profile 1" https://mrsutherland.net/maths/')
        popen.assert_called_once_with(
            [
                r"C:\Chrome\chrome.exe",
                "--profile-directory=Profile 1",
                "https://mrsutherland.net/maths/",
            ],
            close_fds=True,
        )


def test_open_web_url_on_classroom_display_launches_and_places_chrome(tmp_path: Path):
    classroom = make_monitor()
    created_chrome = make_window(hwnd=210, title="Maths Command Station - Google Chrome")
    backend = FakeWindowMonitorBackend([classroom], [])
    backend.launch_window = created_chrome

    ctl, popups = make_controller(
        tmp_path,
        backend,
        classroom_display=classroom.identity_record(),
        last_seen_identities=[classroom.durable_key()],
        apps={
            APP_CHROME: {
                "window_choice": WINDOW_MOST_RECENT,
                "chosen_window": None,
                "maximise": True,
                "launch": 'chrome.exe --profile-directory="Teacher Profile"',
            }
        },
    )

    receipt = ctl.open_web_url_on_classroom_display(
        "https://mrsutherland.net/maths/",
        title="Maths Command Station",
    )
    assert receipt.kind == KIND_OK
    assert receipt.launched is True
    assert receipt.placed is True
    assert receipt.foreground is True
    assert receipt.app_id == APP_CHROME
    assert receipt.hwnd == 210
    assert receipt.granted_paste_permission is False
    assert receipt.paste_ready_target is False
    assert receipt.as_dict()["granted_paste_permission"] is False
    assert receipt.as_dict()["paste_ready_target"] is False
    assert popups == []
    assert backend.launch_calls == [
        'chrome.exe --profile-directory="Teacher Profile" https://mrsutherland.net/maths/'
    ]
    assert backend.place_calls == [(210, classroom.work_area.as_tuple(), True)]


def test_open_web_url_on_classroom_display_rejects_disallowed_url_and_missing_display(tmp_path: Path):
    classroom = make_monitor()
    backend = FakeWindowMonitorBackend([classroom], [])
    ctl, popups = make_controller(
        tmp_path,
        backend,
        classroom_display=classroom.identity_record(),
        last_seen_identities=[classroom.durable_key()],
    )

    bad_receipt = ctl.open_web_url_on_classroom_display("https://evil.example.com/", title="Bad")
    assert bad_receipt.kind == KIND_LAUNCH_FAILED
    assert bad_receipt.message == "Web lesson URL is not allowlisted."
    assert bad_receipt.app_id == APP_CHROME
    assert not bad_receipt.granted_paste_permission
    assert backend.launch_calls == []
    assert backend.place_calls == []

    # Now test missing classroom display with valid URL
    laptop = make_monitor(
        handle=2,
        name="Laptop",
        path="\\\\?\\DISPLAY#LAPTOP",
        left=0,
        top=0,
        right=1920,
        bottom=1080,
    )
    backend.monitors = [laptop]
    missing_receipt = ctl.open_web_url_on_classroom_display("https://mrsutherland.net/")
    assert missing_receipt.kind == KIND_MISSING_DISPLAY
    assert missing_receipt.message == MISSING_DISPLAY_MESSAGE
    assert popups == [MISSING_DISPLAY_MESSAGE]
    assert backend.launch_calls == []


def test_detect_active_classroom_target_identifies_active_window(tmp_path: Path):
    classroom = make_monitor(left=1920, top=0, right=3840, bottom=1080)
    laptop_win = make_window(
        hwnd=10,
        executable=ONENOTE_EXECUTABLE,
        left=100,
        top=100,
        right=900,
        bottom=700,
        last=50.0,
    )
    backend = FakeWindowMonitorBackend([classroom], [laptop_win])
    ctl, _ = make_controller(
        tmp_path,
        backend,
        classroom_display=classroom.identity_record(),
        last_seen_identities=[classroom.durable_key()],
    )

    # Only laptop window open -> classroom display has 'none'
    assert ctl.detect_active_classroom_target() == "none"

    # Place OneNote on classroom monitor
    onenote_cls = make_window(
        hwnd=20,
        executable=ONENOTE_EXECUTABLE,
        left=1920,
        top=0,
        right=3840,
        bottom=1080,
        last=10.0,
    )
    backend.windows.append(onenote_cls)
    assert ctl.detect_active_classroom_target() == APP_ONENOTE

    # Add Chrome on classroom monitor with newer last_foreground_at
    chrome_cls = make_window(
        hwnd=30,
        executable=CHROME_EXECUTABLE,
        left=1920,
        top=0,
        right=3840,
        bottom=1080,
        last=25.0,
    )
    backend.windows.append(chrome_cls)
    assert ctl.detect_active_classroom_target() == APP_CHROME

    # Word window on classroom monitor becomes current foreground
    word_cls = make_window(
        hwnd=40,
        executable=WORD_EXECUTABLE,
        left=1920,
        top=0,
        right=3840,
        bottom=1080,
        last=5.0,
    )
    backend.windows.append(word_cls)
    backend.set_foreground(40)
    assert ctl.detect_active_classroom_target() == APP_WORD

    # Board pupil window on classroom monitor becomes foreground
    pupil_cls = make_window(
        hwnd=50,
        title=BOARD_PUPIL_TITLE,
        executable="PYTHON.EXE",
        left=1920,
        top=0,
        right=3840,
        bottom=1080,
    )
    backend.windows.append(pupil_cls)
    backend.set_foreground(50)
    assert ctl.detect_active_classroom_target() == APP_BOARD
