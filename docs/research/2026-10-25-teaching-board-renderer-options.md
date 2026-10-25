# Teaching-board renderer options

25 October 2026. Primary-source research and local source inspection only.
No dependency was installed and no renderer, window, paid provider operation or
remote Hermes task was run. No final stack is selected.

## Settled needs and unresolved choices

The user has confirmed prepared and live teaching boards, separate teacher and
pupil views, explicitly requested AI edits with undo, and reusable saved lessons.
The second interview round settled fixed pages with zoom/pan; mouse, keyboard,
pen, touch and an eraser initially; atomic audience updates and Freeze; text,
images, basic shapes, arrows and ink first; and local/offline manual boards with
a portable package and PDF export. Board synchronisation comes later.
All Q1-Q15 decisions are now confirmed in the
[agreed design](../2026-10-25-teaching-board-design.md), including audience
annotation/navigation while live, request-scoped remote context, initial
image/text import, the lesson acceptance case, dedicated typed/PC-microphone
Board commands and read-only Freeze. The user subsequently confirmed the overall
design and authorised development on 25 October. B0 renderer probes and B1
document/store foundations proceed separately; no final renderer has been selected.
The no-execution statement above describes this research pass, not later probes.

The current desktop uses [Tkinter/ttk](../../tools/compose/compose_gui.py),
[Pillow previews](../../tools/compose/media_panel.py), and a separate
[media store](../../tools/compose/media_store.py) with immutable image versions.
There is no internal editable board document or drawing surface. Existing
[Hermes results](../../tools/compose/hermes_panel.py) are displayed/queued as
text. These are local implementation findings, not claims about external tools.

## Three practical routes

**Documented** below means an upstream API exists. **Unverified** means this
application has not integrated or physically tested it.

| Route | Documented foundations | Application work and limits | Conditional fit |
| --- | --- | --- | --- |
| Existing Tk canvas | Retained text, image, shape and line items; item tags, picking and coordinate edits. Canvas text has editing/selection commands. [Tk canvas source manual](https://raw.githubusercontent.com/tcltk/tk/core-8-6-branch/doc/canvas.n) | Selection handles, layout, document serialisation and command history still need implementation. Canvas `scale` changes image/text anchor positions rather than resizing their content, so image resampling/font scaling need explicit handling. Same source. | Smallest change to the present UI for a mouse-first board; pressure/multitouch suitability remains unverified. |
| Qt/PySide6 Graphics View | Retained 2D items, picking, transforms and multiple views of one scene. [Graphics View](https://doc.qt.io/qt-6/graphicsview.html). Editable formatted text is supported through text interaction flags. [QGraphicsTextItem](https://doc.qt.io/qt-6/qgraphicstextitem.html) | Resize handles, ink smoothing, page model and persistence remain application work. Adopting Qt beside Tk adds a GUI integration and packaging decision. | Strong native candidate when pen/touch and editable objects are central; requires an isolated integration trial. |
| Local web canvas in a desktop surface | Canvas draws images, paths and text. [HTML canvas standard](https://html.spec.whatwg.org/multipage/canvas.html). A concrete Python host, pywebview, supports local content, a Python/JavaScript API and multiple screen-selected windows. [pywebview API](https://pywebview.flowrl.com/api/) | Canvas is a drawing API, so retained editable objects, hit testing, text-edit controls and undo require an application layer or separately audited editor library. WebView2/runtime deployment and the bridge are additional dependencies. | Flexible candidate if rich layout/media and browser-style interaction become priorities; local/offline operation needs bundled assets and tested runtime provisioning. |

### Pen, touch and ink

Tk 8.6's [binding manual](https://raw.githubusercontent.com/tcltk/tk/core-8-6-branch/doc/bind.n)
documents mouse/button/motion events; it does not establish a pressure or
multitouch contract. This is a documentation limit, not proof that every Tk
version or Windows extension lacks such input. Verify the actual packaged Tk
version and hardware before promising pen behaviour.

Qt exposes pressure and tilt through
[QTabletEvent](https://doc.qt.io/qt-6/qtabletevent.html), while
[QTouchEvent](https://doc.qt.io/qt-6/qtouchevent.html) requires touch acceptance on
widgets/viewports or graphics items. These APIs do not establish palm rejection,
eraser behaviour, latency or driver compatibility on the user's panel.

The web [Pointer Events specification](https://www.w3.org/TR/pointerevents3/)
defines mouse/pen/touch input, pressure, tilt, pointer capture and coalesced
events. Unsupported pressure can yield a fallback value. Actual WebView2,
device/driver support and gesture-versus-ink handling remain physical tests.
None of the three routes automatically supplies handwriting recognition.

### Teacher and pupil windows

Tk's [window-manager API](https://raw.githubusercontent.com/tcltk/tk/core-8-6-branch/doc/wm.n)
supports top-level geometry/fullscreen control. A reliable Windows display picker,
mixed-DPI positioning and unplug/replug recovery would need a tested monitor
inventory layer. Qt permits multiple views of a scene and provides
[QWindow screen selection](https://doc.qt.io/qt-6/qwindow.html#setScreen);
its documentation warns that selecting a virtual-desktop screen alone does not
move a window to that screen's coordinates. pywebview exposes `screen` and
`fullscreen` window options in its API. All routes still need separate teacher
controls and the agreed pupil rendering policy, including fully read-only Freeze.

### Durable lessons and transactional undo

**Design inference, common to all routes:** keep a renderer-independent local
document with stable page/object IDs, image-version references and ink points.
Persist validated commands/snapshots atomically in the isolated companion data
root. Reconstruct views from that document; a screenshot/bitmap alone cannot
preserve editable objects. Pin image versions so later library canonical changes
do not silently alter a saved lesson.

Qt's [QUndoStack](https://doc.qt.io/qt-6/qundostack.html) provides commands,
macros and clean-state tracking. It still needs correctly implemented commands;
a macro is not a database transaction or stale-result guard. Tk and the proposed
web route need an equivalent application command layer. In every route, one AI
edit should validate its expected board revision before an atomic commit, with
one reversible history entry; exact update policy remains under interview.

### Integration, packaging and licence audit

Tk already owns the running UI loop. Python documents its
[event-loop/threading constraints](https://docs.python.org/3/library/tkinter.html#threading-model).
Qt has its own [application event loop](https://doc.qt.io/qt-6/qapplication.html#exec),
and pywebview explicitly requires `start()` on a main thread. **Inference:** for
either new toolkit, a separately launched board process with a narrow validated
command channel is a practical option to test before attempting embedded dual
GUI loops. It is not an implemented architecture decision.

- **Tk:** no new GUI toolkit is needed for the existing desktop, but the selected
  Python/Tcl/Tk/Pillow package contents still need packaging checks. Tk's
  [licence terms](https://raw.githubusercontent.com/tcltk/tk/core-8-6-branch/license.terms)
  require retaining copyright notices and the licence notice in distributions.
- **Qt:** [Qt for Python deployment](https://doc.qt.io/qtforpython-6/deployment/index.html)
  documents desktop freezing, including `pyside6-deploy`. Its
  [Community/Commercial distributions](https://doc.qt.io/qtforpython-6/commercial/index.html)
  have LGPLv3/GPLv3 or commercial terms; audit selected modules, binaries and
  [third-party components](https://doc.qt.io/qtforpython-6/licenses.html) before
  distribution. No public-release compliance decision has been made here.
- **Web:** pywebview's [Windows renderer guide](https://pywebview.flowrl.com/guide/web_engine.html)
  requires Edge Runtime for `edgechromium`; explicitly select the supported engine
  rather than accepting its legacy fallback. Microsoft documents
  [WebView2 detection and online/offline runtime distribution](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution).
  [Freezing guidance](https://pywebview.flowrl.com/guide/freezing.html) covers local
  asset inclusion and unwanted dependency exclusion. pywebview is
  [BSD 3-Clause](https://github.com/r0x0r/pywebview/blob/master/LICENSE);
  audit runtime terms and any JavaScript editor/fonts separately. Expose only
  narrow board operations to trusted bundled content; local HTTP routes also
  need the documented [session-token/CSRF boundary](https://pywebview.flowrl.com/guide/security.html).

## Next decision and later prototype evidence

**Updated inference after round two:** essential pen/touch/eraser support raises
the first selection gate above a mouse-only canvas demonstration. Prioritise Qt
and the local web route for a later physical-input comparison. Tk remains the
integration baseline, but should not be selected merely because it is installed;
it would need equivalent evidence for the required input behaviour. Qt offers
more ready-made retained-object/undo infrastructure; web offers a standard
pointer-input layer but requires an editor model and WebView2 provisioning.
Neither is selected, and no source migration follows from this note.

After design agreement, test the selected candidates against the same small
lesson, subject to user acceptance: three water-cycle pages, saved image
placement/resizing, editable labels, basic shapes/arrows, ink and erasing,
teacher/pupil display selection, one reversible AI edit and save/reopen.
Include stale AI-result rejection, atomic audience updates, Freeze, mixed DPI,
projector removal, portable-package/PDF output, offline restart and actual
pen/touch input. Record packaged-launch evidence
separately from local UI behaviour and physical classroom acceptance.
