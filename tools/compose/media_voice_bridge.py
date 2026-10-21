"""Token-protected loopback handoff from a feature-owned handheld receiver."""
import hmac
import json
import secrets
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import urllib.request


class VoiceBridge:
    def __init__(self, store):
        self.store, self.token = store, secrets.token_urlsafe(32)
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                self.connection.settimeout(5)
                code, payload = 400, {'accepted':False}
                if self.path != '/v1/media-requests':
                    code=404
                elif self.headers.get('Origin') or not hmac.compare_digest(self.headers.get('Authorization',''), 'Bearer '+owner.token):
                    code=401
                else:
                    try:
                        size=int(self.headers.get('Content-Length','0'))
                        if not 0<size<=40_000:raise ValueError()
                        data=json.loads(self.rfile.read(size))
                        if set(data)!={'request_id','transcript'}:raise ValueError()
                        request_id=str(uuid.UUID(data['request_id']))
                        transcript=data['transcript']
                        if not isinstance(transcript,str) or not transcript.strip() or len(transcript)>8000:raise ValueError()
                        owner.store.create_job('voice_request',transcript,job_id=request_id)
                        code,payload=202,{'accepted':True,'request_id':request_id}
                    except Exception:pass
                body=json.dumps(payload).encode()
                self.send_response(code);self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}/v1/media-requests'

    def close(self):
        self.server.shutdown();self.server.server_close()


def forward_transcript(url, token, transcript, request_id=None):
    parsed=urlsplit(url)
    if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or parsed.path!='/v1/media-requests' or parsed.username or parsed.query or parsed.fragment:
        raise ValueError('Media handoff must use the configured loopback bridge.')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    request_id=request_id or str(uuid.uuid4())
    body=json.dumps({'request_id':request_id,'transcript':transcript}).encode()
    request=urllib.request.Request(url,data=body,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    with opener.open(request,timeout=5) as response:
        result=json.load(response)
    if result.get('accepted') is not True or result.get('request_id')!=request_id:
        raise ValueError('Companion did not acknowledge the media request.')
    return request_id
