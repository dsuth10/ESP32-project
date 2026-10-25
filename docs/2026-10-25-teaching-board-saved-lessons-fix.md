# Teaching Board saved-lesson discovery — 25 October 2026

The user reported that differently named saves were absent from the saved-lessons
folder and authorised a repo-local setup. Investigation found independently saved
lessons with valid checkpoints and managed images. The defect was discovery:
**Open lesson folder** opened only the active lesson's UUID data directory, whose
generic reopen launcher did not show any other saved lesson.

## Reproduction and cause

The native regression exercises real Save a copy, the real copy backend and the
folder button; only opening Explorer is intercepted. With two independently
saved titles, the opened directory contained only `Open Teaching Board Lesson.cmd`
and neither chosen title. The test failed repeatedly before the fix, including
the coordinator's run: **one failed in 0.35 s**.

```powershell
& .local/teaching-board-renderer-env/Scripts/python.exe -m pytest tools/compose/tests/test_board_editor_ux.py::test_save_copy_opens_catalogue_containing_both_named_lessons -q --basetemp .local/teaching-board-candidate/pytest-saved-lessons-root-red
```

Inspecting the two synthetic checkpoints confirmed both chosen titles and
independent lesson identities. This ruled out a missing copy or replacement of
the original in that reproduction. Rename/Save still intentionally update one
lesson; Save a copy creates another.

## Resulting behaviour

- **Open saved lessons** opens `.local/teaching-board-candidate/saved-lessons/`.
  Double-click a title-labelled `.cmd` entry to reopen that exact saved lesson.
- Existing lesson data remains at its original location. New access entries
  reference it without moving or rewriting checkpoints, images or history.
- New copies use readable, collision-resistant directories under
  `saved-lessons/data/`, with their own media and history as before.
- Save/autosave refresh discovery after persistence. Rename updates the existing
  named entry; duplicate titles get separate entries. Catalogue errors are shown
  separately from a successful lesson-data save.
- Discovery is shallow and excludes automated test, smoke and crash snapshots.
  Paths, Windows filenames and generated shell arguments are bounded/validated;
  lesson titles remain data rather than shell code. Existing unrelated files
  are preserved. Damaged registered checkpoints retain their access entry and
  produce a visible warning.

The coordinator populated four existing participant entries. A before/after
SHA-256 comparison of **21 existing checkpoint, media and original-launcher
files** found no changes. Private titles, paths and that audit remain in
`.local/teaching-board-candidate/diagnostics/saved-lessons-audit-20261025.json`.

## Verification and remaining acceptance

The seven integrated Board suites passed **141 tests, no skips, in 5.30 s**
outside the sandbox, including real Windows junction checks:

```powershell
& .local/teaching-board-renderer-env/Scripts/python.exe -m pytest tools/compose/tests/test_board_editor_ux.py tools/compose/tests/test_board_candidate.py tools/compose/tests/test_board_resize.py tools/compose/tests/test_board_model.py tools/compose/tests/test_board_session.py tools/compose/tests/test_board_store.py tools/compose/tests/test_board_lessons.py -q -rs --basetemp .local/teaching-board-candidate/pytest-saved-lessons-integrated
```

A subsequently added test executed the actual generated PowerShell reopen
script with process creation intercepted: **one passed in 0.79 s** outside the
sandbox. It confirmed the exact source directory and absence of demo recreation.
The initial sandbox attempt was blocked by PowerShell script authorisation;
the successful test uses the production launcher's execution-policy arguments.
These checks are separate and are not a new physical acceptance result.

The updated two-window native smoke also passed all seven synthetic checks
(Freeze/Resume, ink history and save/reopen) and exited cleanly. Its private
evidence is under `.local/teaching-board-candidate/smoke-saved-lessons-20261025-final/`.
The populated shared folder was opened in Explorer for the user.

On restarting the application, retest Open saved lessons, rename/save,
Save a copy and close/reopen from each named entry. Original participant N/O
and the new interaction retests remain pending. This discovery fix does not
establish a root cause or fix for the earlier native Next crash, deployment,
classroom acceptance or a release.
