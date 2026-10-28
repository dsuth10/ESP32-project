"""Teacher host lifecycle and real synthetic Windows child-window checks."""
import ctypes
from ctypes import wintypes
import io
import os
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget
from PySide6.QtCore import QEvent
from PySide6.QtTest import QTest
import companion_host
from companion_host import CompanionHost, direct_python_executable, native_window_owned_by


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


class FakeProcess:
    pid = 98765

    def __init__(self):
        self.stdin = io.BytesIO()
        self.returncode = None

    def poll(self):
        return self.returncode


@pytest.fixture
def host(app, tmp_path):
    pane = CompanionHost(tmp_path / 'profile')
    yield pane
    pane._timer.stop()
    pane.hide()
    pane.deleteLater()
    app.processEvents()


def test_unready_child_vetoes_close_and_released_live_child_cannot_restart(host, monkeypatch):
    process = FakeProcess()
    host.process = process
    results = []
    host.closePrepared.connect(lambda ready, reason: results.append((ready, reason)))
    host.prepare_close()
    assert results[-1][0] is False
    host._released = True
    monkeypatch.setattr(companion_host.subprocess, 'Popen', lambda *args, **kwargs: pytest.fail('Duplicate child launched'))
    host.start()
    assert host.process is process
    assert 'still open' in host.notice.text()


def test_pending_text_uses_consent_signal_without_cancelling_preflight(host):
    host.process = FakeProcess()
    host._ready = True
    prepared, codes = [], []
    host.closePrepared.connect(lambda ready, reason: prepared.append((ready, reason)))
    host.closeBlockedCode.connect(codes.append)
    host.prepare_close()
    request_id = host._close_request
    host._receive({'type': 'close_blocked', 'request_id': request_id, 'code': 'pending_text', 'reason': 'Queued text'})
    assert codes == ['pending_text']
    assert prepared == []
    host.prepare_close(discard_queued_text=True)
    assert b'"discard_queued_text":true' in host.process.stdin.getvalue()


def test_stale_close_reply_ignored_and_commit_send_failure_vetoes(host):
    process = FakeProcess()
    host.process = process
    host._ready = True
    results = []
    host.closePrepared.connect(lambda ready, reason: results.append((ready, reason)))
    host.prepare_close()
    host._receive({'type': 'close_ready', 'request_id': 'another-request'})
    assert results == []
    host._receive({'type': 'close_ready', 'request_id': host._close_request})
    assert results == [(True, '')]
    process.stdin.close()
    host.commit_close()
    assert results[-1][0] is False


def test_commit_timeout_keeps_board_open_without_killing_child(host, monkeypatch):
    process = FakeProcess()
    host.process = process
    host._ready = True
    results = []
    host.closePrepared.connect(lambda ready, reason: results.append((ready, reason)))
    host.prepare_close()
    host.commit_close()
    host._commit_deadline = time.monotonic() - 1
    host._poll()
    assert results[-1][0] is False
    assert host.is_running
    assert host._close_request is None


def test_activation_restores_only_a_ready_visible_companion(host, app):
    host.process = FakeProcess(); host._ready = True
    host.show(); app.processEvents()
    host.process.stdin = io.BytesIO()
    host.eventFilter(host.window(), QEvent(QEvent.Type.WindowActivate))
    app.processEvents()
    assert b'"restore_input_focus"' in host.process.stdin.getvalue()
    host.hide(); app.processEvents()
    before = host.process.stdin.getvalue()
    host._request_input_focus()
    assert host.process.stdin.getvalue() == before
    host._ready = False; host.show(); app.processEvents()
    before = host.process.stdin.getvalue()
    host._request_input_focus()
    assert host.process.stdin.getvalue() == before


def test_native_identity_rejects_wrong_process_and_invalid_values(app):
    if os.name != 'nt':
        pytest.skip('Windows native windows')
    window = QMainWindow()
    hwnd = int(window.winId())
    assert native_window_owned_by(hwnd, os.getpid())
    assert not native_window_owned_by(hwnd, os.getpid() + 1)
    assert not native_window_owned_by(True, os.getpid())
    assert not native_window_owned_by(-1, os.getpid())
    window.deleteLater()


@pytest.mark.skipif(os.name != 'nt', reason='Windows venv redirector')
def test_venv_launch_retains_selected_environment_without_an_extra_process(tmp_path):
    base = tmp_path / 'base-python.exe'
    base.write_bytes(b'synthetic interpreter identity')
    selected = tmp_path / 'env' / 'Scripts' / 'python.exe'
    selected.parent.mkdir(parents=True)
    selected.write_bytes(b'synthetic redirector identity')
    (selected.parent.parent / 'pyvenv.cfg').write_text(f'executable = {base.resolve()}\n')
    environment = {}
    assert direct_python_executable(selected, environment) == str(base.resolve())
    assert environment['__PYVENV_LAUNCHER__'] == str(selected.resolve())
    base.unlink()
    with pytest.raises(ValueError, match='base interpreter'):
        direct_python_executable(selected, {})


SYNTHETIC_CHILD = '''
import ctypes,json,os,queue,sys,threading,tkinter as tk
root=tk.Tk();root.overrideredirect(True);root.geometry('720x640');root.update();root.withdraw()
root.configure(bg='#19ad73');tk.Label(root,text='Synthetic retained companion controls').pack()
root.update_idletasks();u=ctypes.windll.user32;u.GetAncestor.restype=ctypes.c_void_p
hwnd=int(u.GetAncestor(root.winfo_id(),2));commands=queue.Queue();prepared=None
def emit(value): print(json.dumps(value),flush=True)
def reader():
 for line in sys.stdin:
  commands.put(json.loads(line))
def drain():
 global prepared
 while not commands.empty():
  value=commands.get();kind=value.get('type');request=value.get('request_id')
  if kind=='attached': root.withdraw();root.deiconify();root.update_idletasks()
  elif kind=='prepare_close':
   prepared=request;emit({'type':'close_ready','request_id':request})
  elif kind=='cancel_close': prepared=None
  elif kind=='commit_close' and request==prepared:
   emit({'type':'closed','request_id':request});root.destroy();return
 emit({'type':'status','recording':False,'busy':False});root.after(30,drain)
threading.Thread(target=reader,daemon=True).start();root.after(30,drain)
emit({'type':'ready','pid':os.getpid(),'hwnd':hwnd});root.mainloop()
'''


def wait_until(app, predicate, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        QTest.qWait(20)
    assert predicate(), 'Native child did not reach its expected state'


@pytest.mark.skipif(os.name != 'nt', reason='Native Windows embedding')
def test_real_child_is_embedded_resized_and_shuts_down_after_two_phase_close(app, tmp_path, monkeypatch):
    child = tmp_path / 'synthetic_child.py'
    child.write_text(SYNTHETIC_CHILD, encoding='utf-8')
    popen = companion_host.subprocess.Popen

    def synthetic_popen(arguments, **kwargs):
        arguments[2] = str(child.resolve())
        return popen(arguments, **kwargs)

    monkeypatch.setattr(companion_host.subprocess, 'Popen', synthetic_popen)
    window = QMainWindow()
    pane = CompanionHost(tmp_path / 'profile')
    tabs = QTabWidget()
    board = QWidget()
    tabs.addTab(board, 'Teaching Board')
    tabs.addTab(pane, 'Voice companion')
    window.setCentralWidget(tabs)
    window.resize(1000, 800)
    window.show()
    try:
        pane.start()
        try:
            wait_until(app, lambda: pane.is_ready)
        except AssertionError:
            pytest.fail(f'{pane.notice.text()} (exit={pane.process.poll() if pane.process else None})')
        user = ctypes.WinDLL('user32', use_last_error=True)
        user.IsChild.argtypes = [wintypes.HWND, wintypes.HWND]
        user.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        assert tabs.currentWidget() is board
        tabs.setCurrentWidget(pane)
        wait_until(app, lambda: user.IsChild(int(window.winId()), pane._hwnd))
        wait_until(app, lambda: user.IsWindowVisible(pane._hwnd))
        before = wintypes.RECT()
        user.GetClientRect(pane._hwnd, ctypes.byref(before))
        window.resize(1200, 900)
        QTest.qWait(100)
        after = wintypes.RECT()
        user.GetClientRect(pane._hwnd, ctypes.byref(after))
        assert after.right > before.right
        tabs.setCurrentWidget(board)
        wait_until(app, lambda: not user.IsWindowVisible(pane._hwnd))
        tabs.setCurrentWidget(pane)
        wait_until(app, lambda: bool(user.IsWindowVisible(pane._hwnd)))
        assert user.IsChild(int(window.winId()), pane._hwnd)
        ready = []
        pane.closePrepared.connect(lambda ok, reason: ready.append(ok))
        pane.prepare_close()
        wait_until(app, lambda: ready == [True])
        assert pane.process.poll() is None, 'Preflight must preserve the child'
        pane.cancel_close()
        pane.prepare_close()
        wait_until(app, lambda: ready == [True, True])
        pane.commit_close()
        wait_until(app, lambda: pane.process.poll() is not None)
        assert pane.process.returncode == 0
        assert not user.IsWindow(pane._hwnd)
    finally:
        if pane.process and pane.process.poll() is None:
            # Only this synthetic, work-free fixture may be forcibly cleaned up.
            pane.process.terminate()
            pane.process.wait(timeout=5)
        pane._timer.stop()
        window.close()
        window.deleteLater()
        app.processEvents()


FOCUS_CHILD = '''
import ctypes,json,os,queue,sys,threading,tkinter as tk
from tkinter import ttk
sys.path.insert(0,__COMPOSE__)
from companion_embedded import EmbeddedInputFocus
root=tk.Tk();root.withdraw();root.geometry('720x640')
plain=ttk.Entry(root);plain.pack();masked=ttk.Entry(root,show='*');masked.pack()
handover={'plain':0,'masked':0}
for name,entry in [('plain',plain),('masked',masked)]:
 original=entry.focus_force
 def force(name=name,original=original):
  handover[name]+=1;original()
 entry.focus_force=force
focus=EmbeddedInputFocus(root)
root.overrideredirect(True);root.update_idletasks()
u=ctypes.windll.user32;u.GetAncestor.restype=ctypes.c_void_p
hwnd=int(u.GetAncestor(root.winfo_id(),2));commands=queue.Queue()
def emit(v):print(json.dumps(v),flush=True)
def reader():
 for line in sys.stdin:commands.put(json.loads(line))
 commands.put({'type':'eof'})
def drain():
 while not commands.empty():
  value=commands.get();kind=value.get('type')
  if kind=='attached':root.withdraw();root.deiconify();root.update_idletasks()
  elif kind=='probe_inputs':
   checks={}
   for name,entry in [('plain',plain),('masked',masked)]:
    entry.event_generate('<ButtonPress-1>',x=4,y=4)
    entry.event_generate('<ButtonRelease-1>',x=4,y=4);root.update()
    checks[name+'_focused']=root.focus_get()==entry
    checks[name+'_native_handover']=handover[name]>0
    for key in 'dog':entry.event_generate('<KeyPress-'+key+'>')
    root.update();checks[name+'_typed']=entry.get()=='dog'
   emit({'type':'input_probe','checks':checks})
  elif kind=='eof':focus.close();root.destroy();return
 root.after(30,drain)
threading.Thread(target=reader,daemon=True).start();root.after(30,drain)
emit({'type':'ready','pid':os.getpid(),'hwnd':hwnd});root.mainloop()
'''


@pytest.mark.skipif(os.name != 'nt', reason='Native Windows hosted input')
def test_hosted_clicks_reach_native_focus_handover_before_synthetic_keys(app, tmp_path, monkeypatch):
    child = tmp_path / 'hosted_input_child.py'
    child.write_text(FOCUS_CHILD.replace('__COMPOSE__', repr(str(Path(__file__).resolve().parents[1]))), encoding='utf-8')
    popen = companion_host.subprocess.Popen
    def synthetic_popen(arguments, **kwargs):
        arguments[2] = str(child.resolve())
        return popen(arguments, **kwargs)
    monkeypatch.setattr(companion_host.subprocess, 'Popen', synthetic_popen)
    window = QMainWindow()
    pane = CompanionHost(tmp_path / 'profile')
    window.setCentralWidget(pane); window.resize(1000, 800)
    results = []
    receive = pane._receive
    def observe(value):
        if value.get('type') == 'input_probe':
            results.append(value['checks'])
        else:
            receive(value)
    pane._receive = observe
    window.show(); window.activateWindow()
    try:
        pane.start()
        wait_until(app, lambda: pane.is_ready)
        pane._send({'type': 'probe_inputs'})
        wait_until(app, lambda: bool(results))
        assert results == [{'plain_focused': True, 'plain_native_handover': True, 'plain_typed': True,
                            'masked_focused': True, 'masked_native_handover': True, 'masked_typed': True}]
    finally:
        pane._release_on_host_exit()
        if pane.process:
            pane.process.wait(timeout=5)
        pane._timer.stop(); window.close(); window.deleteLater()
        app.processEvents()
