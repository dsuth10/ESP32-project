# Teaching Board B0 renderer trial

25 October 2026. User-authorised technical feasibility spike after shared design
confirmation. [Accepted design](2026-10-25-teaching-board-design.md),
[renderer research](research/2026-10-25-teaching-board-renderer-options.md) and
[runnable throwaway probes](../tools/compose/prototypes/teaching_board_renderer/README.md).
No final renderer is selected and no stable GUI integration occurred.

## Environment and scope

Neither the bundled runtime nor the current Python had PySide6 or pywebview.
An isolated ignored `.local/teaching-board-renderer-env` was provisioned using
Windows Python 3.13. PySide6-Essentials 6.12.0 and pywebview 6.2.1 were installed
there only. The existing Edge WebView2 runtime was 155.0.4283.62. Both native
routes enumerated two available displays; actual projector placement was not
exercised. No system/stable Python package was changed.

Initial sandbox dependency download failed on DNS; a reviewed unsandboxed pip
installation succeeded. The first web launch encountered a sandbox temporary
profile permission error and was stopped. A single narrowed change to an ignored
project-local WebView2 profile allowed the native web smoke run to pass inside
the sandbox; no browser security flags were weakened.

The fixture has three 1600 × 900 logical pages, text, a locally generated PNG,
rectangle, arrow and ink. It contains no real lesson/user media, credentials or
external assets/scripts. There is no HTTP server, remote backend, provider,
Hermes task, microphone capture or firmware operation. Probe lesson state is
memory-only; raw evidence/profile files remain ignored locally.

## Executed local checks

```powershell
& .local/teaching-board-renderer-env/Scripts/python.exe tools/compose/prototypes/teaching_board_renderer/qt_probe.py --smoke .local/teaching-board-renderer-trial
& .local/teaching-board-renderer-env/Scripts/python.exe tools/compose/prototypes/teaching_board_renderer/web_probe.py --smoke .local/teaching-board-renderer-trial
```

| Check | Qt/PySide6 | Local web/pywebview |
| --- | --- | --- |
| Native launch with teacher and pupil windows | Passed; two actual Qt windows | Passed; two actual WebView2 windows |
| Fixture text/image/shape/arrow/ink rendering | Rendered and screenshots visually inspected | Rendered; canvas screenshots visually inspected |
| Synthetic edit behind Freeze and unchanged pupil artwork | Passed in temporary fixture adapter | Passed; full pupil snapshot/debug metadata also held unchanged |
| Pupil ink/navigation rejected during Freeze | Passed in fixture command checks | Passed; Python bridge also rejected pupil ink |
| Resume presents completed page | Passed in fixture command checks | Passed in fixture command checks |
| Ink add, erase, undo and stale-revision refusal | Passed in fixture command checks | Passed in fixture command checks |
| Pupil cannot request teacher-only text/layout actions | Separate native view handlers | Python-side window-bound role; caller does not choose its own role |
| Actual B1 schema / add-update-remove compatibility | Shared fixture validated by B1; three operations accepted at revisions 0-2 | Same shared fixture |
| Real model/store integration | Not performed; temporary adapter only | Not performed; temporary adapter only |
| Physical pen/touch/eraser and projector placement | Not tested | Not tested |

Checks were synthetic method calls; they do not establish real mouse/stylus/touch
event delivery, pen latency, palm rejection or classroom behaviour. Input handlers
are present for manual trials, but no simulated pen/touch event is counted as a
physical pass. Display enumeration does not prove mixed-DPI placement or recovery.

An independent review identified two web-probe boundary issues before completion:
the initial caller-supplied role was replaced with a Python-side window-bound
role, and pupil debug metadata was restricted to the displayed snapshot so hidden
teacher edits do not visibly change it during Freeze. These are probe checks,
not an accepted production security model.

Raw result records and screenshot files are under ignored
`.local/teaching-board-renderer-trial/`: `qt-result.json`, `web-result.json`,
`model-contract-result.json`, `qt-teacher.png`, `qt-pupil-frozen.png`,
`web-teacher-canvas.png` and `web-pupil-frozen-canvas.png`. Qt captures widgets;
web images capture board artwork only. No captures are committed as lesson assets.

## What the comparison establishes

Both routes can run independently of the existing Tk companion, render the same
kind of page/object fixture and show separate teacher/pupil windows with a held
audience snapshot. The real B1 validator accepted the fixture document and
add/update/remove commands, but renderer-to-B1 integration remains future work.

Text layout is **not equivalent**: Qt's text item wraps its explanation while the
web canvas currently compresses a single line with `fillText` maximum width.
Qt font point units and browser logical pixel sizing also need reconciliation.
The captures establish drawing, not interchangeable layout or rich-text fidelity.
The probes also omit full resizing handles, zoom/pan, general shape editing,
complete cancellation/gesture handling, portable/PDF export and accessible editing.

**Provisional engineering recommendation:** use Qt Graphics View for the next
small B2 integration candidate because its retained items and text widgets reduce
custom editor work; keep the local web probe available for comparison. This is
not a final stack decision: actual pen/touch, projector/DPI behaviour, text layout,
dependency/licence audit and a packaged Windows launch must pass before selection.

Next bounded slice: connect one manual page editor to the actual B1 model/store,
then verify save/reopen/undo and the teacher/pupil Freeze contract with real input.
Dedicated Board voice, live Hermes composition and export remain later slices.
Local source checks, deployment checks and physical teaching acceptance retain
separate evidence; this B0 run closes none of the permanent-route/release gates.
