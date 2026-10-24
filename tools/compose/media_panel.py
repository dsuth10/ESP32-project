"""Accessible library-first image UI; background I/O never manipulates Tk."""
from __future__ import annotations
import shutil
import json
import threading
import uuid
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox, scrolledtext
from pathlib import Path
from PIL import Image, ImageTk


class MediaPanel(ttk.Frame):
    def __init__(self, parent, service, post_ui, on_queue, on_record, record_history=None):
        super().__init__(parent, padding=10)
        self.service, self.post_ui, self.on_queue, self.on_record = service, post_ui, on_queue, on_record
        self.record_history=record_history
        self._closed = self._busy = False
        self.selected = None
        self.prepared_job = None
        self.previewed = set()
        self.rows, self.versions = {}, []
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        ttk.Label(self, text='Image library — prepare first, or queue an image for your current document.').grid(row=0,column=0,sticky='w')
        searchbar = ttk.Frame(self)
        searchbar.grid(row=1,column=0,sticky='ew',pady=5)
        searchbar.columnconfigure(0,weight=1)
        self.query = tk.StringVar()
        ttk.Entry(searchbar,textvariable=self.query).grid(row=0,column=0,sticky='ew')
        ttk.Button(searchbar,text='Search library',command=self.refresh).grid(row=0,column=1,padx=3)
        ttk.Button(searchbar,text='Import image',command=self.import_image).grid(row=0,column=2)
        area = ttk.Panedwindow(self,orient='horizontal')
        area.grid(row=2,column=0,sticky='nsew')
        left,right = ttk.Frame(area),ttk.Frame(area)
        area.add(left,weight=1); area.add(right,weight=2)
        left.rowconfigure(0,weight=1); left.columnconfigure(0,weight=1)
        self.gallery = ttk.Treeview(left,columns=('title','state'),show='headings',height=8,selectmode='browse')
        self.gallery.heading('title',text='Image'); self.gallery.heading('state',text='Version')
        self.gallery.column('title',width=200); self.gallery.column('state',width=100)
        self.gallery.grid(row=0,column=0,sticky='nsew')
        scrollbar=ttk.Scrollbar(left,orient='vertical',command=self.gallery.yview)
        scrollbar.grid(row=0,column=1,sticky='ns'); self.gallery.configure(yscrollcommand=scrollbar.set)
        self.gallery.bind('<<TreeviewSelect>>',self.select_asset)
        self.version_box=ttk.Combobox(left,state='readonly')
        self.version_box.grid(row=1,column=0,columnspan=2,sticky='ew',pady=4)
        self.version_box.bind('<<ComboboxSelected>>',self.select_version)
        self.preview=ttk.Label(right,text='Select an image to preview.',anchor='center')
        self.preview.pack(fill='both',expand=True)
        self.details=ttk.Label(right,wraplength=550,justify='left')
        self.details.pack(side='bottom',fill='x',pady=5,before=self.preview)
        actions=ttk.Frame(self);actions.grid(row=3,column=0,sticky='ew',pady=4)
        for label,callback in [('Keep named version',self.approve),('Queue for Paste Ready',self.queue_selected),
                                ('Copy image',self.copy_selected),('Export image',self.export_selected)]:
            ttk.Button(actions,text=label,command=callback).pack(side='left',padx=2)
        tools=ttk.Menubutton(actions,text='Library tools')
        menu=tk.Menu(tools,tearoff=False)
        menu.add_command(label='Back up media library',command=self.backup)
        menu.add_command(label='Restore backup into a new folder',command=self.restore)
        menu.add_command(label='Review selected job',command=self.review_job)
        tools.configure(menu=menu);tools.pack(side='left',padx=2)
        ttk.Label(self,text='Describe a media request, or refine the selected image (Ctrl+Enter to send)').grid(row=4,column=0,sticky='w')
        self.prompt=scrolledtext.ScrolledText(self,height=3,wrap='word',font=('Segoe UI',11))
        self.prompt.grid(row=5,column=0,sticky='ew')
        self.prompt.bind('<Control-Return>',lambda event:(self.ask(),'break')[1])
        commands=ttk.Frame(self);commands.grid(row=6,column=0,sticky='ew',pady=5)
        for label,callback in [('Ask media assistant',self.ask),('Speak / finish',self.on_record),
                               ('Prepare new image',self.prepare),('Refine selected',lambda:self.prepare(True)),
                               ('Search web images',self.web_search)]:
            ttk.Button(commands,text=label,command=callback).pack(side='left',padx=2)
        self.generate_button=ttk.Button(self,text='Generate prepared image',command=self.generate,state='disabled')
        self.generate_button.grid(row=7,column=0,sticky='w')
        self.notice=ttk.Label(self,wraplength=850,justify='left',text='Library first. Web search and paid generation are explicit actions.')
        self.notice.grid(row=8,column=0,sticky='ew',pady=5)
        self.bind('<Configure>',lambda event:self.notice.configure(wraplength=max(280,event.width-20)) if event.widget is self else None,add='+')
        self.jobs=ttk.Treeview(self,columns=('kind','phase'),show='headings',height=3)
        self.jobs.heading('kind',text='Recent image jobs');self.jobs.heading('phase',text='State')
        self.jobs.grid(row=9,column=0,sticky='ew')
        self.jobs.bind('<Double-1>',lambda event:self.review_job())
        self.refresh()

    def tell(self,text):
        if not self._closed:
            self.notice.configure(text=text)

    def run(self,work,done):
        if getattr(self, "settings_saving", lambda: False)():
            self.tell("Wait until settings have finished saving.");return
        if self._busy:
            self.tell('Finish the current media operation first.');return
        self._busy=True
        def worker():
            try:
                result,error=work(),None
            except Exception as exc:
                result,error=None,str(exc) if isinstance(exc,(ValueError,RuntimeError)) else 'Media operation failed. Check its job and connection settings.'
            self.post_ui(self._finish,done,result,error)
        threading.Thread(target=worker,daemon=True).start()

    def _finish(self,done,result,error):
        self._busy=False
        if self._closed:return
        self.refresh_jobs()
        if error:self.tell(error)
        else:done(result)

    def refresh(self):
        selected=self.selected['asset_id'] if self.selected else None
        rows=self.service.find(self.query.get())
        self.rows={r['asset_id']:r for r in rows}
        self.gallery.delete(*self.gallery.get_children())
        conflicts={c['asset_id'] for c in self.service.store.list_conflicts()}
        for row in rows:
            self.gallery.insert('', 'end',iid=row['asset_id'],values=(row.get('canonical_title') or row['title'],
                'Conflict' if row['asset_id'] in conflicts else 'Kept' if row.get('canonical_version_id')==row['version_id'] else 'Draft'))
        if selected in self.rows:
            self.gallery.selection_set(selected)
        self.refresh_jobs()

    def refresh_jobs(self):
        self.jobs.delete(*self.jobs.get_children())
        for job in self.service.store.list_jobs()[:15]:
            self.jobs.insert('','end',iid=job['job_id'],values=(job['kind'],job['phase']))

    def select_asset(self,event=None):
        selection=self.gallery.selection()
        if not selection:return
        row=self.rows[selection[0]]
        self.versions=self.service.store.list_versions(row['asset_id'])
        self.version_box.configure(values=[('Kept: ' if v['version_id']==row.get('canonical_version_id') else 'Draft: ')+v['version_id'][:8] for v in self.versions])
        index=next((i for i,v in enumerate(self.versions) if v['version_id']==row['version_id']),0)
        if self.versions:self.version_box.current(index)
        self.show_version(row)

    def select_version(self,event=None):
        index=self.version_box.current()
        if index>=0:self.show_version(self.versions[index])

    def show_version(self,row):
        self.selected=row
        try:
            with Image.open(self.service.store.blob_path(row['sha256'])) as image:
                image.thumbnail((max(100,min(570,self.preview.winfo_width())),max(60,min(260,self.preview.winfo_height()))))
                self._photo=ImageTk.PhotoImage(image.copy())
            self.preview.configure(image=self._photo,text='')
            self.previewed.add(row['version_id'])
        except Exception:
            self.preview.configure(image='',text='Image unavailable locally. Check sync status.');return
        source=row.get('source') or {}
        self.details.configure(text=f"{row.get('canonical_title') or row['title']} · {row['width']} × {row['height']} px\n"
            f"{row.get('origin','import')} · Version {row['version_id'][:8]} · {source.get('licence','No reuse licence recorded')}\n{source.get('url','')}")

    def import_image(self):
        path=filedialog.askopenfilename(title='Import image',filetypes=[('Images','*.png *.jpg *.jpeg *.webp')])
        if not path:return
        title=simpledialog.askstring('Image title','Name this image:',initialvalue=Path(path).stem,parent=self)
        if not title:return
        self.run(lambda:self.service.store.import_image(path,title=title),self._asset_result)

    def _asset_result(self,row):
        self.refresh();self.show_version(row)
        self.tell('Image stored locally. Review its preview; keeping a named version and inserting are separate actions.')

    def approve(self,title=None):
        if not self.selected:return self.tell('Select a version first.')
        row=self.selected
        if row['version_id'] not in self.previewed:return self.tell('Preview this version first.')
        title=title or simpledialog.askstring('Keep named version','Keep this version as:',initialvalue=row.get('canonical_title') or row['title'],parent=self)
        if not title:return
        try:
            asset=self.service.store.get_asset(row['asset_id'])
            if any(c['asset_id']==row['asset_id'] for c in self.service.store.list_conflicts()):
                self.service.store.resolve_conflict(row['asset_id'],row['version_id'],canonical_title=title)
            else:
                self.service.store.set_canonical(row['asset_id'],row['version_id'],expected_revision=asset['revision'],canonical_title=title)
            self.refresh();self.tell(f'Kept this version as {title}. Earlier versions remain available.')
        except Exception:
            self.tell('Canonical choice conflicted or could not be saved. Refresh and choose the intended version again.')

    def queue_selected(self,target=None):
        if not self.selected:return self.tell('Select an image first.')
        if self.selected.get('origin')=='generated' and self.selected['version_id'] not in self.previewed:
            return self.tell('Preview the generated version before queueing it.')
        try:
            if target:
                self.on_queue(dict(self.selected),target=target)
            else:
                self.on_queue(dict(self.selected))
        except ValueError as error:
            return self.tell(str(error))
        self.tell('Image queued. Focus Word or OneNote, then press Paste Ready. In OneNote, this uses Ctrl+V at your current cursor/selection.')

    def copy_selected(self):
        if not self.selected:return self.tell('Select an image first.')
        try:
            from media_targets import copy_image
            copy_image(self.service.store.blob_path(self.selected['sha256']))
            self.tell('Image copied. Paste it into your chosen document; clipboard copy is not verified insertion.')
        except Exception:self.tell('Could not copy the image. Export it for the target application instead.')

    def export_selected(self):
        if not self.selected:return
        extension={'image/png':'.png','image/jpeg':'.jpg','image/webp':'.webp'}.get(self.selected['mime'],'.png')
        target=filedialog.asksaveasfilename(title='Export image',defaultextension=extension,filetypes=[('Image','*'+extension)])
        if target:
            try:shutil.copyfile(self.service.store.blob_path(self.selected['sha256']),target);self.tell('Image exported.')
            except Exception:self.tell('Image export failed. Check the destination permissions.')

    def backup(self):
        folder=filedialog.askdirectory(title='Choose where to create a new media backup')
        if folder:
            target=Path(folder)/('Companion-media-backup-'+uuid.uuid4().hex[:8])
            self.run(lambda:self.service.store.export_backup(target),lambda path:self.tell(f'Media backup created: {path}. It includes local media prompts/jobs; keep it private. History and credentials are separate.'))

    def restore(self):
        source=filedialog.askdirectory(title='Select a companion media backup folder')
        if not source:return
        parent=filedialog.askdirectory(title='Choose a parent folder for the restored copy')
        if not parent:return
        target=Path(parent)/('Restored-companion-media-'+uuid.uuid4().hex[:8])
        self.run(lambda:self.service.store.__class__.restore_backup(Path(source),target),
                 lambda store:self.tell(f'Restored and verified media into {store.root}. The current library, History and credentials were left in place.'))

    def review_job(self):
        selection=self.jobs.selection()
        if not selection:return self.tell('Select a recent job first.')
        job=self.service.store.get_job(selection[0])
        window=tk.Toplevel(self);window.title('Review media attempt')
        ttk.Label(window,text=f"{job['kind']} · {job['phase']}\n{job.get('error') or job.get('accounting') or 'No error recorded.'}",
                  wraplength=550,padding=12).pack(fill='x')
        if job['phase']=='needs_recovery':
            ttk.Label(window,text='Check the provider account or target document before making another attempt.\n'
                'Closing this attempt retains its full design allocation and does not claim that an image was generated or inserted.',
                wraplength=550,padding=12).pack(fill='x')
            def reconcile():
                def work():
                    if job['kind'] in {'generate','refine'} and job.get('allocation_cents'):
                        if not self.service.sync:raise ValueError('Reconnect the shared budget server before reconciliation.')
                        self.service.sync.commit_budget(job['job_id'],job['allocation_cents'])
                    self.service.store.update_job(job['job_id'],'reconciled',reconciled_by_user=True)
                window.destroy()
                self.run(work,lambda result:self.tell('Attempt closed after user review. No automatic retry or insertion was performed.'))
            ttk.Button(window,text='I have checked — close attempt, retaining allocation',command=reconcile).pack(padx=12,pady=12)

    def text(self):return self.prompt.get('1.0','end-1c').strip()

    def prepare(self,refine=False,prompt=None,title=''):
        if self._busy:return self.tell('Finish the current media operation first.')
        if refine and not self.selected:return self.tell('Select an image to refine first.')
        try:
            job=self.service.prepare_generation(prompt or self.text(),title,
                self.selected['version_id'] if refine else None)
            self.prepared_job=job['job_id']
            estimate=int(self.service.config.get('IMAGE_ESTIMATE_AUD_CENTS') or 0)
            self.generate_button.configure(state='normal',text=f'Generate prepared image — A${estimate/100:.2f} design allocation')
            self.tell('Prepared image request. Generate dispatches one paid attempt using the configured provider and shared budget. Result will preview before insertion.')
            self.refresh_jobs()
        except Exception as exc:self.tell(str(exc))

    def generate(self):
        if self._busy:return self.tell('Finish the current media operation first.')
        if not self.prepared_job:return
        job_id=self.prepared_job
        self.prepared_job=None
        self.generate_button.configure(state='disabled')
        self.tell('Generating one image attempt. Do not repeat the request if the connection fails.')
        self.run(lambda:self.service.generate(job_id),self._asset_result)

    def ask(self,request=None,inbound_job_id=None,target=None):
        request=request or self.text()
        selected=self.selected['version_id'] if self.selected else None
        def interpret():
            try:
                return self.service.interpret(request,selected)
            except Exception:
                if inbound_job_id:self.service.store.update_job(inbound_job_id,'failed',error='Media request could not be interpreted.')
                raise
        def apply(data):
            if self.record_history:
                self.record_history('media',request,json.dumps({k:v for k,v in data.items() if k in {'intent','query','title'}},ensure_ascii=False),
                    'groq' if self.service.config.get('GROQ_API_KEY') and not str(self.service.config.get('LOCAL_ONLY','0')).lower() in {'1','true','yes'} else 'ollama')
            data['request_target']=target
            self.apply_intent(data)
            if inbound_job_id:self.service.store.update_job(inbound_job_id,'completed')
        self.run(interpret,apply)

    def apply_intent(self,data):
        intent=data['intent'];query=data.get('query','');title=data.get('title','')
        if intent in {'refine','approve','insert'} and data.get('selected_version_id') != (self.selected['version_id'] if self.selected else None):
            return self.tell('Selected image changed while interpreting the request. Select the intended version and ask again.')
        if intent=='find':self.query.set(query);self.refresh();self.tell('Library results shown. No external search or generation was performed.')
        elif intent in {'generate','refine'}:self.prepare(intent=='refine',query,title)
        elif intent=='approve':self.approve(title or None)
        elif intent=='insert':
            if query:
                matches=self.service.find(query)
                if len(matches)!=1:
                    self.query.set(query);self.refresh()
                    return self.tell('Choose the intended library image, then queue it. No external search or generation was performed.')
                self.show_version(matches[0])
            self.queue_selected(data.get('request_target'))
        elif intent=='web':self.web_search(query)
        elif intent=='cancel':
            if self.prepared_job:
                self.service.store.update_job(self.prepared_job,'cancelled');self.prepared_job=None
                self.generate_button.configure(state='disabled');self.refresh_jobs()
            self.tell('Undispatched preparation cancelled. Dispatched jobs require result/accounting reconciliation.')
        else:self.tell('Use the library, previews and recent jobs to review media state. Sync status appears in Settings.')

    def web_search(self,query=None):
        self.run(lambda:self.service.search_web(query or self.text()),self.show_web_results)

    def show_web_results(self,rows):
        if not rows:return self.tell('No supported web images found. No generation was requested.')
        window=tk.Toplevel(self);window.title('External image candidates — review reuse terms')
        window.geometry('700x480')
        listing=tk.Listbox(window,height=8,exportselection=False)
        listing.pack(fill='x',padx=10,pady=5)
        for row in rows:listing.insert('end',row['title'])
        details=scrolledtext.ScrolledText(window,height=10,wrap='word');details.pack(fill='both',expand=True,padx=10)
        rights=tk.BooleanVar(value=False)
        def choose(event=None):
            rights.set(False);details.delete('1.0','end')
            if listing.curselection():
                source=rows[listing.curselection()[0]]['source']
                details.insert('1.0','\n'.join(f'{k}: {v}' for k,v in source.items()))
        listing.bind('<<ListboxSelect>>',choose)
        ttk.Checkbutton(window,text='I have reviewed the source and its reuse/attribution requirements',variable=rights).pack(anchor='w',padx=10)
        def acquire():
            if not listing.curselection() or not rights.get():return
            row=rows[listing.curselection()[0]];window.destroy()
            self.run(lambda:self.service.import_web(row,True),self._asset_result)
        ttk.Button(window,text='Import selected candidate',command=acquire).pack(pady=8)

    def close(self):
        self._closed=True
        self.service.close()
