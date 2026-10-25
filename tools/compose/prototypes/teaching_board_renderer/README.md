# Throwaway Teaching Board renderer probes

B0 technical feasibility only: Qt/PySide6 and local web/WebView2, with a generated
water-cycle fixture. These are not production editor implementations or final UI
designs. No user lesson/media store, persistence, network content, remote agent,
provider or device connection is used. State lives in memory. Closing a probe
discards its lesson. WebView2 uses an ignored project-local scratch profile.

From the repository root, the already provisioned isolated environment runs each
probe with one command:

```powershell
& .local/teaching-board-renderer-env/Scripts/python.exe tools/compose/prototypes/teaching_board_renderer/qt_probe.py
& .local/teaching-board-renderer-env/Scripts/python.exe tools/compose/prototypes/teaching_board_renderer/web_probe.py
```

Close its windows before starting the other route. Teacher controls support
selection/movement, text changes, larger/smaller image/shape sizing, page
navigation, ink, whole-stroke erasing, undo, Freeze and Resume. Pupil windows
support annotation/navigation while live; Freeze blocks them and holds the
snapshot. Mouse, tablet or pointer handlers exist, but actual pen/touch devices
have not been accepted. Multitouch gestures, handwriting recognition, pressure
brushes and a complete editor are outside this spike.

Add `--smoke .local/teaching-board-renderer-trial` for a short native launch,
synthetic commands, fixture checks, ignored screenshots/JSON and automatic exit.
Qt captures its widget windows. Web captures canvas artwork only, not native
window chrome. These synthetic actions are not a physical input/display test.

`fixture.py` has a temporary `ProbeState` adapter. Its snapshot matches the B1
model schema and its add/update/remove operations were checked against B1,
but these renderers do not yet use the actual model, durable store or agent API.
Do not promote its limited validation/undo/permissions into production code.

On a fresh checkout, first create a project-local environment and install only
the probe requirements there. The recorded Windows Python 3.13 setup used:

```powershell
python -m venv .local/teaching-board-renderer-env
python -m pip --python .local/teaching-board-renderer-env/Scripts/python.exe install -r tools/compose/prototypes/teaching_board_renderer/requirements.txt
```

The local sandbox's `venv` ensurepip step failed; its interpreter was nevertheless
created, and base pip's `--python` target installed into it successfully. Do not
install these packages globally as a workaround. Qt uses Essentials rather than
the larger Addons package. The web route explicitly requires Edge WebView2 and
selects `edgechromium`; there is no legacy-engine fallback.

See the [trial record](../../../../docs/2026-10-25-teaching-board-renderer-trial.md)
for results, text-layout differences, dependency versions and remaining gates.
