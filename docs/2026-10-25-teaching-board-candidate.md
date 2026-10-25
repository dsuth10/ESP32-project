# Teaching Board: isolated B2 desktop candidate

25 October 2026. A separate experimental Qt process now uses the actual
[document model](../tools/compose/board_model.py),
[local store](../tools/compose/board_store.py) and
[role-bound session](../tools/compose/board_session.py). It does not use B0's
temporary fixture adapter. The existing companion GUI/settings and stable/home
pilot data are not opened or modified by this candidate.

This is a reviewable B2 increment under the [agreed design](2026-10-25-teaching-board-design.md),
not a stable/classroom release or final renderer selection. Physical pen/touch,
projector/DPI behaviour and packaging/licence checks remain selection gates.

## Run and reopen

From the repository root, start a blank isolated candidate with:

```powershell
& tools/compose/run_teaching_board_candidate.ps1
```

It uses only `.local/teaching-board-candidate/review/`. Subsequent launches reopen
that candidate's saved lesson. To create the explicit synthetic three-page demo:

```powershell
& tools/compose/run_teaching_board_candidate.ps1 -Demo -DataRoot '.local/teaching-board-candidate/water-cycle-demo'
```

The demo refuses an existing lesson; reopen it by using the same `-DataRoot`
without `-Demo`. Any caller-supplied directory must remain a subfolder of the
reserved candidate root. Link/junction redirection, including existing media
storage, is rejected before stores are initialised. The launcher never discovers
home-pilot/stable settings, installs packages, opens a listener or changes firmware.

The existing ignored `.local/teaching-board-renderer-env` contains Python 3.13,
PySide6-Essentials 6.12.0 and Pillow 13.0.0. Pytest 9.1.1 was added there for local
checks. No package was installed into system/stable Python. A fresh environment
needs Qt Essentials and Pillow provisioned into that isolated environment; the
launcher reports missing prerequisites and performs no fallback installation.

## Available teaching actions

- Teacher and pupil windows; page creation/navigation; optional pupil-window
  display selection; teacher zoom/pan. White fixed widescreen pages are distinct
  from the neutral viewport. Objects and ink are clipped to the logical page.
- Text creation/editing, selection/movement and numeric position/size controls;
  rectangles, ellipses and arrows; ink and whole-stroke erasing; teacher undo/redo.
  Text uses explicit logical-pixel font sizing and wrapping.
- Dedicated pupil ink/eraser and page-navigation controls while live. Pupil
  handlers cannot edit text/layout. Freeze pins its complete view and disables
  those controls; teacher edits/navigation stay private until Resume publishes
  the completed document/page. The teacher sees frozen/live status.
- Completed edits schedule autosave after 300 ms; pointer motion/preview strokes
  do not save. Status shows Saved, Unsaved, save failure and recovered-previous
  state. Save-only status refresh preserves a current in-progress gesture.
- Reopen uses the validated current/previous checkpoints and retains bounded
  undo/redo history. Failed saves retain dirty edits; reopening refuses dirty
  state. A successful reopen closes the old session; closing the teacher window
  attempts a save and requires an explicit discard if that save fails.

Text/property forms use **Apply selected changes** and the name field uses
**Rename lesson**. Save status describes applied lesson commands; unapplied form
drafts are not lesson content. A stale property/title edit cannot overwrite a
newer revision. Reload selected fields explicitly to discard a stale form draft.

The initial image seam is deliberately narrow: the explicit demo imports a
generated synthetic PNG into a separate candidate MediaStore. Its model stores
only immutable asset/version/digest references. A validated callback resolves
those exact managed versions; the session checks the digest, and the renderer
checks supported format, 20 MiB byte and 25-million-pixel limits before decoding.
Logical resizing transforms the bounded source pixmap rather than allocating a
model-sized raster. Missing/damaged media keeps an unavailable placeholder and
does not retrieve or generate a replacement. A general image import/library
picker is not yet part of this GUI; a blank candidate has no image-add action.

Dedicated Board voice, remote AI/Hermes, general document/media import, portable
packages, PDF export and board sync are later slices. No provider, Office target,
receiver, microphone, paid call or device operation is connected here.

## Local verification and remaining acceptance

Focused native Qt integration checks passed **13 tests, no skips, in 0.63 s**:

```powershell
& .local/teaching-board-renderer-env/Scripts/python.exe -m pytest tools/compose/tests/test_board_candidate.py -q -rs --basetemp .local/teaching-board-candidate/pytest-candidate-final
```

The suite ran outside the sandbox to exercise a real temporary Windows junction;
the first sandbox attempt could not create that junction. Checks cover reserved
root/link rejection, bounded image rendering, logical font sizing, page clipping,
stale property edits, truthful renamed titles after undo/redo, Freeze controls,
autosave during a gesture, delayed ink rejection, visible save failure/retry,
save/reopen/history/session invalidation, previous-checkpoint recovery and
missing-image placeholders. These use real Qt widgets with synthetic actions.

The one-command native smoke passed seven actual-session/store checks and exited
cleanly after launching two real windows:

```powershell
& tools/compose/run_teaching_board_candidate.ps1 -DataRoot '.local/teaching-board-candidate/smoke-final-20261025' -Smoke
```

Smoke requires a fresh folder. Its checks cover pinned Freeze, refused pupil
ink/navigation, complete Resume, ink/erase/undo/redo, exact save/reopen and durable
history. Raw JSON and visually inspected teacher/pupil captures remain ignored
under that folder's `evidence/`. Both available displays were enumerated; their
names/identities are not published here.

No real pen, touch, stylus eraser, palm rejection, projector placement, mixed-DPI
recovery, keyboard-only accessibility or teaching rehearsal has passed yet.
Gesture handlers are candidates for those physical checks, not evidence they
work on the user's hardware. Package launch on another Windows installation and
the dependency/licence audit remain open. No deployment or classroom gate was
closed by these local results.
