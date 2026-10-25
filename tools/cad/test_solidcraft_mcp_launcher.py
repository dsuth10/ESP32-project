import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('launcher', Path(__file__).with_name('solidcraft_mcp_launcher.py'))
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
launcher.WORKSPACE = Path(os.environ.get('SOLIDCRAFT_TEST_WORKSPACE', str(launcher.WORKSPACE)))
INIT = {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'lazy-start-regression','version':'1'}}}


class LazyStartTests(unittest.TestCase):
    def test_real_discovery_does_not_open_window_or_leave_cli_running(self):
        bridge = launcher.Bridge()
        output = io.StringIO()
        with patch.object(launcher, 'open_window', side_effect=AssertionError('GUI launch during discovery')) as window, contextlib.redirect_stdout(output):
            bridge.handle(INIT)
            bridge.handle({'jsonrpc':'2.0','method':'notifications/initialized'})
            bridge.handle({'jsonrpc':'2.0','id':2,'method':'tools/list'})
            bridge.handle({'jsonrpc':'2.0','id':3,'method':'resources/list'})
            bridge.handle({'jsonrpc':'2.0','id':4,'method':'resources/templates/list'})
            bridge.handle({'jsonrpc':'2.0','id':5,'method':'ping'})
        replies = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([r['id'] for r in replies], [1,2,3,4,5])
        self.assertGreaterEqual(len(replies[1]['result']['tools']),19)
        self.assertNotIn('headless in-process', replies[0]['result']['instructions'])
        self.assertIsNone(bridge.process)
        window.assert_not_called()

    def test_first_cad_call_activates_once_and_subsequent_calls_forward(self):
        bridge = launcher.Bridge()
        bridge.initial = INIT
        with patch.object(bridge, 'activate') as activate, patch.object(bridge, 'write') as write, patch.object(launcher,'listening',return_value=True):
            activate.side_effect = lambda: setattr(bridge, 'process', object())
            first = {'jsonrpc':'2.0','id':8,'method':'tools/call','params':{'name':'inspect_design','arguments':{}}}
            second = dict(first,id=9)
            bridge.handle(first)
            bridge.handle(second)
            activate.assert_called_once()
            self.assertEqual([c.args[0] for c in write.call_args_list], [first,second])

    def test_failed_launch_returns_to_idle_and_can_retry(self):
        bridge = launcher.Bridge()
        bridge.initial = INIT
        with patch.object(bridge, 'activate', side_effect=RuntimeError('unavailable')) as activate:
            for _ in range(2):
                with self.assertRaisesRegex(RuntimeError,'unavailable'):
                    bridge.handle({'id':2,'method':'tools/call'})
                self.assertIsNone(bridge.process)
            self.assertEqual(activate.call_count,2)

    def test_closed_window_is_reopened_on_a_later_request(self):
        bridge = launcher.Bridge()
        bridge.initial = INIT
        bridge.process = object()
        with patch.object(launcher,'listening',return_value=False), patch.object(bridge,'close') as close, patch.object(bridge,'activate') as activate, patch.object(bridge,'write'):
            close.side_effect = lambda: setattr(bridge,'process',None)
            bridge.handle({'id':5,'method':'tools/call'})
            close.assert_called_once()
            activate.assert_called_once()

    def test_existing_window_is_reused(self):
        with patch.object(launcher,'listening',return_value=True), patch.object(launcher.subprocess,'Popen') as popen:
            launcher.open_window()
            popen.assert_not_called()

    def test_absent_window_opens_only_when_requested(self):
        with patch.object(launcher,'listening',side_effect=[False,True]), patch.object(launcher.subprocess,'Popen') as popen:
            launcher.open_window()
            self.assertEqual(popen.call_args.args[0], [str(launcher.INSTALL/'solidcraft.exe'),'--control','7878'])

    def test_real_read_only_call_reaches_existing_visible_app(self):
        if not launcher.listening():
            self.skipTest('No existing CAD window; test must not open one')
        bridge = launcher.Bridge()
        replies = []
        bridge.send = replies.append
        try:
            bridge.handle(INIT)
            bridge.handle({'jsonrpc':'2.0','id':99,'method':'tools/call','params':{'name':'inspect_design','arguments':{}}})
            deadline = time.monotonic()+20
            while not any(r.get('id')==99 for r in replies) and time.monotonic()<deadline:
                time.sleep(0.05)
            result = next(r for r in replies if r.get('id')==99)
            self.assertNotIn('error',result)
            self.assertFalse(result['result'].get('isError',False))
            self.assertTrue(result['result'].get('content'))
        finally:
            bridge.close()


if __name__=='__main__':
    unittest.main(verbosity=2)
