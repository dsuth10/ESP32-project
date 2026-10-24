"""Opt-in, identity-bound USB display feedback. No recording/insertion/provider actions.

The Tk thread supplies small snapshots; the serial worker never reads widgets.
Only an explicitly configured port is opened. BLE remains the action transport.
"""
from __future__ import annotations
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import threading
import time
import unicodedata

STATES = {'idle','record_compose','record_dictate','record_media','working','review','text_ready','image_ready','error'}

def display_text(value, maximum):
    plain=unicodedata.normalize('NFKD',str(value or '')).encode('ascii','ignore').decode()
    return ' '.join(re.sub(r'[^\x20-\x7e]|[|]',' ',plain).split())[:maximum]

def frame(nonce, sequence, value):
    if not re.fullmatch('[0-9a-f]{24}',nonce) or not 0<sequence<1_000_000_000 or value.get('state') not in STATES:
        raise ValueError('Invalid bounded device feedback frame.')
    return f"CP1|{nonce}|{sequence}|{value['state']}|{display_text(value.get('title'),27)}|{display_text(value.get('detail'),33)}\n".encode('ascii')

def snapshot(app):
    """Call only from Tk. Never send a transcript, document text or credential."""
    panel=getattr(app,'media_panel',None)
    if getattr(app,'is_recording',False):
        mode=getattr(app,'recording_mode','compose')
        return {'state':'record_'+('media' if mode=='media' else 'dictate' if mode=='dictate' else 'compose'),
                'title':'Recording '+('image request' if mode=='media' else mode),'detail':'PC microphone - tap to finish'}
    if getattr(app,'_busy',False):
        return {'state':'working','title':'Processing speech','detail':'Please wait on PC'}
    if panel is not None and getattr(panel,'_busy',False):
        generation=getattr(panel,'_generation_job_id',None)
        elapsed=max(0,int(time.perf_counter()-getattr(panel,'_generation_started',time.perf_counter())))
        return {'state':'working','title':'Creating image' if generation else 'Working with images',
                'detail':f'{elapsed} s elapsed - do not repeat' if generation else 'Please wait on PC'}
    image=getattr(app,'pending_media',None)
    if image:
        return {'state':'image_ready','title':'Image ready','detail':image.get('canonical_title') or image.get('title') or 'Reviewed image queued'}
    if getattr(app,'pending_ready_payload',None):
        return {'state':'text_ready','title':'Text ready','detail':'Focus document then Paste Ready'}
    if panel is not None and getattr(panel,'prepared_job',None):
        return {'state':'review','title':'Review image brief','detail':'Generate from the PC'}
    if panel is not None and getattr(panel,'selected',None):
        # Selection is context for an edit, not an unfinished operation. Keep
        # recording available after paste while leaving Paste Ready inactive.
        return {'state':'idle','title':'Ready for a request','detail':'Image selected - speak to edit'}
    return {'state':'idle','title':'Ready for a request','detail':'PC mic - tap or hold to speak'}

class DeviceFeedback:
    def __init__(self, port, identity, *, serial_factory=None, start=True, audit_path=None):
        if not re.fullmatch(r'COM[1-9][0-9]*',str(port)) or not re.fullmatch(r'[0-9a-f]{12}',str(identity)):
            raise ValueError('Set the explicit device port and private registered identity.')
        self.port,self.identity,self.serial_factory=port,identity,serial_factory
        self.audit_path=Path(audit_path) if audit_path else None
        self._lock=threading.Lock();self._stop=threading.Event()
        self._value={'state':'idle','title':'Ready for a request','detail':'PC microphone'}
        self._status='Connecting USB feedback';self._last_ack=0;self._page=None
        self._last_error_type=None
        self.thread=threading.Thread(target=self._worker,daemon=True)
        if start:self.thread.start()

    def submit(self,value):
        # Validate/sanitise before crossing the Tk/worker boundary.
        frame('0'*24,1,value)
        clean={'state':value['state'],'title':display_text(value.get('title'),27),'detail':display_text(value.get('detail'),33)}
        with self._lock:self._value=clean

    def status(self):
        with self._lock:
            return 'USB feedback linked' if time.monotonic()-self._last_ack<3 else self._status

    def _set_status(self,value):
        with self._lock:self._status=value

    def _audit(self,event,**fields):
        if self.audit_path is None:return
        self.audit_path.parent.mkdir(parents=True,exist_ok=True)
        with self.audit_path.open('a',encoding='utf-8') as stream:
            stream.write(json.dumps({'time':time.time(),'event':event,**fields})+'\n')
            stream.flush();os.fsync(stream.fileno())

    def _open(self):
        factory=self.serial_factory
        if factory is None:
            import serial
            factory=serial.Serial
        connection=factory(port=None,baudrate=115200,timeout=0.1,write_timeout=0.5)
        connection.dtr=False;connection.rts=False;connection.port=self.port
        connection.open()
        return connection

    def _handshake(self,connection,nonce):
        connection.write(f'CP1? {nonce}\n'.encode('ascii'))
        deadline=time.monotonic()+4
        while not self._stop.is_set() and time.monotonic()<deadline:
            line=connection.readline(256)
            if not line.startswith(b'CP1! '):continue
            parts=line.decode('ascii').strip().split()
            if len(parts)!=4 or parts[0]!='CP1!' or parts[1]!=nonce or parts[3]!='page7-v1':
                raise ValueError('Unsupported device feedback handshake.')
            if not hmac.compare_digest(parts[2],self.identity):
                raise ValueError('USB device identity does not match its configuration.')
            return
        raise TimeoutError('USB device feedback not acknowledged.')

    def _worker(self):
        while not self._stop.is_set():
            connection=None
            try:
                connection=self._open();nonce=secrets.token_hex(12)
                self._handshake(connection,nonce)
                self._audit('device_identity_verified',firmware='page7-v1')
                self._last_error_type=None
                # This explicitly enabled UI trial opens page 7 once per link.
                connection.write(b'page 7\n')
                sequence=0;last_send=0;last_ack=time.monotonic();sent=set();previous_value=None;previous_page=None
                while not self._stop.is_set():
                    now=time.monotonic()
                    if now-last_send>=0.75:
                        with self._lock:value=dict(self._value)
                        sequence+=1
                        connection.write(frame(nonce,sequence,value));sent={sequence};last_send=now
                        if value!=previous_value:
                            self._audit('display_state_sent',**value);previous_value=value
                    line=connection.readline(256)
                    if line.startswith(b'CP1+ '):
                        parts=line.decode('ascii').strip().split()
                        if len(parts)==4 and parts[1]==nonce and parts[2].isdigit() and int(parts[2]) in sent and parts[3].isdigit() and 1<=int(parts[3])<=8:
                            last_ack=time.monotonic()
                            with self._lock:self._last_ack=last_ack;self._page=int(parts[3])
                            if int(parts[3])!=previous_page:
                                self._audit('device_page_acknowledged',page=int(parts[3]),sequence=int(parts[2]));previous_page=int(parts[3])
                    if now-last_ack>3:raise TimeoutError('USB feedback acknowledgement expired.')
            except Exception as error:
                self._set_status('USB feedback unavailable ('+type(error).__name__+')')
                with self._lock:self._last_ack=0
                if self._last_error_type!=type(error).__name__:
                    try:self._audit('device_link_error',error_type=type(error).__name__)
                    except OSError:pass
                    self._last_error_type=type(error).__name__
            finally:
                if connection is not None:
                    try:connection.close()
                    except Exception:pass
            self._stop.wait(2)

    def close(self):
        self._stop.set()
        if self.thread.is_alive():self.thread.join(timeout=2)
