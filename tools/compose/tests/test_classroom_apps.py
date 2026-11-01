"""Classroom app registry: OneNote, Word, Chrome and Board. Linux stubs only."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from monitor_shortcut import (
    AMBIGUOUS_WINDOWS_MESSAGE,
    APP_CHROME,
    APP_ONENOTE,
    APP_WORD,
    BOARD_UNAVAILABLE_MESSAGE,
    CHOSEN_GONE_AMBIGUOUS_MESSAGE,
    KIND_AMBIGUOUS,
    KIND_BOARD_UNAVAILABLE,
    KIND_MISSING_DISPLAY,
    KIND_OK,
    MISSING_DISPLAY_MESSAGE,
    WINDOW_MOST_RECENT,
    FakeBoardPupilTarget,
    MonitorShortcutController,
    resolve_app_window,
)
from window_monitor_manager import (
    BOARD_PUPIL_TITLE,
    CHROME_EXECUTABLE,
    WORD_EXECUTABLE,
    AppWindow,
    FakeWindowMonitorBackend,
    MonitorInfo,
    Rect,
    is_allowlisted_launch,
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


def window(*, hwnd=10, pid=400, title='Document', left=0, top=0, right=800, bottom=600,
           last=None, executable='ONENOTE.EXE', show_state='normal'):
    return AppWindow(
        hwnd=hwnd, pid=pid, title=title, executable=executable,
        bounds=Rect(left, top, right, bottom), last_foreground_at=last,
        show_state=show_state,
    )


def assigned(item: MonitorInfo):
    return item.identity_record(), [item.durable_key()]


def controller(tmp_path, backend, board_target=None, **profile_fields):
    popups = []
    ctl = MonitorShortcutController(
        backend=backend, root=tmp_path, popup=popups.append, wait_timeout_s=0.1,
        board_target=board_target)
    settings = ctl.load()
    settings['profiles']['Home'].update(profile_fields)
    ctl.save(settings)
    return ctl, popups


def test_allowlist_accepts_onenote_word_chrome_and_optional_chrome_profile():
    assert is_allowlisted_launch('onenote:')
    assert is_allowlisted_launch(r'C:\Program Files\Microsoft Office\root\Office16\ONENOTE.EXE')
    assert is_allowlisted_launch(r'C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE')
    assert is_allowlisted_launch('WINWORD.EXE', APP_WORD)
    assert is_allowlisted_launch(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    assert is_allowlisted_launch('chrome.exe --profile-directory=Default')
    assert is_allowlisted_launch('chrome.exe --profile-directory="Profile 1"')
    assert not is_allowlisted_launch('notepad.exe')
    assert not is_allowlisted_launch('cmd.exe /c calc')
    assert not is_allowlisted_launch('chrome.exe --kiosk')
    assert not is_allowlisted_launch('chrome.exe --profile-directory=Default --kiosk')
    assert not is_allowlisted_launch(r'C:\Windows\System32\cmd.exe')
    assert not is_allowlisted_launch('WINWORD.EXE', APP_CHROME)
    assert not is_allowlisted_launch('onenote:', APP_WORD)


def _choice_cases(app_id, executable, label):
    older = window(hwnd=11, title=f'Older {label}', last=10, executable=executable)
    newer = window(hwnd=12, title=f'Newer {label}', last=50, executable=executable)
    profile = {'apps': {app_id: {'window_choice': WINDOW_MOST_RECENT, 'chosen_window': None,
                                 'maximise': True, 'launch': executable}}}
    if app_id == APP_ONENOTE:
        profile['onenote_window_choice'] = WINDOW_MOST_RECENT
    status, chosen, warning = resolve_app_window(app_id, profile, [older, newer])
    assert status == KIND_OK and chosen.hwnd == 12 and warning == ''

    status, chosen, warning = resolve_app_window(app_id, profile, [older, newer], foreground_hwnd=11)
    assert chosen.hwnd == 11

    first = window(hwnd=21, title=f'{label} A', executable=executable)
    second = window(hwnd=22, title=f'{label} B', executable=executable)
    status, chosen, message = resolve_app_window(app_id, profile, [first, second])
    assert status == KIND_AMBIGUOUS and chosen is None
    if app_id == APP_ONENOTE:
        assert message == AMBIGUOUS_WINDOWS_MESSAGE
    else:
        assert f'Several {label} windows are open' in message

    target = window(hwnd=31, pid=9, title=f'Chosen {label}', executable=executable)
    other = window(hwnd=32, pid=9, title=f'Other {label}', last=99, executable=executable)
    chosen_profile = {
        'apps': {app_id: {
            'window_choice': 'chosen',
            'chosen_window': {'hwnd': 31, 'pid': 9, 'title': target.title, 'executable': executable},
            'maximise': True, 'launch': executable,
        }},
    }
    if app_id == APP_ONENOTE:
        chosen_profile['onenote_window_choice'] = 'chosen'
        chosen_profile['chosen_window'] = chosen_profile['apps'][app_id]['chosen_window']
    status, chosen, warning = resolve_app_window(app_id, chosen_profile, [target, other])
    assert status == KIND_OK and chosen.hwnd == 31 and warning == ''

    remaining = [window(hwnd=41, title='A', executable=executable),
                 window(hwnd=42, title='B', executable=executable)]
    gone = {
        'apps': {app_id: {
            'window_choice': 'chosen',
            'chosen_window': {'hwnd': 99, 'pid': 1, 'title': 'Gone', 'executable': executable},
            'maximise': True, 'launch': executable,
        }},
    }
    if app_id == APP_ONENOTE:
        gone['onenote_window_choice'] = 'chosen'
        gone['chosen_window'] = gone['apps'][app_id]['chosen_window']
    status, chosen, message = resolve_app_window(app_id, gone, remaining)
    assert status == KIND_AMBIGUOUS and chosen is None
    if app_id == APP_ONENOTE:
        assert message == CHOSEN_GONE_AMBIGUOUS_MESSAGE

    only = window(hwnd=51, title=f'Only {label}', executable=executable)
    status, chosen, message = resolve_app_window(app_id, gone, [only])
    assert status == KIND_OK and chosen.hwnd == 51
    assert 'no longer open' in message


def test_window_choice_onenote_word_and_chrome():
    _choice_cases(APP_ONENOTE, 'ONENOTE.EXE', 'OneNote')
    _choice_cases(APP_WORD, WORD_EXECUTABLE, 'Word')
    _choice_cases(APP_CHROME, CHROME_EXECUTABLE, 'Chrome')


def test_chrome_without_last_used_time_asks_and_does_not_guess():
    first = window(hwnd=11, title='School', executable=CHROME_EXECUTABLE)
    second = window(hwnd=12, title='Personal', executable=CHROME_EXECUTABLE)
    status, chosen, message = resolve_app_window(
        APP_CHROME, {'apps': {APP_CHROME: {'window_choice': WINDOW_MOST_RECENT}}}, [first, second])
    assert status == KIND_AMBIGUOUS
    assert chosen is None
    assert message == (
        'Several Chrome windows are open. Choose one in Classroom display, '
        'or bring the intended window to the front once.')


def test_find_launch_and_most_recent_for_each_office_app(tmp_path):
    classroom = monitor()
    for app_id, executable, title, launch in (
            (APP_ONENOTE, 'ONENOTE.EXE', 'Notebook', 'onenote:'),
            (APP_WORD, WORD_EXECUTABLE, 'Essay.docx', 'WINWORD.EXE'),
            (APP_CHROME, CHROME_EXECUTABLE, 'Year 8 tab', 'chrome.exe')):
        existing = window(hwnd=80 + hash(app_id) % 50, title=title, executable=executable, last=3)
        backend = FakeWindowMonitorBackend([classroom], [existing])
        fields = {'classroom_display': classroom.identity_record(),
                  'last_seen_identities': [classroom.durable_key()]}
        if app_id != APP_ONENOTE:
            fields['apps'] = {app_id: {'window_choice': WINDOW_MOST_RECENT, 'chosen_window': None,
                                       'maximise': True, 'launch': launch}}
        ctl, _ = controller(tmp_path / app_id / 'find', backend, **fields)
        receipt = ctl.open_app_on_classroom_display(app_id)
        assert receipt.kind == KIND_OK
        assert receipt.launched is False
        assert backend.launch_calls == []
        assert backend.place_calls[0][2] is True

        created = window(hwnd=180 + hash(app_id) % 50, title=f'Fresh {title}', executable=executable)
        empty = FakeWindowMonitorBackend([classroom], [])
        empty.launch_window = created
        ctl, _ = controller(tmp_path / app_id / 'launch', empty, **fields)
        launched = ctl.open_app_on_classroom_display(app_id)
        assert launched.kind == KIND_OK
        assert launched.launched is True
        assert empty.launch_calls == [launch]


def test_word_and_chrome_refuse_non_allowlisted_launch(tmp_path):
    classroom = monitor()
    backend = FakeWindowMonitorBackend([classroom], [])
    ctl, _ = controller(
        tmp_path, backend, classroom_display=classroom.identity_record(),
        last_seen_identities=[classroom.durable_key()],
        apps={
            APP_WORD: {'window_choice': WINDOW_MOST_RECENT, 'chosen_window': None,
                       'maximise': True, 'launch': 'notepad.exe'},
        })
    settings = ctl.load()
    assert settings['profiles']['Home']['apps'][APP_WORD]['launch'] == 'WINWORD.EXE'
    backend.launch_window = window(hwnd=9, title='Doc', executable=WORD_EXECUTABLE)
    receipt = ctl.open_app_on_classroom_display(APP_WORD)
    assert receipt.kind == KIND_OK
    assert backend.launch_calls == ['WINWORD.EXE']


def test_missing_classroom_display_warns_for_every_app_including_board(tmp_path):
    classroom = monitor()
    laptop = monitor(handle=2, name='Laptop', path='\\\\?\\DISPLAY#LAPTOP', edid_mfg='LGD',
                     edid_product='0099', left=0, top=0, right=1920, bottom=1080, primary=True,
                     device_name='\\\\.\\DISPLAY1')
    target = FakeBoardPupilTarget()
    backend = FakeWindowMonitorBackend([laptop], [
        window(hwnd=50, executable='ONENOTE.EXE'),
        window(hwnd=51, executable=WORD_EXECUTABLE),
        window(hwnd=52, executable=CHROME_EXECUTABLE),
        window(hwnd=53, title=BOARD_PUPIL_TITLE, executable='PYTHON.EXE'),
    ])
    ctl, popups = controller(
        tmp_path, backend, board_target=target,
        classroom_display=classroom.identity_record(),
        last_seen_identities=[classroom.durable_key()])
    for app_id, action in (
            (APP_ONENOTE, ctl.open_onenote_on_classroom_display),
            (APP_WORD, lambda: ctl.open_app_on_classroom_display(APP_WORD)),
            (APP_CHROME, lambda: ctl.open_app_on_classroom_display(APP_CHROME)),
            ('board', ctl.bring_board_to_classroom_display)):
        receipt = action()
        assert receipt.kind == KIND_MISSING_DISPLAY
        assert receipt.message == MISSING_DISPLAY_MESSAGE
        assert receipt.app_id == app_id
        assert not receipt.granted_paste_permission
        assert not receipt.paste_ready_target
    assert popups == [MISSING_DISPLAY_MESSAGE] * 4
    assert backend.place_calls == []
    assert backend.launch_calls == []
    assert target.place_calls == []


def test_board_bring_forward_shows_hidden_pupil_and_leaves_frozen_snapshot(tmp_path):
    classroom = monitor()
    snapshot = {
        'frozen': True, 'page_id': 'page-9', 'revision': 4, 'token': 'freeze-token',
        'document': {'title': 'Pinned lesson', 'pages': [{'id': 'page-9'}]},
    }
    target = FakeBoardPupilTarget(visible=False, snapshot=snapshot)
    backend = FakeWindowMonitorBackend([classroom], [
        window(hwnd=60, title='Notebook', executable='ONENOTE.EXE', last=9),
    ])
    ctl, popups = controller(
        tmp_path, backend, board_target=target,
        classroom_display=classroom.identity_record(),
        last_seen_identities=[classroom.durable_key()])
    before = target.pupil_snapshot()
    receipt = ctl.bring_board_to_classroom_display()
    assert receipt.kind == KIND_OK
    assert receipt.app_id == 'board'
    assert not receipt.granted_paste_permission
    assert not receipt.paste_ready_target
    assert popups == []
    assert target.visible is True
    assert target.show_checked is True
    assert target.place_calls == [(classroom.work_area.as_tuple(), classroom.durable_key())]
    assert target.raise_calls == 1
    assert target.navigate_calls == 0
    assert target.freeze_calls == 0
    assert target.resume_calls == 0
    assert target.pupil_snapshot() == before
    assert backend.place_calls == []


def test_board_live_bring_forward_does_not_change_content(tmp_path):
    classroom = monitor()
    snapshot = {
        'frozen': False, 'page_id': 'page-1', 'revision': 2, 'token': 'live',
        'document': {'title': 'Live lesson'},
    }
    target = FakeBoardPupilTarget(snapshot=snapshot)
    backend = FakeWindowMonitorBackend([classroom], [])
    ctl, _ = controller(
        tmp_path, backend, board_target=target,
        classroom_display=classroom.identity_record(),
        last_seen_identities=[classroom.durable_key()])
    before = target.pupil_snapshot()
    receipt = ctl.bring_board_to_classroom_display()
    assert receipt.kind == KIND_OK
    assert target.pupil_snapshot() == before
    assert target.navigate_calls == 0


def test_board_unavailable_when_teaching_board_is_not_running(tmp_path):
    classroom = monitor()
    backend = FakeWindowMonitorBackend([classroom], [])
    ctl, _ = controller(
        tmp_path, backend, classroom_display=classroom.identity_record(),
        last_seen_identities=[classroom.durable_key()])
    receipt = ctl.bring_board_to_classroom_display()
    assert receipt.kind == KIND_BOARD_UNAVAILABLE
    assert receipt.message == BOARD_UNAVAILABLE_MESSAGE
    assert backend.place_calls == []


def test_board_window_path_places_existing_pupil_without_hiding_office(tmp_path):
    classroom = monitor()
    note = window(hwnd=70, title='Notebook', executable='ONENOTE.EXE', left=1920, top=0, right=3840, bottom=1080)
    pupil = window(hwnd=71, title=BOARD_PUPIL_TITLE, executable='PYTHON.EXE', show_state='hidden')
    backend = FakeWindowMonitorBackend([classroom], [note, pupil])
    ctl, _ = controller(
        tmp_path, backend, classroom_display=classroom.identity_record(),
        last_seen_identities=[classroom.durable_key()])
    receipt = ctl.bring_board_to_classroom_display()
    assert receipt.kind == KIND_OK
    assert backend.show_calls == [71]
    assert backend.place_calls == [(71, classroom.work_area.as_tuple(), False)]
    assert note.alive is True
    assert backend.launch_calls == []
