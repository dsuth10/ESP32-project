"""THROWAWAY pywebview/WebView2 B0 probe. In-memory fixture; no HTTP server."""
import argparse
import base64
import copy
import json
import threading
import time
from pathlib import Path
import webview
from fixture import IMAGE_URL, ProbeState, exercise


class Bridge:
    def __init__(self):
        self.state, self.lock = ProbeState(), threading.RLock()

    def snapshot(self, audience):
        with self.lock:
            summary = self.state.summary()
            if audience:
                document = self.state.audience if self.state.frozen else self.state.document
                page = self.state.audience_page if self.state.frozen else self.state.page
                summary = dict(revision=document['revision'], page=page+1, frozen=self.state.frozen)
            return dict(page=copy.deepcopy(self.state.visible(audience)), frozen=self.state.frozen,
                        summary=summary, image=IMAGE_URL)

    def action(self, name, args, audience):
        with self.lock:
            if audience and (self.state.frozen or name not in ('nav', 'ink', 'erase')):
                return False
            if name == 'nav':
                return self.state.navigate(args['delta'], audience)
            if name == 'ink':
                return self.state.ink(args['points'], args.get('source', 'mouse'), audience)
            if name == 'erase':
                value = next((o for o in self.state.visible()['objects'] if o['id'] == args['id']), None)
                return self.state.erase(args['id'], audience) if value and value['type'] == 'ink' else False
            if name == 'freeze':
                self.state.freeze()
            elif name == 'resume':
                self.state.resume()
            elif name == 'undo':
                self.state.undo()
            elif name in ('text', 'move', 'resize'):
                value = next((o for o in self.state.visible()['objects'] if o['id'] == args.get('id')), None)
                if not value:
                    return False
                if name == 'text' and value['type'] == 'text':
                    self.state.update(value['id'], text=args['text'])
                elif name == 'move':
                    self.state.update(value['id'], x=args['x'], y=args['y'])
                elif name == 'resize':
                    self.state.update(value['id'], width=value['width']*args['scale'], height=value['height']*args['scale'])
            return True


class WindowBridge:
    """Bind role on Python side; pupil JavaScript cannot request teacher access."""
    def __init__(self, bridge, audience):
        self._bridge, self._audience = bridge, audience

    def snapshot(self):
        return self._bridge.snapshot(self._audience)

    def action(self, name, args):
        return self._bridge.action(name, args, self._audience)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', type=Path)
    args = parser.parse_args()
    bridge = Bridge()
    source = Path(__file__).with_suffix('.html').read_text(encoding='utf-8')
    teacher = webview.create_window('PROTOTYPE — Web teacher', html=source.replace('__AUDIENCE__', 'false'),
                                    js_api=WindowBridge(bridge, False), width=1100, height=760, x=30, y=30)
    pupil = webview.create_window('PROTOTYPE — Web pupil', html=source.replace('__AUDIENCE__', 'true'),
                                  js_api=WindowBridge(bridge, True), width=850, height=550, x=200, y=150)
    if args.smoke:
        def smoke():
            teacher.events.loaded.wait()
            pupil.events.loaded.wait()
            time.sleep(1)
            for window in (teacher, pupil):
                window.evaluate_js('poll()')
            bridge.action('ink', dict(points=[[200, 700], [400, 650], [600, 710]], source='mouse'), False)
            bridge.action('freeze', {}, False)
            frozen_before = bridge.snapshot(True)
            bridge.state.update(bridge.state.visible()['objects'][0]['id'], text='Evaporation — synthetic edit')
            for window in (teacher, pupil):
                window.evaluate_js('poll()')
            time.sleep(0.5)
            args.smoke.mkdir(parents=True, exist_ok=True)
            for name, window in [('web-teacher-canvas', teacher), ('web-pupil-frozen-canvas', pupil)]:
                data = window.evaluate_js("document.querySelector('#board').toDataURL('image/png')")
                (args.smoke/(name+'.png')).write_bytes(base64.b64decode(data.split(',', 1)[1]))
            denied = bridge.action('ink', dict(points=[[5, 5], [20, 20]], source='mouse'), True) is False
            role_denied = WindowBridge(bridge, True).action('text', dict(id=bridge.state.visible()['objects'][0]['id'], text='Blocked')) is False
            result = dict(route='pywebview/edgechromium', checks=exercise(), actual_windows=2,
                          bridge_freeze_rejection=denied, pupil_teacher_action_rejected=role_denied,
                          frozen_complete_snapshot_unchanged=bridge.snapshot(True) == frozen_before,
                          displays_available=len(webview.screens),
                          screenshots='Canvas artwork only; excludes native window chrome',
                          physical_pen_tested=False, physical_touch_tested=False,
                          physical_projector_tested=False, state=bridge.state.summary())
            (args.smoke/'web-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            print(json.dumps(result), flush=True)
            teacher.destroy()
            pupil.destroy()
        worker = smoke
    else:
        worker = None
    scratch = Path(__file__).resolve().parents[4]/'.local/teaching-board-renderer-profile'
    scratch.mkdir(parents=True, exist_ok=True)
    webview.start(worker, gui='edgechromium', http_server=False, private_mode=True,
                  storage_path=str(scratch))
