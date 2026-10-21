"""Local companion setup; secrets are masked and stored with Windows DPAPI."""
import tkinter as tk
from tkinter import ttk

from companion_settings import save_settings


class SettingsPanel(ttk.Frame):
    def __init__(self, parent, config, before_save, after_save, post_ui):
        super().__init__(parent)
        self.before_save = before_save
        self.after_save = after_save
        self.post_ui = post_ui
        self._saving = False
        self._closed = False
        self.values = {}
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        content = ttk.Frame(canvas, padding=14)
        content.columnconfigure(1, weight=1)
        window_id = canvas.create_window((0, 0), window=content, anchor='nw')
        content.bind('<Configure>', lambda _event: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(window_id, width=event.width))
        ttk.Label(content, text='Credentials and network settings stay on this computer.',
                  wraplength=800).grid(row=0, column=0, columnspan=2, sticky='w', pady=8)
        entries = [('GROQ_API_KEY', 'Groq key (primary embedded assistant)', True, ''),
                   ('HERMES_URL', 'Private Hermes service URL', False, ''),
                   ('HERMES_TOKEN', 'Hermes bearer token (separate from media server)', True, ''),
                   ('MEDIA_SERVER_URL', 'Private media server URL', False, ''),
                   ('MEDIA_SERVER_TOKEN', 'Media server bearer token (separate from Hermes)', True, ''),
                   ('OPENAI_API_KEY', 'OpenAI image provider key', True, ''),
                   ('IMAGE_MODEL', 'Image model', False, 'gpt-image-2.5-sunburst'),
                   ('IMAGE_ESTIMATE_AUD_CENTS', 'Conservative allocation per image attempt (AUD cents)', False, '')]
        row = 1
        for key, label, secret, default in entries:
            ttk.Label(content, text=label).grid(row=row, column=0, sticky='w', padx=4, pady=5)
            var = tk.StringVar(value=config.get(key, default))
            self.values[key] = var
            ttk.Entry(content, textvariable=var, show='•' if secret else '').grid(
                row=row, column=1, sticky='ew', pady=5)
            row += 1
        flags = [('HERMES_ENABLED', 'Enable the separate Hermes task panel', '0'),
                 ('MEDIA_SYNC_ENABLED', 'Synchronise media automatically with my private server', '0'),
                 ('IMAGE_GENERATION_ENABLED', 'Enable paid image requests when I press Generate (shared budget required)', '0'),
                 ('LOCAL_ONLY', 'Local-only providers; disables Groq, Hermes, media sync, web and image providers', '0'),
                 ('ESP32_ENABLE_HOTKEYS', 'Enable handheld/keyboard hotkeys in this feature app (restart required)', '0'),
                 ('ESP32_START_RECEIVER', 'Start a voice receiver from this feature app (restart required)', '0')]
        for key, label, default in flags:
            var = tk.BooleanVar(value=str(config.get(key, default)).lower() in ('1', 'true', 'yes'))
            self.values[key] = var
            ttk.Checkbutton(content, text=label, variable=var).grid(
                row=row, column=0, columnspan=2, sticky='w', pady=4)
            row += 1
        ttk.Label(content, text='A$30/month is the pilot design allowance on the shared server. Allocations are estimates, not provider invoice amounts.\n'
                  'A failed or ambiguous dispatched attempt retains its allocation until reconciled. No paid request runs during setup.',
                  wraplength=800).grid(row=row, column=0, columnspan=2, sticky='w', pady=8)
        row += 1
        ttk.Button(content, text='Save and apply settings', command=self.save).grid(row=row, column=0, sticky='w')
        row += 1
        self.status = ttk.Label(content, text='Hermes and media sync are not configured.', wraplength=800, justify='left')
        self.status.grid(row=row, column=0, columnspan=2, sticky='ew', pady=8)

    def save(self):
        if self._saving:
            return
        values = {key: ('1' if var.get() else '0') if isinstance(var, tk.BooleanVar)
                  else var.get().strip() for key, var in self.values.items()}
        try:
            amount = values['IMAGE_ESTIMATE_AUD_CENTS']
            if amount and (not amount.isdecimal() or not 1 <= int(amount) <= 3000):
                raise ValueError('Set a per-attempt allocation from 1 to 3000 AUD cents, or leave it empty while generation is disabled.')
            if values['IMAGE_GENERATION_ENABLED'] == '1' and not amount:
                raise ValueError('Configure the per-attempt allocation before enabling paid images.')
            self._saving = True
            self.status.configure(text='Checking active work and protecting settings…')
            # Keep a new request from starting between the busy-state check and
            # the asynchronous service/configuration commit.
            try:
                self.grab_set()
            except tk.TclError:
                pass
            import threading
            threading.Thread(target=self._save_worker, args=(values,), daemon=True).start()
        except ValueError as error:
            self.status.configure(text=str(error))
        except Exception:
            self.status.configure(text='Settings could not be applied. Finish current operations and check protected storage access. No keys were logged.')

    def _save_worker(self, values):
        rollback = None
        try:
            # The Hermes unresolved-run check and protected disk writes run away
            # from Tk. Nothing is persisted until the service accepts the change.
            rollback = self.before_save(values)
            save_settings(values)
            error = None
        except ValueError as exc:
            error = str(exc)
        except Exception:
            error = 'Settings could not be applied. Finish current operations and check protected storage access. No keys were logged.'
        if error and rollback:
            try:
                rollback()
            except Exception:
                pass
        if not self._closed:
            self.post_ui(self._save_finished, values, error)

    def _save_finished(self, values, error):
        self._saving = False
        try:
            self.grab_release()
        except tk.TclError:
            pass
        if error:
            self.status.configure(text=error)
            return
        try:
            self.after_save(values)
        except Exception:
            self.status.configure(text='Settings were protected, but an application feature could not be refreshed. Restart the companion to apply them.')

    def set_status(self, text):
        self.status.configure(text=text)

    def close(self):
        self._closed = True
        try:
            self.grab_release()
        except tk.TclError:
            pass
