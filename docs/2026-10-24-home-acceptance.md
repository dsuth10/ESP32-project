# Home desktop acceptance — 24 October 2026

Testing used the companion branch based on `c88afff`, the existing stable S3
firmware, the PC microphone, and disposable Word/OneNote material. Results below
separate user observations from automated or agent-operated checks. This does not
close M5, deployment, paid-provider or classroom-release gates.

## User-confirmed passes

- Handheld Dictate starts and stops PC recording; the requested sentence appears
  once at the intended Word cursor.
- Handheld Compose produces explanatory writing rather than typing the spoken
  instruction verbatim, and inserts the response once in Word.
- Switching to the companion during recording leaves the result queued; returning
  to Word and pressing handheld Paste Ready inserts it once.
- A saved History response can be queued and inserted once without a new request.
- Local PNG import, preview and explicit named-version selection work.
- Queued image insertion into Word preserves position, colour order and proportions.
  Undo, redo, saving and reopening retain the expected image.
- History, the named image and its preview survive a graceful companion restart.
- Text input into the disposable OneNote page works.
- After the approved keyboard-paste change, a physical handheld Paste Ready press
  inserts one new image correctly into the disposable OneNote page.

These observations do not independently review generated scientific content.

## OneNote image finding and feedback fix

The user reported no image insertion and no visible warning. At a visible caret
on the disposable page, the live application target check consistently refused
selection verification. The focused OneNote document canvas and its inspected
ancestors exposed no UI Automation TextPattern to this adapter. This observation
applies to the tested editing surface, not every OneNote edition or mode.

A focused regression reproduced the missing feedback: rejection updated the
writing tab's status but never notified the Image library panel. The fix
adds a shared status banner across tabs and mirrors blocked, changed-target and
uncertain image outcomes to the Image library notice. Predispatch refusals retain
the image queue; uncertain dispatched attempts still require recovery and cannot
be blindly replayed. Word and OneNote target guards remain unchanged.

Using the companion's existing **Copy image**, then deliberate Ctrl+V at a visible
caret on the disposable OneNote page, the agent visually verified one correctly
rendered synthetic image. Clipboard format is usable on this installation. This
is manual-fallback evidence, not automatic insertion or OneNote save/reopen proof.
After manually pasting and checking an image, use **Clear queued image** if its
undispatched queue remains; copying alone does not verify insertion.

The updated app has been restarted with the same feature data and session-only
hotkeys. The user physically retested handheld Paste Ready and confirmed the
warning is visible in the shared banner and Image library, with the image still
queued. This closes the missing-feedback defect on this installation.

## Local verification

- Focused image feedback/target suite: **21 passed**.
- Non-GUI regression suite: **299 passed, 3 skipped, 14 subtests passed**.
- Native GUI suite in a separate process: **5 passed, 1 skipped**. One Hermes
  layout case could not load an installed Tcl/ttk resource.
- Separate full-companion layout check, with synthetic data and remote/hardware
  inputs disabled: shared feedback, media notice and Copy image remain within
  both 920 × 740 and 720 × 640 windows.
- The combined single-process test command hit a Windows native breakpoint during
  garbage collection in an HTTP fixture on two attempts. The separate runs above
  are the reported evidence; no combined passing result is claimed for this patch.

The original S3 firmware and registration were not changed. Test receipts, local
databases and disposable documents remain private and are excluded from previews.

## Remaining acceptance

OneNote undo/redo and save/reopen; remaining image selection/caret/focus guards; handheld
microphone audio; full S3 regressions; Windows reboot; authorised image-provider
quality/cost tests; deployed private HTTPS, library restore and two-host sync;
installed accessibility/school/classroom pilot. The existing authenticated Hermes
development API passed health/capabilities at home, but its configured HTTP route
does not establish the permanent private HTTPS milestone.

## Approved OneNote keyboard-paste follow-up

After the warning retest, the user explicitly approved normal Ctrl+V behaviour
for a fresh Paste Ready gesture when OneNote cannot expose its selection. This
can replace selected content in the same way as manual Ctrl+V. The earlier
blocked-image observations above describe the original adapter.

The new candidate distinguishes a verified caret, a reported selection and an
unavailable selection API. A reported selection still blocks insertion. When
inspection is unavailable, only the explicit Paste Ready path can bind delivery
to the foreground OneNote process/window, window title and focused document
canvas. These checks run before and after copying, followed by one checked Ctrl+V.
Changed targets abort; background image requests do not receive this permission.
Existing uncertain-job handling prevents automatic duplicate retries. Word's
document/caret checks are unchanged.

The live disposable-page capture now passes with explicit keyboard delivery and
selection inspection correctly recorded as unavailable. The focused target/UI
suite passed **30 tests**. The non-GUI suite passed **308 tests, 3 skipped,
14 subtests**. All six native GUI cases passed individually in fresh processes;
the grouped native run encountered Tcl resource skips. The full-app layout check
passed at both supported sizes. After restarting the companion with the new route,
the user queued the test image, focused the disposable OneNote page and pressed
physical handheld Paste Ready once. The user confirmed: “One new image appears
correctly”. This accepts insertion on this installation; undo/redo and save/reopen
remain separate checks. The actual paste receipt remains `paste_requested`,
not a declaration that OneNote saved the image.

Microsoft documents [OneNote selection export](https://learn.microsoft.com/en-us/office/client-developer/onenote/application-interface-onenote)
and [window properties](https://learn.microsoft.com/en-us/office/client-developer/onenote/window-interfaces-onenote).
Read-only attempts through the registered legacy and 2013-compatible automation
objects did not expose Windows on this installation, so this candidate uses the
observed native document canvas rather than claiming COM selection verification.
