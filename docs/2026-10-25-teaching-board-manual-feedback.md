# Teaching Board manual feedback — 25 October 2026

Participant-reported results from the isolated three-page water-cycle candidate,
under B2/B5 of the [consolidated programme](2026-10-21-companion-media-agent-master-plan.md).
The full private checklist is retained with its lesson and diagnostic evidence
under `.local/teaching-board-candidate/manual-test-20261025-2dd33b9e/`.
This record captures the user's findings and requested changes. It does not
claim new implementation, automated checks, deployment or classroom acceptance.

## Results reported by the user

| Check | Result and limit |
| --- | --- |
| A — Windows | Pass: teacher controls, pupil view and initial three lesson pages. |
| B — Teacher navigation | Pass on the current retest through Next/Previous. The earlier confirmed native Next crash remains unresolved as a root-cause/fix question. |
| C — Pupil navigation | Pass. |
| D — Move text | Pass; mouse resize handles requested. |
| E — Edit text | Pass for editing and applying readable text. |
| F — Image | Qualified functional pass: moving/resizing works, but independent width/height changes distort the image. Default aspect lock requested. |
| G — Shapes/arrows | Pass for adding/moving and undo/redo; mouse resize handles requested. |
| H — Drawing/erasing | Pass; switching tools through a drop-down is cumbersome, so quick buttons requested. |
| I — Consecutive drawing | Pass. |
| J — Freeze | Pass; preserve pinned pupil content and disabled pupil controls. |
| K — Resume | Pass. |
| L — New page | Pass; live text/property editing requested without repeated Apply clicks. |
| M — Rename/save | Pass for the visible save workflow. The user expected two lessons after saving, renaming and saving again, and could not discover the saved lesson/reopen workflow. This does not establish two independent copies or successful reopen. |
| N — Reopen | Incomplete: user unable to complete; no persistence pass or demonstrated data-loss failure. |
| O — Saved history | Incomplete because reopening was not completed. |
| P — Pen | User-reported pass. Physical stylus eraser and palm-rejection coverage not separately established. |
| Q — Touch | User-reported pass. |
| R — Second display | User-reported pass. Broader mixed-DPI, projector-specific and display-reconnection coverage not separately established. |

The earlier confirmed crash occurred at **14:07:05 AEST on 25 October 2026**,
with GUI process 27264 failing in pythonw.exe/ntdll.dll with **0xC0000374**.
Private crash reports, debugger stack and lesson copy remain preserved.
The current navigation pass does not identify a root cause or verify a fix.
If a crash or hang recurs, stop testing and record the exact step and time.

## Requested changes

| ID | Requested behaviour | Acceptance to add after implementation |
| --- | --- | --- |
| TB-F1 | Eight corner/edge mouse resize handles on selected text boxes, shapes and images. | Drag each handle, verify useful resizing, pupil mirroring while live, pinned Freeze, bounds and undo/redo. |
| TB-F2 | Images retain aspect ratio by default, with explicit lock/unlock. A width or height change updates the other dimension when locked. Apply the same default to video when video is supported. | Verify both mouse and numeric resizing; unlocking allows deliberate independent dimensions. Current candidate does not support video. |
| TB-F3 | Quick visible Ink and Erase controls instead of repeated drop-down selection. | Direct switching and visible active mode; Freeze continues to disable pupil editing. |
| TB-F4 | Text/property edits update live by default without repeated Apply/Update actions. Teacher uses Freeze when pupils should not see edits yet. | Latest typing survives immediate navigation/save, undo remains useful, stale edits are rejected and frozen pupil content stays unchanged. |
| TB-F5 | Discoverable saving, lesson location, closing and reopening; distinguish Save, Rename and any future Save a copy behaviour. | Explicitly complete N and O; verify any independent copy preserves its own content and history. |

No general feature-removal request was made. The user specifically wants to
remove the need for repeated Apply/Update clicks and reduce reliance on the
ink/erase drop-down. Entries above are requests, not participant retest results.

## Confirmed design decisions

The user answered yes to all three recommended decisions in the follow-up
Grill Me round:

1. **Resize handles and proportions:** show eight handles for selected text,
   shapes and images. Text-box resizing changes wrapping without changing font
   size; shapes resize freely. Images have a visible aspect lock enabled by
   default, coupling both numeric dimensions and mouse resizing. Unlocking
   permits intentional stretching. Lock state belongs to each image for the
   current session; reopening defaults to locked. Video follows the same policy
   when video support is added.
2. **Live editing and quick tools:** apply text/property changes automatically
   after a short typing pause, group each typing burst into useful Undo, and
   commit pending changes before selection, page changes or closing. Provide
   separate visible Ink/Erase buttons with highlighted active mode in both
   windows. Preserve Freeze's pupil privacy and input restrictions. Timer values
   are implementation details, not a participant-promised timing threshold.
3. **Independent lesson copies:** Save a copy creates a separately named lesson
   with its own self-contained media, then switches to the copy after success.
   The original remains available. Save updates the current lesson; Rename
   changes its title. Copy failures retain the original active session.

## Current saving semantics and open gates

The current candidate updates `lesson.json` in its selected isolated data folder.
`lesson.previous.json` is a recovery checkpoint, not a separate independent
lesson. Renaming changes the current lesson's title; saving after a rename
updates that same lesson. The test folder's existing reopen launcher targets
that same lesson. Closing the teacher window attempts a save and closes the
pupil view; closing only the pupil window hides that view. The existing
**Reopen saved** action reloads the saved lesson in-app, but does not replace the
original close-and-relaunch acceptance check. The private checklist now gives
step-by-step instructions for both paths. N and O still require a participant
retest; no new outcome is inferred from those instructions.

The confirmed choices above guide the new implementation. An already running
candidate still has its previous controls until restarted; the original A–R
results apply to that earlier running version. New controls need fresh retests.

## Independent copy backend — local engineering evidence

`tools/compose/board_lessons.py` provides a staged saved-lesson copy helper.
It requires a saved current source and a new sibling candidate folder, keeps the
source open and unchanged, gives the copy a new lesson identity across bounded
Undo/Redo history, and uses the selected copy title consistently through that
history. It imports only referenced images, including images used only by saved
history, into a separate media store with new immutable references and retained
allowlisted provenance. Prompts, jobs, unrelated images, crash evidence and logs
are not copied. Missing/damaged referenced media prevents an incomplete copy.

Staging validates lesson, history, media and reopen launcher before atomic Windows
publication. Existing destinations and links/junctions are rejected. If final
opening fails after a complete copy was published, the error identifies the
preserved destination and its reopen launcher while leaving the original active.
The UI must switch/close the original only after helper success.

Synthetic backend verification passed **9 tests, no skips, in 0.70 s**, including
a real Windows junction, source byte preservation, independent media/history,
dirty/stale-source rejection, invalid/existing destinations, concurrent
destination appearance, missing-media failure and post-publication reopen
failure. Exact command:

```powershell
& .local/teaching-board-renderer-env/Scripts/python.exe -m pytest tools/compose/tests/test_board_lessons.py -q -rs --basetemp .local/teaching-board-candidate/pytest-lesson-copies-native-20261025-reviewed
```

This suite ran outside the sandbox because the initial sandbox run could not
create a real Windows junction (five passes, one permission-related skip before
the additional cases were added). These are synthetic storage checks; they do
not close participant N/O or verify the new UI workflow.

## Implemented candidate and next participant retest

Subsequent saving feedback exposed a folder-discovery bug, now addressed by the
[shared Saved lessons folder](2026-10-25-teaching-board-saved-lessons-fix.md).
**Open saved lessons** lists named reopen entries for existing lessons and new
copies. Existing data was preserved; future copies use readable central folders.
The earlier sibling-folder implementation below is historical evidence. Retest
this shared folder as part of saving/reopening; do not infer participant passes
from the engineering checks.

The new source now contains resize handles/aspect controls, live text/property
editing with grouped Undo, quick teacher/pupil tools and the save/copy/location/
close controls described in the confirmed decisions. Independent copy-flow
review verified that the UI waits for a complete helper result before switching,
retains the source on cancellation/failure, shows the actual saved location and
reopen launcher, and refuses copy/reopen while frozen until Resume. The original
participant A–R results remain unchanged; these new controls have not yet passed
the participant's physical retest.

The integrated seven-suite native check passed **133 tests, no skips, in 4.54 s**
outside the sandbox, using the exact command in the
[candidate guide](2026-10-25-teaching-board-candidate.md#local-verification-and-remaining-acceptance).
This includes the nine-test copy backend suite; counts are not added.
The coordinator separately recorded **36 B3 fixture tests in 0.49 s** and a
successful two-window smoke with seven synthetic checks under
`.local/teaching-board-candidate/feedback-native-smoke-20261025-1536/`.
No live participant process or lesson was changed for those checks, and the
historical native Next crash has no established root cause/fix.

On the restarted candidate, retest the following independently:

1. Resize selected text, shapes and images using corners and edges. Text should
   wrap at unchanged font size; shapes resize freely. Images keep proportions
   while locked using both handles and numeric dimensions; unlocking permits
   stretching. Reopen should restore the default locked state.
2. Type/edit without Apply, wait briefly, then immediately change selection/page
   or save. Confirm the latest text is retained, wrapping/caret remain usable
   and Undo/Redo handles a typing burst usefully.
3. Switch visible Ink/Erase buttons in both windows. Check the highlighted tool,
   consecutive strokes, erasing and Undo/Redo.
4. Freeze, edit and navigate privately, then Resume. Pupil controls/content stay
   pinned until Resume. Save may run while frozen; copy/reopen should request
   Resume rather than expose private edits.
5. Save now and inspect the visible folder/reopen hint. Use Save a copy with a
   new name, verify the copy opens and its location changes, then verify the
   original remains separately available. Cancelling copy keeps the original.
6. Complete original N/O explicitly: Save and close the teacher window, use the
   current lesson's displayed reopen launcher, inspect all saved content and try
   Undo/Redo before making another edit. Report original lesson and new-copy
   results separately. Reopen saved is an additional in-app check, not a
   substitute for the close-and-relaunch part of N.

If a crash/hang recurs, stop and record the exact action and time. These retests
remain pending until the user reports their results.

These findings supersede the earlier statement that no participant pen, touch or
second-display pass had been recorded. They do not establish broader device
compatibility, packaging/licence clearance, classroom acceptance, live AI/voice,
general image imports, video, export, sync or any M1–M9 release gate.
