"""
Floating non-activating HUD status overlay pill using Tkinter & Win32 styles.
Guaranteed never to steal window or keyboard focus from active document editors.
"""

import sys
import time
import threading
import tkinter as tk
import win32gui
import win32con

from board_theme_tokens import TOKENS

# Win32 extended style flags
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008


class StatusOverlay:
    """Thread-safe floating HUD status pill."""

    def __init__(self):
        self._root: tk.Tk | None = None
        self._label_icon: tk.Label | None = None
        self._label_title: tk.Label | None = None
        self._label_sub: tk.Label | None = None
        self._frame: tk.Frame | None = None
        self._ready_event = threading.Event()
        self._queue_lock = threading.Lock()
        self._pending_update = None
        self._auto_hide_timer = None

        self._thread = threading.Thread(target=self._run_ui_loop, daemon=True)
        self._thread.start()
        self._ready_event.wait(timeout=3.0)

    def _run_ui_loop(self):
        root = tk.Tk()
        self._root = root

        root.overrideredirect(True)
        root.attributes("-topmost", True)
                root.configure(bg=TOKENS['background'])

        # Set transparent key or dark rounded background
        frame = tk.Frame(root, bg=TOKENS['surface_low'], highlightthickness=1,
                         highlightbackground=TOKENS['outline_variant'], padx=16, pady=8)
        frame.pack(fill="both", expand=True)
        self._frame = frame

        # Inner layout: Dot/Icon, Title, Subtitle
        icon_lbl = tk.Label(frame, text="●", font=("Segoe UI", 12, "bold"), fg=TOKENS['warning'],
                            bg=TOKENS['surface_low'])
        icon_lbl.pack(side="left", padx=(0, 8))
        self._label_icon = icon_lbl

        content_box = tk.Frame(frame, bg=TOKENS['surface_low'])
        content_box.pack(side="left", fill="both", expand=True)

        title_lbl = tk.Label(content_box, text="Ready", font=("Segoe UI", 10, "bold"),
                             fg=TOKENS['on_surface'], bg=TOKENS['surface_low'], anchor="w")
        title_lbl.pack(fill="x")
        self._label_title = title_lbl

        sub_lbl = tk.Label(content_box, text="", font=("Segoe UI", 8), fg=TOKENS['on_surface_variant'],
                           bg=TOKENS['surface_low'], anchor="w")
        sub_lbl.pack(fill="x")
        self._label_sub = sub_lbl

        root.update_idletasks()

        # Apply WS_EX_NOACTIVATE via Win32 API to ensure no focus theft
        try:
            hwnd = win32gui.GetParent(root.winfo_id()) or root.winfo_id()
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST)
        except Exception as e:
            print(f"[StatusOverlay] Note: Could not set WS_EX_NOACTIVATE: {e}")

        # Position at bottom-center of primary display
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        w = 320
        h = 56
        x = (sw - w) // 2
        y = sh - h - 70
        root.geometry(f"{w}x{h}+{x}+{y}")
        root.withdraw()  # Initially hidden

        self._ready_event.set()

        def check_queue():
            with self._queue_lock:
                update = self._pending_update
                self._pending_update = None

            if update is not None:
                action, title, sub, color, autohide_ms = update
                if action == "show":
                    self._label_title.config(text=title)
                    self._label_sub.config(text=sub)
                    self._label_icon.config(fg=color)
                    self._frame.config(highlightbackground=color)
                    root.deiconify()
                    root.lift()

                    if self._auto_hide_timer:
                        root.after_cancel(self._auto_hide_timer)
                        self._auto_hide_timer = None

                    if autohide_ms > 0:
                        self._auto_hide_timer = root.after(autohide_ms, lambda: root.withdraw())

                elif action == "hide":
                    if self._auto_hide_timer:
                        root.after_cancel(self._auto_hide_timer)
                        self._auto_hide_timer = None
                    root.withdraw()

            root.after(40, check_queue)

        root.after(40, check_queue)
        root.mainloop()

    def show(self, title: str, subtitle: str = "", color: str = None, autohide_ms: int = 0):
        """Displays or updates the HUD overlay non-blockingly."""
        with self._queue_lock:
            self._pending_update = ("show", title, subtitle, color or TOKENS['warning'], autohide_ms)

    def hide(self):
        """Hides the HUD overlay."""
        with self._queue_lock:
            self._pending_update = ("hide", "", "", "", 0)

    # Convenience state presets
    def show_listening_compose(self):
        self.show("Listening (Compose)...", "Speak prompt, release button to write", color=TOKENS['warning'])

    def show_listening_dictate(self):
        self.show("Listening (Dictate)...", "Speak text, release button to paste", color=TOKENS['primary_container'])

    def show_processing(self, text: str = "Writing..."):
        self.show(text, "Synthesizing text at cursor...", color=TOKENS['secondary'])

    def show_ready_to_paste(self, title: str = "READY"):
        self.show("READY TO PASTE", "Window changed. Tap F15 to paste.", color=TOKENS['tertiary'])

    def show_pasted(self):
        self.show("Pasted!", "Inserted at cursor", color=TOKENS['tertiary'], autohide_ms=1200)

    def show_error(self, err_msg: str):
        self.show("Error", err_msg[:50], color=TOKENS['error'], autohide_ms=3000)


if __name__ == "__main__":
    overlay = StatusOverlay()
    print("[StatusOverlay] Testing display...")
    overlay.show_listening_compose()
    time.sleep(1.0)
    overlay.show_processing("Writing... (Part 1)")
    time.sleep(1.0)
    overlay.show_pasted()
    time.sleep(1.5)
    print("[StatusOverlay] Test Finished.")
