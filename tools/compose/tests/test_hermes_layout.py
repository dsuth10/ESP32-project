"""Native regression: Hermes actions must remain usable at supported sizes."""
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
import tkinter as tk
from tkinter import ttk

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hermes_panel import HermesPanel


@pytest.mark.parametrize("width,height", [(720,640),(920,740)])
def test_all_hermes_actions_fit_inside_nested_notebook(width,height):
    try:
        root=tk.Tk()
    except tk.TclError as error:
        pytest.skip("Native Tk display unavailable: " + str(error))
    try:
        root.attributes("-alpha",0)
        root.geometry(f"{width}x{height}")
        outer=ttk.Notebook(root)
        outer.pack(fill="both",expand=True,padx=8,pady=8)
        page=ttk.Frame(outer)
        outer.add(page,text="Ask your companion")
        inner=ttk.Notebook(page)
        inner.pack(fill="both",expand=True)
        tab=ttk.Frame(inner)
        inner.add(tab,text="Hermes tasks")
        panel=HermesPanel(tab,None,lambda *_:None,Mock(),lambda:False,lambda:False,lambda:True)
        panel.pack(fill="both",expand=True)
        root.update()
        for name in ("submit_button","stop_button","discard_button","queue_button"):
            widget=getattr(panel,name)
            left=widget.winfo_rootx()-root.winfo_rootx()
            top=widget.winfo_rooty()-root.winfo_rooty()
            assert widget.winfo_width() >= 70, name
            assert 0 <= left and left+widget.winfo_width() <= width, name
            assert 0 <= top and top+widget.winfo_height() <= height, name
    finally:
        root.destroy()
