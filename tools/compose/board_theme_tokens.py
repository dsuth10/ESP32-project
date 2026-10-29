"""Shared Teaching Board / companion colour tokens. No Qt import.

board_theme.py builds the Qt stylesheet from these values. Tk companion
screens (Voice companion, image library, Settings) use apply_tk() so a token
swap here restyles both toolkits. Never fetches fonts or assets from the
network.
"""
from __future__ import annotations

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
    'warning': '#f59e0b',
    'page': '#ffffff',
    'viewport': '#131b2e',
    'selection': '#22d3ee',
    'input_fill': '#060e20',
    'placeholder': '#859397',
}


def tokens():
    return dict(TOKENS)


def apply_tk(root, notebook=None):
    """Apply the same tokens to a Tk root and ttk widgets. No behaviour change."""
    from tkinter import ttk
    t = TOKENS
    try:
        root.configure(bg=t['background'])
    except Exception:
        pass
    style = ttk.Style(root)
    try:
        style.theme_use('clam')
    except Exception:
        pass
    style.configure('.', background=t['background'], foreground=t['on_surface'],
                    fieldbackground=t['input_fill'], bordercolor=t['outline_variant'],
                    darkcolor=t['surface_low'], lightcolor=t['surface_high'],
                    troughcolor=t['surface_lowest'])
    style.configure('TFrame', background=t['background'])
    style.configure('TLabel', background=t['background'], foreground=t['on_surface'])
    style.configure('TCheckbutton', background=t['background'], foreground=t['on_surface'],
                    focuscolor=t['primary_container'])
    style.configure('TRadiobutton', background=t['background'], foreground=t['on_surface'])
    style.configure('TButton', background=t['surface_highest'], foreground=t['on_surface'],
                    padding=(10, 6), borderwidth=1, focusthickness=1, focuscolor=t['primary'])
    style.map('TButton',
              background=[('active', t['primary_container']), ('pressed', t['primary'])],
              foreground=[('active', t['on_primary']), ('pressed', t['on_primary'])])
    style.configure('TEntry', fieldbackground=t['input_fill'], foreground=t['on_surface'],
                    insertcolor=t['on_surface'], padding=4)
    style.configure('TCombobox', fieldbackground=t['input_fill'], foreground=t['on_surface'],
                    background=t['surface_highest'], padding=4)
    style.map('TCombobox', fieldbackground=[('readonly', t['input_fill'])],
              foreground=[('readonly', t['on_surface'])])
    style.configure('TNotebook', background=t['background'], borderwidth=0)
    style.configure('TNotebook.Tab', background=t['surface_container'],
                    foreground=t['on_surface_variant'], padding=(14, 8), borderwidth=0)
    style.map('TNotebook.Tab',
              background=[('selected', t['primary_container'])],
              foreground=[('selected', t['on_primary'])])
    style.configure('Treeview', background=t['input_fill'], foreground=t['on_surface'],
                    fieldbackground=t['input_fill'], bordercolor=t['outline_variant'], rowheight=24)
    style.configure('Treeview.Heading', background=t['surface_high'], foreground=t['on_surface'],
                    relief='flat')
    style.map('Treeview',
              background=[('selected', t['primary_container'])],
              foreground=[('selected', t['on_primary'])])
    style.configure('TScrollbar', background=t['surface_highest'], troughcolor=t['surface_lowest'],
                    bordercolor=t['surface_lowest'], arrowcolor=t['on_surface_variant'])
    style.configure('TPanedwindow', background=t['background'])
    style.configure('TLabelframe', background=t['background'], foreground=t['on_surface'])
    style.configure('TLabelframe.Label', background=t['background'], foreground=t['primary'])
    style.configure('TMenubutton', background=t['surface_highest'], foreground=t['on_surface'],
                    padding=(10, 6), borderwidth=1)
    style.map('TMenubutton',
              background=[('active', t['primary_container'])],
              foreground=[('active', t['on_primary'])])
    style.configure('TSeparator', background=t['outline_variant'])
    style.configure('Horizontal.TProgressbar', background=t['primary_container'],
                    troughcolor=t['surface_highest'])
    style.configure('Vertical.TProgressbar', background=t['primary_container'],
                    troughcolor=t['surface_highest'])
    if notebook is not None:
        try:
            notebook.configure(style='TNotebook')
        except Exception:
            pass
    return t


def style_tk_text(widget):
    """Colour a Tk Text / ScrolledText from TOKENS. Leaves bindings and state alone."""
    t = TOKENS
    kwargs = dict(bg=t['input_fill'], fg=t['on_surface'], insertbackground=t['on_surface'],
                  selectbackground=t['primary_container'], selectforeground=t['on_primary'],
                  highlightbackground=t['outline_variant'], highlightcolor=t['primary'],
                  relief='flat')
    try:
        widget.configure(**kwargs)
    except Exception:
        kwargs.pop('insertbackground', None)
        widget.configure(**kwargs)
    return widget


def style_tk_canvas(widget):
    t = TOKENS
    widget.configure(bg=t['background'], highlightthickness=0)
    return widget


def style_tk_listbox(widget):
    t = TOKENS
    widget.configure(bg=t['input_fill'], fg=t['on_surface'],
                     selectbackground=t['primary_container'], selectforeground=t['on_primary'],
                     highlightbackground=t['outline_variant'], relief='flat')
    return widget


def style_tk_menu(menu):
    t = TOKENS
    menu.configure(bg=t['surface_high'], fg=t['on_surface'],
                   activebackground=t['primary_container'], activeforeground=t['on_primary'],
                   relief='flat')
    return menu
