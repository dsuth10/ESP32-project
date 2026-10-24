"""Native layout and masking at both supported companion window sizes."""
import sys
from pathlib import Path
from unittest.mock import Mock

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
        assert 'rendering unavailable' in panel.image_status.cget('text')
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
        assert str(panel.generate_button.cget('state')) == 'disabled'
        assert 'pending implementation' in panel.generate_button.cget('text')
    finally:
        root.destroy()
