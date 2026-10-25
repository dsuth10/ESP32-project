# Teaching Board image insertion — 25 October 2026

This bounded B2/B4 increment implements the immediate image-add workflow from
[the agreed Board design](2026-10-25-teaching-board-design.md): choose a saved
library version or a local image, preview it, then place and resize it in an
editable lesson. It builds on the existing aspect controls, durable Undo/Redo
and [saved-lesson discovery](2026-10-25-teaching-board-saved-lessons-fix.md).

## Teacher workflow

Restart the isolated candidate to load the new controls, then:

1. Select **Add image…** in the teacher window.
2. On **Saved image library**, use **Choose library folder** to select the
   companion data folder containing `media.sqlite3`. Search titles/tags and choose
   the exact saved version; the current canonical version is labelled. Search
   shows up to 500 matches, so narrow the terms when needed. The version list
   includes the latest 500 versions and the canonical version, even when older. The
   chosen folder is remembered locally for this lesson. Alternatively, select
   **Local file** and **Choose local image file**.
3. Inspect the preview, dimensions and available attribution/licence details,
   then choose **Insert on this page**. Cancelling leaves the lesson unchanged.
4. The image appears selected, centred on the current page and sized to fit.
   Move it with the existing Select / move tool. Resize using the eight handles
   or numeric dimensions. **Lock image aspect ratio** is enabled by default;
   unlocking permits deliberate stretching. Reopening defaults to locked.
5. Use Undo/Redo for insertion and subsequent edits. Save and close, then use the
   lesson's named entry in **Open saved lessons** to reopen it. **Save a copy**
   retains an independent lesson with its own referenced images and history.

PNG, JPEG and WebP are supported, with the existing 20 MiB and 25-million-pixel
limits. Choosing a file validates its content, rather than trusting its extension.
An unavailable library can be changed explicitly or bypassed using Local file.
No match or damaged media starts no web search or paid generation.

## Persistence and editing boundaries

The source library is browsed read-only; opening it does not create/migrate a
database, load provider settings or start sync. The candidate does not discover
private companion settings. A caller-supplied library path or the explicit
`ESP32_COMPANION_DATA_DIR` environment variable can supply the initial chooser
location; otherwise the chooser starts with the current lesson's own media.

Before publishing an image object, the application validates and durably retains
the chosen bytes inside the lesson's managed media. The object pins an immutable
asset/version/digest reference. Changing a source library's canonical choice or
removing the original file does not change that saved image. Saved-library imports
retain allowlisted provenance; unrelated images, prompts, jobs, credentials and
History are excluded. The remembered source-folder path is a local chooser
preference and is excluded from Save a copy.

An insertion creates one document command/Undo entry. A changed page, revision or
session invalidates the captured chooser action. Cancellation, unsafe input or
failed validation creates no image object. A storage interruption may leave an
unreferenced managed cache item; it must not publish a reference to an incomplete
blob. Missing/damaged saved media retains the existing unavailable placeholder.

Insertion follows the existing live/Freeze rules: teacher edits stay private
while frozen, pupil content/input remains pinned, and Resume publishes the
completed changes. Existing Compose, Dictate, Images and Paste Ready workflows
remain separate.

## Verification and remaining acceptance

Independent verification after the library-search review correction passed
**22 focused image tests, no skips, in 5.47 s**, using synthetic images and stores:

```powershell
& .local/teaching-board-renderer-env/Scripts/python.exe -m pytest tools/compose/tests/test_board_images.py tools/compose/tests/test_board_image_insertion.py tools/compose/tests/test_board_image_acceptance.py -q -rs --basetemp .local/teaching-board-candidate/pytest-images-independent-search-delta-20261025
```

These checks cover source-independent file imports, read-only library browsing,
exact version/provenance selection, invalid/missing/changed media, picker preview
and cancellation, the actual Add image action, insertion/resize/history, stale
picker rejection, damaged chooser preferences, Freeze and saved Redo after
source removal. Independent lifecycle checks also cover a copied lesson with
saved history, mouse/numeric resizing and a fresh Python process reopening the
exact saved image after its source file was deleted. Review corrected search
that previously excluded older assets before matching; two regressions cover
more than 500 assets/versions and an older canonical selection. No actionable
review finding remains in this bounded slice.

Before that final search correction, the broader native integration run passed
**198 tests, no skips, in 7.89 s** outside the sandbox:

```powershell
& .local/teaching-board-renderer-env/Scripts/python.exe -m pytest tools/compose/tests/test_board_images.py tools/compose/tests/test_board_image_insertion.py tools/compose/tests/test_board_image_acceptance.py tools/compose/tests/test_board_editor_ux.py tools/compose/tests/test_board_candidate.py tools/compose/tests/test_board_resize.py tools/compose/tests/test_board_model.py tools/compose/tests/test_board_session.py tools/compose/tests/test_board_store.py tools/compose/tests/test_board_lessons.py tools/compose/tests/test_board_hermes.py -q -rs --basetemp .local/teaching-board-candidate/pytest-images-independent-integrated-final-20261025
```

The final 22-test selection verifies the subsequent search correction; these
overlapping results are not added. Its sandboxed native `.show` emitted a
non-fatal Windows COM `0x8001010d` warning, while all tests and the process passed.
The preceding native integration and separate visible launch had no such warning.
Picker/teacher/pupil screenshots from the visible launch were visually reviewed
for usable controls, proportionate image rendering and matching live content.
Private captures/result JSON remain under
`.local/teaching-board-candidate/smoke-image-visual-review-20261025/`.
No running participant lesson was changed and no physical retest is inferred.

The participant retest should cover both an actual saved-library image and a
local file: insert, move, resize while locked/unlocked, Undo/Redo, save, close and
reopen. Remove or rename a disposable source file/library after saving and confirm
the reopened lesson still renders the same image. Verify saved history and an
independent Save a copy, then repeat insertion while frozen and confirm it stays
hidden from pupils until Resume. Existing participant N/O remain pending until
the teacher completes that close/relaunch/history check.

This slice does not complete wider image/text paste/drop imports, whole-document
import, portable lesson/PDF export, live Board AI/voice, or the full water-cycle
classroom acceptance. The earlier native Next crash still has no established
root cause or verified fix. No deployment or release is established here.
