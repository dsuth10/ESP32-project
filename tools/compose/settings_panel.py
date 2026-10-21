"""Local companion setup; secrets are masked and stored with Windows DPAPI."""
import tkinter as tk
from tkinter import ttk
from companion_settings import save_settings


class SettingsPanel(ttk.Frame):
    def __init__(self,parent,config,on_apply):
        super().__init__(parent,padding=14)
        self.on_apply=on_apply
        self.values={}
        self.columnconfigure(1,weight=1)
        ttk.Label(self,text='Feature setup — credentials and network settings stay on this computer.',wraplength=800).grid(row=0,column=0,columnspan=2,sticky='w',pady=8)
        entries=[('GROQ_API_KEY','Groq key (primary embedded assistant)',True,''),
                 ('MEDIA_SERVER_URL','Private media server URL',False,''),
                 ('MEDIA_SERVER_TOKEN','Media server bearer token (separate from Hermes)',True,''),
                 ('OPENAI_API_KEY','OpenAI image provider key',True,''),
                 ('IMAGE_MODEL','Image model',False,'gpt-image-2.5-sunburst'),
                 ('IMAGE_ESTIMATE_AUD_CENTS','Conservative allocation per image attempt (AUD cents)',False,'')]
        row=1
        for key,label,secret,default in entries:
            ttk.Label(self,text=label).grid(row=row,column=0,sticky='w',padx=4,pady=5)
            var=tk.StringVar(value=config.get(key,default));self.values[key]=var
            ttk.Entry(self,textvariable=var,show='•' if secret else '').grid(row=row,column=1,sticky='ew',pady=5)
            row+=1
        for key,label,default in [('MEDIA_SYNC_ENABLED','Synchronise media automatically with my private server','0'),
             ('ALLOW_PRIVATE_SYNC','Allow my configured private server in local-only mode','0'),
             ('IMAGE_GENERATION_ENABLED','Enable paid image requests when I press Generate (shared budget required)','0'),
             ('LOCAL_ONLY','Local-only processing (no image generation or external web lookup)','0'),
             ('ESP32_ENABLE_HOTKEYS','Enable handheld/keyboard hotkeys in this feature app (restart required)','0'),
             ('ESP32_START_RECEIVER','Start a voice receiver from this feature app (restart required)','0')]:
            var=tk.BooleanVar(value=str(config.get(key,default)).lower() in ('1','true','yes'))
            self.values[key]=var
            ttk.Checkbutton(self,text=label,variable=var).grid(row=row,column=0,columnspan=2,sticky='w',pady=4);row+=1
        ttk.Label(self,text='A$30/month is the pilot design allowance on the shared server. Allocations are estimates, not provider invoice amounts.\n'
            'A failed or ambiguous dispatched attempt retains its allocation until reconciled. No paid request runs during setup.',wraplength=800).grid(row=row,column=0,columnspan=2,sticky='w',pady=8);row+=1
        ttk.Button(self,text='Save and apply media settings',command=self.save).grid(row=row,column=0,sticky='w');row+=1
        self.status=ttk.Label(self,text='Sync not configured.',wraplength=800,justify='left')
        self.status.grid(row=row,column=0,columnspan=2,sticky='ew',pady=8)

    def save(self):
        values={k:('1' if v.get() else '0') if isinstance(v,tk.BooleanVar) else v.get().strip() for k,v in self.values.items()}
        try:
            amount=values['IMAGE_ESTIMATE_AUD_CENTS']
            if amount and (not amount.isdecimal() or not 1<=int(amount)<=3000):
                raise ValueError('Set a per-attempt allocation from 1 to 3000 AUD cents, or leave it empty while generation is disabled.')
            if values['IMAGE_GENERATION_ENABLED']=='1' and not amount:
                raise ValueError('Configure the per-attempt allocation before enabling paid images.')
            save_settings(values)
            self.on_apply(values)
        except ValueError as error:self.status.configure(text=str(error))
        except Exception:self.status.configure(text='Settings could not be applied. Finish current operations and check protected storage access. No keys were logged.')

    def set_status(self,text):self.status.configure(text=text)
