"""Classroom display / OneNote placement — Linux-stub unit tests."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from monitor_shortcut import (
    AMBIGUOUS_WINDOWS_MESSAGE,
    CHOSEN_GONE_AMBIGUOUS_MESSAGE,
    DISPLAY_SET_CHANGED_MESSAGE,
    KIND_AMBIGUOUS,
    KIND_FOREGROUND_FAILED,
    KIND_MISSING_DISPLAY,
    KIND_NEEDS_CONFIRM,
    KIND_OK,
    KIND_PLACEMENT_FAILED,
    KIND_UNASSIGNED,
    KIND_WINDOW_GONE,
    MISSING_DISPLAY_MESSAGE,
    MonitorShortcutController,
    WINDOW_MOST_RECENT,
    match_classroom_monitor,
    resolve_onenote_window,
)
from window_monitor_manager import (
    AppWindow,
    FakeWindowMonitorBackend,
    MonitorInfo,
    Rect,
    is_allowlisted_launch,
    verify_placement,
)


def monitor(*, handle=1, name='Classroom panel', path='\\\\?\\DISPLAY#ABC123',
            edid_mfg='PRM', edid_product='0001', left=1920, top=0, right=3840, bottom=1080,
            dpi=96, work=None, primary=False, device_name='\\\\.\\DISPLAY2'):
    bounds = Rect(left, top, right, bottom)
    return MonitorInfo(
        handle=handle, friendly_name=name, device_name=device_name, device_path=path,
        edid_manufacturer=edid_mfg, edid_product=edid_product, bounds=bounds,
        work_area=work or bounds, dpi=dpi, is_primary=primary,
    )


def window(*, hwnd=10, pid=400, title='Year 8 — Water cycle', left=0, top=0, right=800, bottom=600,
           last=None, executable='ONENOTE.EXE'):
    return AppWindow(
        hwnd=hwnd, pid=pid, title=title, executable=executable,
        bounds=Rect(left, top, right, bottom), last_foreground_at=last,
    )


def assigned(item: MonitorInfo, last_seen=None) -> dict:
    record = item.identity_record()
    return record, list(last_seen if last_seen is not None else [item.durable_key()])


def test_allowlist_accepts_onenote_only():
    assert is_allowlisted_launch('onenote:')
    assert is_allowlisted_launch(r'C:\Program Files\Microsoft Office\root\Office16\ONENOTE.EXE')
    assert not is_allowlisted_launch('notepad.exe')
    assert not is_allowlisted_launch('cmd.exe /c calc')


def test_missing_classroom_display_is_an_exact_warning():
    classroom = monitor()
    saved, seen = assigned(classroom, last_seen=[classroom.durable_key()])
    status, found, message = match_classroom_monitor(saved, [monitor(
        handle=2, name='Laptop', path='\\\\?\\DISPLAY#LAPTOP', edid_mfg='LGD',
        edid_product='0099', left=0, top=0, right=1920, bottom=1080, device_name='\\\\.\\DISPLAY1',
        primary=True)], seen)
    assert status == KIND_MISSING_DISPLAY
    assert found is None
    assert message == MISSING_DISPLAY_MESSAGE


def test_unassigned_display_is_not_the_unplugged_warning():
    status, found, message = match_classroom_monitor(None, [monitor()])
    assert status == KIND_UNASSIGNED
    assert found is None
    assert message != MISSING_DISPLAY_MESSAGE


def test_vanished_device_path_does_not_reuse_another_same_model_edid():
    classroom = monitor(path='\\\\?\\DISPLAY#HOME', edid_mfg='DEL', edid_product='2719')
    other = monitor(handle=2, name='Other Dell', path='\\\\?\\DISPLAY#WORK',
                    edid_mfg='DEL', edid_product='2719', left=0, top=0, right=1920, bottom=1080,
                    device_name='\\\\.\\DISPLAY1', primary=True)
    saved, seen = assigned(classroom)
    status, found, message = match_classroom_monitor(saved, [other], seen)
    assert status == KIND_MISSING_DISPLAY
    assert found is None
    assert message == MISSING_DISPLAY_MESSAGE


def test_path_identity_matches_after_index_reorder():
    classroom = monitor(left=-1920, top=0, right=0, bottom=1080, device_name='\\\\.\\DISPLAY1')
    reordered = monitor(left=1920, top=0, right=3840, bottom=1080, device_name='\\\\.\\DISPLAY2')
    saved, seen = assigned(classroom)
    status, found, _ = match_classroom_monitor(saved, [reordered], seen)
    assert status == KIND_OK
    assert found.device_path == classroom.device_path


def test_bounds_fallback_requires_confirm_when_the_set_changes():
    home = monitor(path='', edid_mfg='', edid_product='', left=1920, top=0, right=3840, bottom=1080)
    saved = home.identity_record()
    seen = [home.durable_key(), 'path:old-laptop']
    same_bounds = monitor(handle=9, name='Unknown', path='', edid_mfg='', edid_product='',
                          left=1920, top=0, right=3840, bottom=1080, device_name='\\\\.\\DISPLAY3')
    status, found, message = match_classroom_monitor(saved, [same_bounds], seen)
    assert status == KIND_NEEDS_CONFIRM
    assert found == same_bounds
    assert message == DISPLAY_SET_CHANGED_MESSAGE


def test_bounds_fallback_matches_when_the_set_is_unchanged():
    home = monitor(path='', edid_mfg='', edid_product='', left=1920, top=0, right=3840, bottom=1080)
    saved = home.identity_record()
    status, found, message = match_classroom_monitor(saved, [home], [home.durable_key()])
    assert status == KIND_OK
    assert found is home
    assert message == ''


def test_most_recent_default_uses_last_foreground_window():
    older = window(hwnd=11, title='Older notebook', last=10)
    newer = window(hwnd=12, title='Newer notebook', last=50)
    status, chosen, warning = resolve_onenote_window(
        {'onenote_window_choice': WINDOW_MOST_RECENT}, [older, newer], foreground_hwnd=0)
    assert status == KIND_OK
    assert chosen.hwnd == 12
    assert warning == ''


def test_most_recent_prefers_the_current_foreground_onenote_window():
    older = window(hwnd=11, title='Older notebook', last=10)
    newer = window(hwnd=12, title='Newer notebook', last=50)
    status, chosen, _ = resolve_onenote_window(
        {'onenote_window_choice': WINDOW_MOST_RECENT}, [older, newer], foreground_hwnd=11)
    assert chosen.hwnd == 11


def test_most_recent_refuses_to_guess_when_recency_is_unknown():
    first = window(hwnd=11, title='Notebook A')
    second = window(hwnd=12, title='Notebook B')
    status, chosen, message = resolve_onenote_window(
        {'onenote_window_choice': WINDOW_MOST_RECENT}, [first, second])
    assert status == KIND_AMBIGUOUS
    assert chosen is None
    assert message == AMBIGUOUS_WINDOWS_MESSAGE


def test_chosen_window_is_reused_when_still_present():
    target = window(hwnd=21, pid=9, title='Chosen page')
    other = window(hwnd=22, pid=9, title='Other page', last=99)
    profile = {
        'onenote_window_choice': 'chosen',
        'chosen_window': {'hwnd': 21, 'pid': 9, 'title': 'Chosen page', 'executable': 'ONENOTE.EXE'},
    }
    status, chosen, warning = resolve_onenote_window(profile, [target, other])
    assert status == KIND_OK
    assert chosen.hwnd == 21
    assert warning == ''


def test_chosen_window_gone_with_several_left_does_not_guess():
    remaining = [window(hwnd=31, title='A'), window(hwnd=32, title='B')]
    profile = {
        'onenote_window_choice': 'chosen',
        'chosen_window': {'hwnd': 99, 'pid': 1, 'title': 'Gone', 'executable': 'ONENOTE.EXE'},
    }
    status, chosen, message = resolve_onenote_window(profile, remaining)
    assert status == KIND_AMBIGUOUS
    assert chosen is None
    assert message == CHOSEN_GONE_AMBIGUOUS_MESSAGE


def test_chosen_window_gone_with_one_left_falls_back_with_message():
    remaining = window(hwnd=31, title='Only notebook')
    profile = {
        'onenote_window_choice': 'chosen',
        'chosen_window': {'hwnd': 99, 'pid': 1, 'title': 'Gone', 'executable': 'ONENOTE.EXE'},
    }
    status, chosen, message = resolve_onenote_window(profile, [remaining])
    assert status == KIND_OK
    assert chosen.hwnd == 31
    assert 'no longer open' in message


def test_title_alone_does_not_identify_onenote():
    fake = window(hwnd=40, title='Year 8 — Water cycle', executable='WINWORD.EXE')
    status, chosen, _ = resolve_onenote_window({'onenote_window_choice': WINDOW_MOST_RECENT}, [fake])
    assert chosen is None


def controller(tmp_path, backend, **profile_fields):
    popups = []
    ctl = MonitorShortcutController(backend=backend, root=tmp_path, popup=popups.append, wait_timeout_s=0.1)
    settings = ctl.load()
    settings['profiles']['Home'].update(profile_fields)
    ctl.save(settings)
    return ctl, popups


def test_open_warns_and_moves_nothing_when_display_is_missing(tmp_path):
    classroom = monitor()
    laptop = monitor(handle=2, name='Laptop', path='\\\\?\\DISPLAY#LAPTOP', edid_mfg='LGD',
                     edid_product='0099', left=0, top=0, right=1920, bottom=1080, primary=True,
                     device_name='\\\\.\\DISPLAY1')
    note = window(hwnd=50, left=10, top=10, right=700, bottom=500)
    backend = FakeWindowMonitorBackend([laptop], [note])
    ctl, popups = controller(tmp_path, backend, classroom_display=classroom.identity_record(),
                             last_seen_identities=[classroom.durable_key()])
    receipt = ctl.open_onenote_on_classroom_display()
    assert receipt.kind == KIND_MISSING_DISPLAY
    assert receipt.message == MISSING_DISPLAY_MESSAGE
    assert popups == [MISSING_DISPLAY_MESSAGE]
    assert backend.place_calls == []
    assert backend.launch_calls == []
    assert not receipt.granted_paste_permission
    assert not receipt.paste_ready_target


def test_find_existing_onenote_and_place_into_negative_work_area(tmp_path):
    classroom = monitor(left=-1920, top=0, right=0, bottom=1080, work=Rect(-1920, 0, 0, 1040))
    note = window(hwnd=60, left=100, top=80, right=900, bottom=700, last=5)
    backend = FakeWindowMonitorBackend([classroom], [note])
    ctl, _ = controller(tmp_path, backend, classroom_display=classroom.identity_record(),
                        last_seen_identities=[classroom.durable_key()], maximise=True)
    receipt = ctl.open_onenote_on_classroom_display()
    assert receipt.kind == KIND_OK
    assert receipt.placed and receipt.foreground
    assert receipt.launched is False
    assert backend.place_calls == [(60, (-1920, 0, 0, 1040), True)]
    assert note.bounds.as_tuple() == (-1920, 0, 0, 1040)
    assert verify_placement(note.bounds, classroom.work_area)


def test_launch_only_when_no_onenote_is_running(tmp_path):
    classroom = monitor()
    created = window(hwnd=70, title='Fresh OneNote')
    backend = FakeWindowMonitorBackend([classroom], [])
    backend.launch_window = created
    ctl, _ = controller(tmp_path, backend, classroom_display=classroom.identity_record(),
                        last_seen_identities=[classroom.durable_key()])
    receipt = ctl.open_onenote_on_classroom_display()
    assert receipt.kind == KIND_OK
    assert receipt.launched is True
    assert backend.launch_calls == ['onenote:']
    assert receipt.hwnd == 70


def test_does_not_launch_when_a_window_already_exists(tmp_path):
    classroom = monitor()
    note = window(hwnd=80)
    backend = FakeWindowMonitorBackend([classroom], [note])
    ctl, _ = controller(tmp_path, backend, classroom_display=classroom.identity_record(),
                        last_seen_identities=[classroom.durable_key()])
    ctl.open_onenote_on_classroom_display()
    assert backend.launch_calls == []


def test_hwnd_dying_during_placement_is_a_clear_failure(tmp_path):
    classroom = monitor()
    note = window(hwnd=90)
    backend = FakeWindowMonitorBackend([classroom], [note])
    backend.die_during_place = True
    ctl, _ = controller(tmp_path, backend, classroom_display=classroom.identity_record(),
                        last_seen_identities=[classroom.durable_key()])
    receipt = ctl.open_onenote_on_classroom_display()
    assert receipt.kind == KIND_WINDOW_GONE
    assert receipt.placed is False
    assert 'closed' in receipt.message.lower()


def test_foreground_failure_is_reported_separately_from_placement(tmp_path):
    classroom = monitor()
    note = window(hwnd=91)
    backend = FakeWindowMonitorBackend([classroom], [note])
    backend.fail_foreground = True
    ctl, _ = controller(tmp_path, backend, classroom_display=classroom.identity_record(),
                        last_seen_identities=[classroom.durable_key()])
    receipt = ctl.open_onenote_on_classroom_display()
    assert receipt.kind == KIND_FOREGROUND_FAILED
    assert receipt.placed is True
    assert receipt.foreground is False
    assert backend.place_calls


def test_placement_failure_does_not_request_foreground(tmp_path):
    classroom = monitor()
    note = window(hwnd=92)
    backend = FakeWindowMonitorBackend([classroom], [note])
    backend.fail_place = True
    ctl, _ = controller(tmp_path, backend, classroom_display=classroom.identity_record(),
                        last_seen_identities=[classroom.durable_key()])
    receipt = ctl.open_onenote_on_classroom_display()
    assert receipt.kind == KIND_PLACEMENT_FAILED
    assert backend.foreground_requests == []


def test_profiles_keep_separate_classroom_mappings(tmp_path):
    home = monitor(name='Home screen', path='\\\\?\\DISPLAY#HOME')
    work = monitor(name='Work panel', path='\\\\?\\DISPLAY#WORK', left=0, top=-1080, right=1920, bottom=0)
    backend = FakeWindowMonitorBackend([work], [window(hwnd=15)])
    ctl, popups = controller(tmp_path, backend, classroom_display=home.identity_record(),
                             last_seen_identities=[home.durable_key()])
    settings = ctl.load()
    settings['active_profile'] = 'Work'
    settings['profiles']['Work']['classroom_display'] = work.identity_record()
    settings['profiles']['Work']['last_seen_identities'] = [work.durable_key()]
    ctl.save(settings)
    receipt = ctl.open_onenote_on_classroom_display()
    assert receipt.kind == KIND_OK
    assert receipt.profile == 'Work'
    assert popups == []
    settings['active_profile'] = 'Home'
    ctl.save(settings)
    missing = ctl.open_onenote_on_classroom_display()
    assert missing.kind == KIND_MISSING_DISPLAY
    assert popups == [MISSING_DISPLAY_MESSAGE]


def test_maximise_defaults_on_and_can_be_disabled(tmp_path):
    classroom = monitor()
    note = window(hwnd=16)
    backend = FakeWindowMonitorBackend([classroom], [note])
    ctl, _ = controller(tmp_path, backend, classroom_display=classroom.identity_record(),
                        last_seen_identities=[classroom.durable_key()], maximise=False)
    ctl.open_onenote_on_classroom_display()
    assert backend.place_calls[0][2] is False


def test_receipt_never_marks_paste_ready_or_insert_permission(tmp_path):
    classroom = monitor()
    backend = FakeWindowMonitorBackend([classroom], [window(hwnd=17)])
    ctl, _ = controller(tmp_path, backend, classroom_display=classroom.identity_record(),
                        last_seen_identities=[classroom.durable_key()])
    receipt = ctl.open_onenote_on_classroom_display()
    payload = receipt.as_dict()
    assert payload['granted_paste_permission'] is False
    assert payload['paste_ready_target'] is False
    assert receipt.granted_paste_permission is False
