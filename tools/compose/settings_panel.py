"""Local companion setup; secrets are masked and stored with Windows DPAPI."""
import tkinter as tk
from tkinter import ttk

from companion_settings import save_settings
from image_provider_config import (PROVIDER_LABELS, OPENAI_MODEL, GOOGLE_MODEL,
                                   selected_provider, selected_model, image_readiness, image_snapshot, uncapped_images)
from board_resource_policy import board_image_readiness
from board_theme_tokens import TOKENS, style_tk_canvas


class SettingsPanel(ttk.Frame):
    def __init__(self, parent, config, before_save, after_save, post_ui):
        super().__init__(parent)
        self.before_save = before_save
        self.after_save = after_save
        self.post_ui = post_ui
        self._saving = False
        self._closed = False
        self._checking = False
        self._image_revision = 0
        self.values = {}
        canvas = tk.Canvas(self, highlightthickness=0, bg=TOKENS['background'])
        style_tk_canvas(canvas)
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
        initial_provider = config.get('IMAGE_PROVIDER') or 'openai'
        self.values['IMAGE_PROVIDER'] = tk.StringVar(value=initial_provider)
        entries = [('GROQ_API_KEY', 'Groq key (primary embedded assistant)', True, ''),
                   ('HERMES_URL', 'Private Hermes service URL', False, ''),
                   ('HERMES_TOKEN', 'Hermes bearer token (separate from media server)', True, ''),
                   ('MEDIA_SERVER_URL', 'Private media server URL', False, ''),
                   ('MEDIA_SERVER_TOKEN', 'Media server bearer token (separate from Hermes)', True, ''),
                   ('OPENAI_API_KEY', 'OpenAI image provider key', True, ''),
                   ('GOOGLE_IMAGE_API_KEY', 'Google image API key', True, ''),
                   ('IMAGE_MODEL', 'OpenAI model (exact identifier)', False, OPENAI_MODEL),
                   ('GOOGLE_IMAGE_MODEL', 'Google model (exact identifier)', False, GOOGLE_MODEL),
                   ('IMAGE_ESTIMATE_AUD_CENTS', 'OpenAI allocation for this model (AUD cents)', False, '')]
        row = 1
        ttk.Label(content, text='Image producer').grid(row=row, column=0, sticky='w', padx=4)
        self.producer_label = tk.StringVar(value=PROVIDER_LABELS.get(initial_provider, 'Choose image producer'))
        producer = ttk.Combobox(content, textvariable=self.producer_label, state='readonly',
                                values=list(PROVIDER_LABELS.values()))
        producer.grid(row=row, column=1, sticky='ew')
        producer.bind('<<ComboboxSelected>>', self._producer_changed)
        row += 1
        for key, label, secret, default in entries:
            ttk.Label(content, text=label, wraplength=230).grid(row=row, column=0, sticky='w', padx=4, pady=5)
            var = tk.StringVar(value=config.get(key, default))
            self.values[key] = var
            if key in {'IMAGE_MODEL', 'GOOGLE_IMAGE_MODEL'}:
                field = ttk.Combobox(content, textvariable=var,
                    values=[GOOGLE_MODEL if key == 'GOOGLE_IMAGE_MODEL' else OPENAI_MODEL],
                    state='readonly' if key == 'GOOGLE_IMAGE_MODEL' else 'normal')
            else:
                field = ttk.Entry(content, textvariable=var, show='•' if secret else '')
            field.grid(row=row, column=1, sticky='ew', pady=5)
            row += 1
        choices = [('GOOGLE_IMAGE_ASPECT_RATIO', 'Google aspect ratio', ('1:1', '3:4', '4:3'), '1:1')]
        for key, label, options, default in choices:
            ttk.Label(content, text=label).grid(row=row, column=0, sticky='w', padx=4)
            self.values[key] = tk.StringVar(value=config.get(key) or default)
            ttk.Combobox(content, textvariable=self.values[key], values=options, state='readonly').grid(row=row, column=1, sticky='ew')
            row += 1
        advanced = ttk.LabelFrame(content, text='Advanced Google image options', padding=8)
        advanced.grid(row=row, column=0, columnspan=2, sticky='ew', pady=8)
        advanced.columnconfigure(1, weight=1)
        for index,(key, label, options, default) in enumerate([
                ('GOOGLE_IMAGE_SIZE', 'Resolution', ('1K', '2K', '4K'), '1K'),
                ('GOOGLE_IMAGE_THINKING', 'Thinking level', ('minimal', 'medium', 'high'), 'medium')]):
            ttk.Label(advanced, text=label).grid(row=index, column=0, sticky='w', padx=4)
            self.values[key] = tk.StringVar(value=config.get(key) or default)
            ttk.Combobox(advanced, textvariable=self.values[key], values=options, state='readonly').grid(row=index, column=1, sticky='ew', pady=3)
        for index, size in enumerate(('1K', '2K', '4K'), start=2):
            key = f'GOOGLE_IMAGE_ESTIMATE_{size}_AUD_CENTS'
            self.values[key] = tk.StringVar(value=config.get(key, ''))
            ttk.Label(advanced, text=f'{size} allocation (AUD cents)').grid(row=index, column=0, sticky='w', padx=4)
            ttk.Entry(advanced, textvariable=self.values[key]).grid(row=index, column=1, sticky='ew', pady=3)
        row += 1
        flags = [('HERMES_ENABLED', 'Enable the separate Hermes task panel', '0'),
                 ('MEDIA_SYNC_ENABLED', 'Synchronise media automatically with my private server', '0'),
                 ('IMAGE_GENERATION_ENABLED', 'Enable paid image requests', '0'),
                 ('IMAGE_SPENDING_UNCAPPED', 'No spending cap — charge image requests directly to my provider account\n(no shared budget server required)', '0'),
                 ('LOCAL_ONLY', 'Local-only providers; disables Groq, Hermes, media sync, web and image providers', '0'),
                 ('ESP32_ENABLE_HOTKEYS', 'Enable handheld/keyboard hotkeys in this feature app\n(restart required)', '0'),
                 ('ESP32_START_RECEIVER', 'Start a voice receiver from this feature app (restart required)', '0')]
        for key, label, default in flags:
            var = tk.BooleanVar(value=str(config.get(key, default)).lower() in ('1', 'true', 'yes'))
            self.values[key] = var
            ttk.Checkbutton(content, text=label, variable=var).grid(
                row=row, column=0, columnspan=2, sticky='w', pady=4)
            row += 1
        self.image_status = ttk.Label(content, text='', wraplength=600, justify='left')
        self.image_status.grid(row=row, column=0, columnspan=2, sticky='ew', pady=8)
        row += 1
        self.board_image_status = ttk.Label(content, text='', wraplength=800, justify='left')
        self.board_image_status.grid(row=row, column=0, columnspan=2, sticky='ew', pady=8)
        row += 1
        self.check_button = ttk.Button(content, text='Check Google connection (no image)', command=self.check_connection)
        self.check_button.grid(row=row, column=0, columnspan=2, sticky='w', pady=4)
        row += 1
        self.connection_status = ttk.Label(content, text='Model access has not been checked.', wraplength=600)
        self.connection_status.grid(row=row, column=0, columnspan=2, sticky='ew')
        row += 1
        for variable in self.values.values():
            variable.trace_add('write', lambda *_: self._image_status())
        self._image_status()
        ttk.Label(content, text='With No spending cap selected, images use provider billing directly without an application spending limit or shared budget server.\n'
                  'Otherwise the shared server enforces its allowance (A$30/month by default). Allocations are estimates, not provider invoice amounts.\n'
                  'Board illustrations use the selected producer and output options, including Google 1K/2K/4K or OpenAI. '
                  'Save here, then reload Board settings to apply changes.\n'
                  'A failed or ambiguous dispatched attempt retains its allocation until reconciled. No paid request runs during setup.',
                  wraplength=800).grid(row=row, column=0, columnspan=2, sticky='w', pady=8)
        row += 1
        ttk.Button(content, text='Save and apply settings', command=self.save).grid(row=row, column=0, sticky='w')
        row += 1
        self.status = ttk.Label(content, text='Hermes and media sync are not configured.', wraplength=800, justify='left')
        self.status.grid(row=row, column=0, columnspan=2, sticky='ew', pady=8)

    def _producer_changed(self, _event=None):
        self.values['IMAGE_PROVIDER'].set(next(key for key, label in PROVIDER_LABELS.items()
                                               if label == self.producer_label.get()))

    def _image_status(self):
        self._image_revision += 1
        self.connection_status.configure(text='Model access has not been checked for these settings.')
        try:
            text = image_readiness({key: var.get() for key, var in self.values.items()})
        except ValueError as error:
            text = str(error)
        self.image_status.configure(text=text)
        if hasattr(self, 'board_image_status'):
            self.board_image_status.configure(text=board_image_readiness({key: var.get() for key, var in self.values.items()}))

    def check_connection(self):
        if self._checking or self._saving or self._closed:return
        config = {key: var.get() for key, var in self.values.items()}
        revision = self._image_revision
        self._checking = True
        self.check_button.configure(state='disabled')
        self.connection_status.configure(text='Checking Google model metadata; no image request…')
        def worker():
            from gemini_images import check_google_model
            try:
                message = check_google_model(config)
            except ValueError as error:
                message = str(error)
            except Exception:
                message = 'Google model access could not be checked. No image was requested.'
            if not self._closed:self.post_ui(self._connection_finished, revision, message)
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _connection_finished(self, revision, message):
        if self._closed:return
        self._checking = False
        self.check_button.configure(state='normal')
        self.connection_status.configure(text=message if revision == self._image_revision else 'Settings changed during checking. Check again when ready.')
        if revision == self._image_revision and self.values['IMAGE_PROVIDER'].get() == 'gemini':
            state = 'model metadata accessible; rendering unverified' if message.startswith('Google model metadata is accessible.') else 'model access not confirmed'
            self.image_status.configure(text=self.image_status.cget('text').replace('model access unchecked', state))

    def save(self):
        if self._checking:
            self.status.configure(text='Wait for the Google connection check to finish before saving settings.')
            return
        if self._saving:
            return
        values = {key: ('1' if var.get() else '0') if isinstance(var, tk.BooleanVar)
                  else var.get().strip() for key, var in self.values.items()}
        try:
            provider = selected_provider(values)
            selected_model(values, provider)
            for key in ('IMAGE_ESTIMATE_AUD_CENTS', 'GOOGLE_IMAGE_ESTIMATE_1K_AUD_CENTS',
                        'GOOGLE_IMAGE_ESTIMATE_2K_AUD_CENTS', 'GOOGLE_IMAGE_ESTIMATE_4K_AUD_CENTS'):
                amount = values[key]
                if not uncapped_images(values) and amount and (not amount.isdecimal() or not 1 <= int(amount) <= 3000):
                    raise ValueError('Set allocations from 1 to 3000 AUD cents, or leave unused allocations empty.')
            if values['IMAGE_GENERATION_ENABLED'] == '1' and not uncapped_images(values) and not image_snapshot(values)['allocation_cents']:
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
