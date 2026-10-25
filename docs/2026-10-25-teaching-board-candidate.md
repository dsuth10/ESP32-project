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
- Text creation/editing, selection/movement, eight mouse resize handles and
  numeric position/size controls; rectangles, ellipses and arrows; ink and
  whole-stroke erasing; teacher undo/redo. Text-box resizing changes wrapping
  without changing font size. Images preserve their current aspect ratio by
  default for mouse and numeric resizing; visible unlocking permits deliberate
  stretching. Per-image locks are session-local and default to locked on reopen.
- Dedicated pupil ink/eraser and page-navigation controls while live. Pupil
  handlers cannot edit text/layout. Freeze pins its complete view and disables
  those controls; teacher edits/navigation stay private until Resume publishes
  the completed document/page. Teacher and pupil have visible quick Ink/Erase
  buttons with highlighted active mode. The teacher sees frozen/live status.
- Completed edits schedule autosave after 300 ms; pointer motion/preview strokes
  do not save. Status shows Saved, Unsaved, save failure and recovered-previous
  state. Save-only status refresh preserves a current in-progress gesture.
- Reopen uses the validated current/previous checkpoints and retains bounded
  undo/redo history. Failed saves retain dirty edits; reopening refuses dirty
  state. A successful reopen closes the old session; closing the teacher window
  attempts a save and requires an explicit discard if that save fails.

Text/property forms now update automatically after a short pause, with grouped
Undo for a typing burst. Pending changes are committed before selection,
navigation, saving or closing; no repeated Apply click is required. A stale draft
cannot overwrite a newer revision and is retained for explicit review/reload.
The name field retains **Rename lesson**; **Save now** also commits a valid
pending name. Save failures retain unsaved work and close requires an explicit
discard if persistence failed.

**Save a copy** creates a separately named, self-contained lesson in a readable
folder under `.local/teaching-board-candidate/saved-lessons/data/` and switches only after the saved copy is validated. The
original remains available. Referenced images, including saved-history images,
and allowlisted provenance are copied; local prompts, jobs, unrelated images,
logs and crash evidence are excluded. Each copy has its own bounded history and
fresh lesson identity; its chosen title is consistent through that copied history.
The copy includes **Open Teaching Board Lesson.cmd**. **Open saved lessons** now
opens the shared `.local/teaching-board-candidate/saved-lessons/` folder, which
contains a title-labelled reopen entry for every saved teacher lesson. Existing
lessons remain at their original paths and are included without moving their
content, images or history. Renaming updates the named entry; equal titles stay
distinct. Automated test and crash-reproduction lessons are excluded. The visible
location distinguishes this shared folder from the current lesson's data.
**Save and close** closes both views. Save/Rename still update the current lesson rather than creating
another copy. Missing referenced media prevents an incomplete copy; failed final
opening after publication identifies the preserved copy's location.

This corrects a reproduced discovery defect: the former folder button opened
only the active UUID directory, so independently saved copies appeared missing.
See the [saved-lessons investigation](2026-10-25-teaching-board-saved-lessons-fix.md)
for the failing reproduction, verification and existing-lesson preservation check.

**Reopen saved** and **Save a copy** require Resume while the pupil view is frozen,
so neither silently publishes private teacher edits. Saving itself remains
available while frozen. An already running candidate retains its old controls
until restarted; all new interactions need fresh participant retests. See the
[feedback and retest record](2026-10-25-teaching-board-manual-feedback.md).

**Add image…** now offers a saved-image library and local PNG/JPEG/WebP files,
with preview and explicit **Insert on this page**. Choose an existing library
folder containing `media.sqlite3`, search titles/tags and select the exact saved
version, or use the Local file tab. The chooser browses library metadata
read-only and remembers only the explicitly chosen source location. It does not
load companion settings or start sync. See the
[image-insertion workflow and evidence](2026-10-25-teaching-board-image-insertion.md).

Chosen bytes are validated and retained in the lesson's own managed media before
one undoable image-add command is published. Immutable asset/version/digest
references keep the lesson independent of later canonical changes or removed
source files. The session verifies the digest; the renderer checks supported
format, 20 MiB and 25-million-pixel limits. Logical resizing transforms the
bounded source pixmap rather than allocating a model-sized raster. Missing or
damaged media keeps an unavailable placeholder without retrieval/generation.

Dedicated Board voice, remote AI/Hermes, wider paste/drop and document imports, portable
packages, PDF export and board sync are later slices. No provider, Office target,
receiver, microphone, paid call or device operation is connected here.

## Local verification and remaining acceptance

The later [image-insertion evidence](2026-10-25-teaching-board-image-insertion.md)
records independent native integration, final focused search/lifecycle checks
and visual review of the chooser and both Board windows. The results below
remain earlier checkpoints; none substitutes for the pending participant
file/library insertion and close/relaunch retest.

After implementing the confirmed feedback, the integrated synthetic native suite
passed **133 tests, no skips, in 4.54 s** outside the sandbox for real Windows
junction checks:

```powershell
& .local/teaching-board-renderer-env/Scripts/python.exe -m pytest tools/compose/tests/test_board_editor_ux.py tools/compose/tests/test_board_candidate.py tools/compose/tests/test_board_resize.py tools/compose/tests/test_board_model.py tools/compose/tests/test_board_session.py tools/compose/tests/test_board_store.py tools/compose/tests/test_board_lessons.py -q -rs --basetemp .local/teaching-board-candidate/pytest-board-ux-integrated-final
```

An independent B3 fixture regression passed **36 tests in 0.49 s**. A separate
actual two-window smoke completed seven synthetic checks and exited successfully;
its private evidence is under
`.local/teaching-board-candidate/feedback-native-smoke-20261025-1536/`. The copy
backend's nine-test focused run overlaps the integrated suite; these counts are
not added. Independent copy-flow review confirmed success-before-switch, retained
source on cancellation/failure, location/reopen guidance and frozen-view guards.
No participant lesson/process was altered by these synthetic checks. They do not
establish a fix for the historical native Next crash or new physical acceptance.

The following earlier checkpoint results remain historical evidence:

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

The later [participant feedback](2026-10-25-teaching-board-manual-feedback.md)
records user-reported passes for pen, touch and second-display checks, plus the
basic editor/navigation/Freeze workflow. Image resizing works but distorts
proportions; aspect locking and other interaction changes are requested.
Close/reopen and durable undo/redo checks remain incomplete because the saving
and reopening workflow was unclear. The earlier confirmed native Next crash is
retained; a passing navigation retest does not establish its root cause or fix.

Physical stylus eraser, palm rejection, projector-specific behaviour, broader
mixed-DPI recovery, keyboard-only accessibility and teaching rehearsal are not
separately established. Package launch on another Windows installation and the
dependency/licence audit remain open. No deployment or classroom gate is closed
by the local checks or participant feedback.
