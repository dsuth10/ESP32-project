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

### Round 3 save-stress (plain results)

| Scenario | What happened |
| --- | --- |
| Process killed after writing `.board-pending-*` but before `os.replace` | Last complete `lesson.json` stays. Pending file is left behind (cleanup skipped). Reopen loads the last complete checkpoint. |
| Process killed during the **first** save of a new lesson | Nothing is promoted. Reopen reports no saved lesson. In-memory work from that first save is gone. |
| Full or read-only folder (`ENOSPC` / `EROFS`) | Save fails with a visible save error. The window stays dirty. Last good `lesson.json` is unchanged. |
| `chmod 555` on the lesson folder | Same as above on this Linux user (not root). |
| Save while Freeze is active | Teacher edits and images **do** persist. Freeze itself is **not** written. Save a copy is refused until Resume. Reopen is live (not frozen) on the saved page. |
| Two teacher windows | `claim_lesson` refuses a second owner (“already open”). A stale window that loaded, then lagged behind another save, is refused rather than overwriting. Two `BoardCandidate` objects in one process are not blocked unless that claim is wired (the unified launcher does wire it). Overlapping concurrent `BoardStore.save` calls: one is refused. |
| Long lesson (10 pages, 20 images) | Save succeeds. Reopen lands on the last page. Every image digest still resolves. |

Could not reproduce: durable `lesson.json` failing to write when storage works; Save and close dropping edits when storage works; images vanishing after the source library is removed; freeze surviving a relaunch; a second window silently clobbering a newer checkpoint.

## Image and UI bugs (verified, then fixed)

| Bug | Repro | Fix |
| --- | --- | --- |
| Tiny images stay ~12×12 | `fitted_image_size` capped scale at 1 | Grow to at least 240 logical units, still within 60% of the page |
| Add image buried under Board assistant | `insertWidget(0, agent_panel)` | Page tools first; extra **Add image…** on the main toolbar |
| EXIF phone photos squashed/sideways | PIL stored unrotated pixels | Bake orientation into new local imports; Qt decode stays untransformed so old lessons do not squash |

Saved-library copies keep original bytes/digests. Already-saved EXIF photos are not rewritten.

## Last-round failures (triage)

| What failed last time | Kind | Outcome this round |
| --- | --- | --- |
| 2 media/provider-layout tests (`test_full_companion_device_feedback_and_media_actions_fit`) | Linux-only `win32gui` import via `ComposeApp`, not a media-store bug | Pass with test-harness stubs |
| 2 Hermes/receiver “failures” | Same two layout tests in a mixed run | Hermes/receiver were already green; layout now passes |
| 7 deployment backup/stage tests (`/tmpXXXX`) | Real **test** bug: `PROJECT_ROOT = SCRIPT.parents[3]` is `/` | Pass after `parents[2]`; extra regression asserts the repo root |
| Collection: `win32gui` / PortAudio | Linux environment | Stubs if missing. Real `sounddevice` used here (PortAudio present). `faster_whisper` also stubbed so CUDA-retry mocks can collect |

Stubs are not installed on Windows. `skipif(os.name != 'nt')` tests stay skipped. Stubs do not open a microphone, send keystrokes or inspect real windows.

## Tests (Linux, `--basetemp` inside `.local/teaching-board-candidate`)

- Board suites (`test_board_*`, including save-stress): **596 passed, 3 skipped**
- Previously blocked compose/media/Hermes/layout/embedding: **238 passed** (includes the old 2+2 layout failures)
- Deployment install/stage/backup: **20 passed** (was 7 failed)
- Companion host/settings/packages/portable server: **46 passed, 9 skipped**
- Paid / live providers: not run
- Windows UI, pen/touch, projector, Next crash: not run

Headless captures: `.local/board-tester-debug/screenshots/` (gitignored). Pupil window showed inserted PNG/JPEG/WebP, tiny, transparent, EXIF-upright and library images. Freeze hid teacher-only text from the pupil view.

## Classroom / Next-crash risk

Page restore uses `teacher_navigate`, not the Next button. Image sizing and EXIF apply to
new inserts. Toolbar Add image is an extra control beside existing navigation. No change
to paid generation, billing or firmware. Save-stress covers store/session behaviour, not
the native Next path.
