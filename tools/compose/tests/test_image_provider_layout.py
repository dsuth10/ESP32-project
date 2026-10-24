"""Native layout and masking at both supported companion window sizes."""
import sys
from pathlib import Path
from unittest.mock import Mock
import queue
import threading
import time

import pytest
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_panel import MediaPanel
from media_service import MediaService
from media_store import MediaStore
from settings_panel import SettingsPanel


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


@pytest.mark.parametrize('width,height', [(920, 740), (720, 640)])
def test_image_settings_masks_key_and_keeps_save_reachable(width, height):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Native Tk display unavailable')
    try:
        root.attributes('-alpha', 0)
        root.geometry(f'{width}x{height}')
        notebook = ttk.Notebook(root)
        notebook.pack(fill='both', expand=True, padx=8, pady=8)
        panel = SettingsPanel(notebook, {'IMAGE_PROVIDER': 'gemini', 'GOOGLE_IMAGE_API_KEY': 'synthetic-key'},
                              Mock(), Mock(), Mock())
        notebook.add(panel, text='Settings')
        root.update()
        key_var = str(panel.values['GOOGLE_IMAGE_API_KEY'])
        entry = next(w for w in descendants(panel) if isinstance(w, ttk.Entry)
                     and str(w.cget('textvariable')) == key_var)
        assert entry.cget('show') == '•'
        assert entry.winfo_rootx() + entry.winfo_width() <= root.winfo_rootx() + width
        assert 'Adapter: ready' in panel.image_status.cget('text')
        for widget in descendants(panel):
            if isinstance(widget, ttk.Label) and widget.cget('text') == 'Hermes bearer token (separate from media server)':
                assert widget.winfo_reqheight() > 20  # The long label wraps instead of clipping.
        canvas = next(w for w in panel.winfo_children() if isinstance(w, tk.Canvas))
        canvas.yview_moveto(1)
        root.update()
        save = next(w for w in descendants(panel) if isinstance(w, ttk.Button)
                    and w.cget('text') == 'Save and apply settings')
        assert root.winfo_rooty() <= save.winfo_rooty()
        assert save.winfo_rooty() + save.winfo_height() <= root.winfo_rooty() + height
    finally:
        root.destroy()


@pytest.mark.parametrize('width,height', [(920, 740), (720, 640)])
def test_gemini_wait_keeps_ui_responsive_and_records_display_timing(tmp_path, width, height):
    from gemini_images import GeminiImageProvider
    from test_gemini_images import session, Response, CONFIG
    entered, release = threading.Event(), threading.Event()
    transport = session()
    def post(*_args, **_kwargs):
        entered.set()
        if not release.wait(4):raise TimeoutError('Synthetic test wait expired')
        return Response()
    transport.post.side_effect = post
    events = queue.Queue()
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Native Tk display unavailable')
    panel = None
    try:
        root.attributes('-alpha', 0)
        root.geometry(f'{width}x{height}')
        service = MediaService(MediaStore(tmp_path), CONFIG, Mock(),
                               provider=GeminiImageProvider('synthetic-key', session=transport))
        panel = MediaPanel(root, service, lambda callback,*args:events.put((callback,args)), Mock(), Mock())
        panel.pack(fill='both', expand=True)
        panel.prepare(prompt='Synthetic diagram')
        prepared = panel.prepared_job
        panel.generate()
        heartbeat = []
        root.after(20, lambda:heartbeat.append(True))
        def pump_until(predicate, seconds):
            deadline = time.monotonic() + seconds
            while not predicate() and time.monotonic() < deadline:
                while not events.empty():
                    callback,args = events.get();callback(*args)
                root.update()
                time.sleep(.01)
            assert predicate()
        pump_until(lambda:entered.is_set() and bool(heartbeat), 2)
        pump_until(lambda:'Requesting image' in panel.notice.cget('text') and 'elapsed' in panel.notice.cget('text'), 2)
        assert 'does not cancel' in panel.notice.cget('text')
        assert panel._busy
        assert service.store.get_job(prepared)['phase'] == 'acquiring'
        release.set()
        pump_until(lambda:not panel._busy, 3)
        root.update()
        job = service.store.get_job(prepared)
        assert job['phase'] == 'preview_ready'
        assert job['button_to_preview_seconds'] >= job['provider_receipt']['round_trip_seconds']
        assert 'Google Gemini' in panel.details.cget('text')
        assert 'button to preview' in panel.details.cget('text')
        assert bool(panel.preview.cget('image'))
        assert panel.preview.winfo_height() >= 24
        panel.on_queue.assert_not_called()
        assert transport.post.call_count == 1
    finally:
        release.set()
        if panel is not None:panel.close()
        root.destroy()


@pytest.mark.parametrize('width,height', [(920, 740), (720, 640)])
def test_frozen_choice_and_image_actions_fit_nested_media_page(tmp_path, width, height):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Native Tk display unavailable')
    try:
        root.attributes('-alpha', 0)
        root.geometry(f'{width}x{height}')
        outer = ttk.Notebook(root)
        outer.pack(fill='both', expand=True, padx=8, pady=8)
        page = ttk.Frame(outer)
        outer.add(page, text='Ask your companion')
        inner = ttk.Notebook(page)
        inner.pack(fill='both', expand=True)
        tab = ttk.Frame(inner)
        inner.add(tab, text='Image library')
        service = MediaService(MediaStore(tmp_path), {'IMAGE_ESTIMATE_AUD_CENTS': '100'})
        panel = MediaPanel(tab, service, Mock(), Mock(), Mock())
        panel.pack(fill='both', expand=True)
        panel.prepare(prompt='Synthetic diagram')
        root.update()
        assert 'OpenAI' in panel.prepared_choice.cget('text')
        for widget in descendants(panel):
            if isinstance(widget, (ttk.Button, ttk.Menubutton)):
                assert widget.winfo_rootx() + widget.winfo_width() <= root.winfo_rootx() + width
                assert widget.winfo_rooty() + widget.winfo_height() <= root.winfo_rooty() + height
        assert panel.jobs.winfo_rooty() + panel.jobs.winfo_height() <= root.winfo_rooty() + height
        assert panel.preview.winfo_height() >= 60
        service.config['IMAGE_PROVIDER'] = 'gemini'
        panel.prepare(prompt='Another synthetic diagram')
        assert str(panel.generate_button.cget('state')) == 'normal'
        assert 'Google Gemini' in panel.prepared_choice.cget('text')
    finally:
        root.destroy()
