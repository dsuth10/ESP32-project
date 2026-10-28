# Teaching Board debug work tree — 28 October 2026

Branch: `board-tester/debug`, from `db3d68d` on `codex/companion-media-agent`.
Draft review only. Not a merge to `main`. No paid image calls. No firmware writes.

Linux Qt-offscreen evidence. Windows and classroom acceptance remain open.

## Save (“doesn’t save”)

Reproduced in part. Lesson JSON, images and undo history already saved. Reopen always
showed **page 1**, so work on later pages looked lost. Freeze is still session-local
by design.

Fix: write `lesson.view.json` with the current page on a successful save, and restore
it on open, in-app reopen, Open saved lesson and Save a copy. A sidecar failure does
not undo a successful lesson save.

Could not reproduce: durable lesson.json failing to write; Save and close dropping
edits when storage works; images vanishing after the source library is removed.

## Image and UI bugs (verified, then fixed)

| Bug | Repro | Fix |
| --- | --- | --- |
| Tiny images stay ~12×12 | `fitted_image_size` capped scale at 1 | Grow to at least 240 logical units, still within 60% of the page |
| Add image buried under Board assistant | `insertWidget(0, agent_panel)` | Page tools first; extra **Add image…** on the main toolbar |
| EXIF phone photos squashed/sideways | PIL stored unrotated pixels | Bake orientation into new local imports; Qt decode stays untransformed so old lessons do not squash |

Saved-library copies keep original bytes/digests. Already-saved EXIF photos are not rewritten.

## Tests (Linux, `--basetemp` inside `.local/teaching-board-candidate`)

- Board suites: **586 passed, 3 skipped**
- New regressions + dummy library + visual: **passed**
- Companion host/settings, packages, uncapped spending, media store/sync/end-to-end, portable media server: passed where they collected
- Could not collect/run here: `win32gui` (embedding, Voice GUI, some Hermes UI), Windows PowerShell setup, Windows-native host embedding, PortAudio Voice GUI until the library was installed, deployment tempfile paths in this VM

Headless captures: `.local/board-tester-debug/screenshots/` (gitignored). Pupil window showed inserted PNG/JPEG/WebP, tiny, transparent, EXIF-upright and library images. Freeze hid teacher-only text from the pupil view.

## Classroom / Next-crash risk

Page restore uses `teacher_navigate`, not the Next button. Image sizing and EXIF apply to
new inserts. Toolbar Add image is an extra control beside existing navigation. No change
to paid generation, billing or firmware.
