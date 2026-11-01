# Classroom app buttons: OneNote, Word, Chrome and the Board

1 November 2026. Planning only on `board-tester/plan-app-buttons`, based on
the latest `codex/companion-media-agent` (including the merged classroom-display
OneNote action). Same-day follow-up: Douglas answered the three open
decisions; they are recorded in [section 7](#7-decisions-1-november-2026).
No application, firmware, test, flash or device change is included. This
does not close M5, M7, physical or classroom acceptance.

## Summary

You already have a desktop action that finds or starts **desktop OneNote** and
puts it on a named **Classroom display**. This plan extends that same idea to
**Word** and **Google Chrome**, and adds a **Board** action that brings the
Teaching Board pupil window onto that same classroom screen.

**Recommended order:** prove everything on the computer first (buttons in the
companion, optional keyboard shortcuts left off). Add handheld buttons only
after you explicitly approve a recoverable firmware trial. Do not squeeze new
buttons onto the current Create & Paste page: its sixth slot is not a spare
button, and Paste Ready is already the full-width bottom control.

**Decided:** the Board button shows the pupil lesson on the classroom display
and brings it to the front. It does not hide OneNote, Word or Chrome, and it
does not Freeze, Resume or change the lesson page.

**Decided:** later device firmware adds Classroom Apps as a **new ninth
page**. Custom Keys stay unchanged. Create & Paste stays on page 7 (its
zero-based index stays 6). After that trial the device will show pages as
*n*/9 instead of *n*/8.

**Decided:** Chrome uses the most recent window by default. The
teacher-chosen window list remains an option, the same as OneNote.

## What you asked for

1. Other applications, with a device button that brings each one to your
   screen: **OneNote**, **Word** and **Google Chrome**.
2. The **Teaching Board pupil display** callable to the **main pupil /
   classroom display**.
3. A plan, not a build.

## What already works

The 1 November OneNote work is already on the companion branch. In the Voice
companion, the **Classroom display** tab lets you:

- Name the classroom screen with **Identify screens** (Home and Work
  remembered separately).
- Choose **most recent** OneNote window, or a specific window.
- Maximise OneNote (on by default).
- Press **Open OneNote on classroom display** or **Test**.
- Optionally turn on **F18** or **Ctrl+Alt+Shift+F6**. That shortcut stays
  **off** until you tick it. There is **no handheld OneNote button** yet.

If the classroom screen is unplugged or asleep, the companion warns
**“No classroom display detected.”** and does not guess another screen.

This action only moves a window. It does not type, it does not open a
notebook page, and it does not become Paste Ready.

The handheld still only sends keyboard codes. Windows chooses the screen and
the window. Bluetooth cannot pick a monitor.

Create & Paste on the device (page 7 of 8 today; page 7 of 9 after a later
ninth-page trial) is unchanged: Compose, Dictate, Images, Library and the
full-width Paste Ready. Those five controls already have a basic physical
pass. Their firmware is an approved recoverable trial; the original 16 MiB
backup and write-locked registration remain in place. Custom Keys stay on
their current page.

## 1. A small app list, not three one-off buttons

Generalise the OneNote action into one **classroom app list** with the same
rules for each app. Settings stay in the existing Classroom display tab
(Home / Work, Identify screens, Test).

| App | How the computer recognises it | How it may be started | Window choice | Screen |
| --- | --- | --- | --- | --- |
| OneNote | `ONENOTE.EXE` (already implemented) | Allowlisted `onenote:` or a path that ends in `ONENOTE.EXE` | Most recent, or a window you pick | Classroom display role |
| Word | `WINWORD.EXE` | Allowlisted path that ends in `WINWORD.EXE` | Same | Same |
| Chrome | `chrome.exe` | Allowlisted path that ends in `chrome.exe`, optionally one safe profile switch (below) | Same, plus extra Chrome rules | Same |
| Board pupil | The existing Teaching Board pupil window, not a separate program | Never launched as an Office app; shown if it was hidden | The current pupil window only | Same |

Per app, remember:

- **Process identity** (the program name above, not the window title alone).
- **Launch policy** (only the allowlisted path or URI; refuse anything else).
- **Most recent** as the default, plus a **teacher-chosen window**.
- **Maximise** (on by default, one tick box per app).
- **Target monitor role:** the durable **Classroom display**, never “Display 2”.

### Safety that must stay true

- No typing into the document.
- No Office COM navigation (no jumping to a notebook, page or Word heading).
- A successful move is **not** a Paste Ready grant and **not** an insert
  target. Compose, Dictate and Paste Ready keep their existing Word/OneNote
  checks.
- If several windows are open and the companion cannot tell which you want,
  it asks you to choose. It does not pick a private window at random.
- If the chosen window has closed, it uses the only remaining window, or
  asks again when several remain.
- Launch only the allowlisted program. No `cmd`, PowerShell, or extra
  command-line flags except Chrome’s optional profile name.

### Chrome: profiles and many windows

Chrome is the awkward one. A school laptop often has many Chrome windows, a
personal profile and a school profile, plus extra hidden Chrome processes.

Rules:

- Match visible Chrome windows belonging to `chrome.exe`. Ignore tiny or
  tool windows.
- **Decided default:** the **most recently used** Chrome window, same as
  OneNote.
- **Decided option:** you may still pin a **specific window** from the
  chosen-window list in Classroom display.
- If several windows are open and none has a “last used” time, refuse with a
  clear line such as: “Several Chrome windows are open. Choose one in
  Classroom display, or bring the intended window to the front once.”
- Starting Chrome, if needed, uses only the allowlisted `chrome.exe`. An
  optional **profile** may be added later as a single
  `--profile-directory=Name` value (letters, numbers, spaces, `.` `_` `-`
  only). No other switches. No website is opened by this button.
- Do not treat Chrome as a Paste Ready destination.

### Word

Word already has separate paste/insert rules. This plan only **finds or
starts** `WINWORD.EXE` and places that window. Several documents mean
several windows: most recent, or the one you pick. Starting Word uses only
the allowlisted program path.

### Shared classroom screen

Keep the existing Identify-screens setup. Replace the Board’s current
**Display 1 / Display 2** list with the same **Classroom display** name, so
Office apps and the Board aim at one remembered screen at home and one at
work. If that screen is missing, every app (including the Board) uses the
same warning: **“No classroom display detected.”**

## 2. Device buttons

The computer work can ship without touching the handheld. A physical button
is a later, separately approved firmware trial.

### Why the empty sixth slot is a poor first choice

On paper, Create & Paste has an unused sixth slot. In the actual firmware it
is not a spare button:

- The page is defined with five controls.
- Paste Ready is drawn **full width** along the bottom.
- Touch handling only accepts the five existing controls (Compose, Dictate,
  Images, Library, Paste Ready).
- Turning that slot on would shrink Paste Ready and reopen the approved
  page 7 trial.

Do not put OneNote, Word or Chrome there.

### Options

| Option | What it is | Fit | Cost / risk |
| --- | --- | --- | --- |
| **A. Companion buttons first (recommended now)** | OneNote, Word, Chrome and Board buttons on the computer, plus optional shortcuts left off | Matches how OneNote already works | No handheld press yet |
| **B. Optional keyboard shortcuts** | New `HotkeyState` modes, off until you tick them | Good for home testing without a flash | Easy to press by accident if left on |
| **C. Fill Create & Paste’s sixth slot** | One extra button on page 7 | Only one button; breaks full-width Paste Ready | Needs a new firmware trial; not enough space for four apps |
| **D. Remap Custom Keys** | Replace the current three Custom Keys with Classroom Apps | Four labelled buttons; still 8 pages | **Not chosen.** Custom Keys stay |
| **E. Add a ninth page (decided later firmware)** | New Classroom Apps page after Storage Explorer | Keeps Custom Keys and Create & Paste | Changes page count from 8 to 9; status, wrap and USB `page N` range all follow `NUM_PAGES` |
| **F. New F-keys only, no new page** | Firmware emits F18–F21 from some remapped existing button | Small code change | Poor labels; easy to confuse with Create & Paste |
| **G. Host command over Wi-Fi** | Historical design; not implemented | Would let the device name the app | Large, separate M7 design; out of scope |

**Recommended order:** A, then B if you want keyboard testing, then **E**
only after explicit approval. Do not do C, D, F or G for this request.

The handheld still only sends a key. Windows still chooses the screen. A
firmware button that “opens OneNote on the board” is the same desktop
action, triggered by a key.

### Exact keys and conflicts

Create & Paste (already in use; do not reuse):

| Device button | Key the device sends | Keyboard stand-in |
| --- | --- | --- |
| Compose | F13 | Ctrl+Alt+Shift+F9 |
| Dictate | F14 | Ctrl+Alt+Shift+F10 |
| Paste Ready (on release) | F15 | Ctrl+Alt+Shift+F11 |
| Images | F16 | Ctrl+Alt+Shift+F8 |
| Library | F17 | Ctrl+Alt+Shift+F7 |

Proposed classroom apps (new; shortcuts off until you enable them):

| Action | Key the device would send | Keyboard stand-in | Notes |
| --- | --- | --- | --- |
| OneNote | F18 | Ctrl+Alt+Shift+F6 | Already reserved in the companion; off by default; no device button yet |
| Word | F19 | Ctrl+Alt+Shift+F5 | New. F5 alone is Refresh; this chord is not F5 |
| Chrome | F20 | Ctrl+Alt+Shift+F4 | New. This is not Alt+F4 (close window) |
| Board pupil | F21 | Ctrl+Alt+Shift+F3 | New. This is not ordinary Find (F3) |

Those extra function keys are already known to the device keyboard library.
Ordinary laptop keyboards often have no F18–F21; the handheld can send them.
The Ctrl+Alt+Shift stand-ins are for a normal keyboard during host testing.

Leave them **off** by default, behind one tick box (“Enable classroom app
shortcuts”), matching the existing OneNote option. The five Create & Paste
listeners stay on their own existing switch.

No conflict with Compose, Dictate, Images, Library or Paste Ready. Avoid
enabling them on a machine that already remaps F18–F21 (for example
PowerToys Keyboard Manager).

### Screen layout and labels (firmware, later)

**Decided:** Classroom Apps is a **new ninth page** after Storage Explorer.
Custom Keys stay on page 5 of 9 with their three current buttons. Create &
Paste stays page 7 of 9 with its current labels and full-width Paste Ready.
Storage Explorer stays page 8 of 9.

Classroom Apps (page 9 of 9), portrait 2×3 grid, four buttons used:

```
ONENOTE     WORD
CHROME      BOARD
(spare)     (spare)
```

Short subtitles the teacher can read at arm’s length, for example
“Classroom screen”. Spare slots stay blank. Do not add Paste Ready here.

Today the device lists eight pages (`NUM_PAGES` is 8). The status bar prints
`currentPage + 1 / NUM_PAGES`, so Create & Paste reads **7/8** and Storage
reads **8/8**. A ninth page must raise that constant to 9. After the trial
those labels become **7/9**, **8/9** and **9/9**. The zero-based indexes do
not shuffle: Create & Paste stays `PAGE_COMPOSE` 6; Storage stays
`PAGE_STORAGE` 7; Classroom Apps is a new `PAGE_CLASSROOM_APPS` 8. The
`PROFILES[NUM_PAGES]` table gains one extra entry.

Page navigation uses the same wrap as today: previous from page 1 goes to
the last page, next from the last page returns to System. After the trial,
previous from System lands on Classroom Apps (not Storage), and next from
Storage lands on Classroom Apps instead of wrapping to System. The USB
`page N` command already accepts `1` through `NUM_PAGES`, so `page 9`
becomes valid once the constant changes. Soft-wake restores a saved page
only when `rtcSavedPage < NUM_PAGES`.

USB companion feedback must stay on Create & Paste. The current handshake
is `page7-v1` and, after a successful link, writes `page 7`. That must
still open Create & Paste. Do not retarget the handshake or the once-per-
link `page 7` write to the new ninth page.

### Firmware trial and safety

A handheld button is a firmware write. Choosing the S3 does not authorise
it. A ninth page is a larger candidate than remapping Custom Keys, because
it changes the compile-time page count, the wrap-around, the on-screen
*n*/9 label, the USB page range and the sleep-restore bound. It still stays
inside the ordinary application image. Before any trial:

1. You say yes, in writing, to that exact ninth-page candidate (Classroom
   Apps added; Custom Keys and Create & Paste unchanged).
2. A complete private **16 MiB** recovery image is taken and matched on a
   second full read. The board currently runs the approved page 7 trial;
   this new write needs its own backup/authorisation, not a reuse of the
   older page 7 receipt.
3. The write uses only the scoped `tools/board_trial.py` route: application
   area only, one durable claim, independent read-back. It cannot write
   bootloaders, partition tables, OTA selection, NVS or filesystems.
4. The stable registry stays **write-locked**. A guard refusal is
   investigated, not edited to pass.
5. After the write, recheck Create & Paste (Compose, Dictate, Images,
   Library, Paste Ready), Custom Keys unchanged, Storage still page 8 of 9,
   Classroom Apps on page 9 of 9, previous/next wrap, and that a USB link
   still opens page 7 — not page 9.

Follow [board upload safety](board-upload-safety.md) and the
[Create & Paste trial record](2026-10-24-create-paste-device-trial.md).
Host testing never grants a flash.

## 3. Board pupil callable to the main pupil display

Two readings of the request were plausible. **Meaning A is decided.**

### Meaning A — decided

**Bring the Teaching Board pupil window onto the classroom display when you
ask.** Same Classroom display role as OneNote, Word and Chrome. The pupil
window is shown if it was hidden, moved to that screen, and brought to the
front. It does **not** hide OneNote, Word or Chrome.

This matches “I want the class to see the Board now”, and reuses the
Identify-screens setup you already have.

### Meaning B — not chosen

**The Board button swaps the classroom screen** between OneNote/Word/Chrome
and the Board, hiding the other app.

That is a show-control toggle. It can surprise a live class (a notebook
vanishes), and it is a different product from “bring this app to the
screen”. Douglas chose meaning A.

### Decided behaviour for meaning A

| Situation | What happens |
| --- | --- |
| Classroom display is connected and named | Pupil window is shown, moved there, brought to the front. Maximise follows the Board tick box (on by default). |
| Pupil window was unchecked / hidden | It is shown. The existing “Show pupil window” tick becomes checked. |
| Lesson is **Frozen** | The frozen snapshot stays. This action does **not** Resume, does **not** Freeze, and does **not** change the published page. Pupil ink and pupil Next/Previous stay disabled while frozen. |
| Lesson is live | The live pupil view is unchanged; only the window’s screen and front-to-back order change. |
| Teacher is on the Voice companion tab | The pupil lesson is not rewritten. Switching teacher tabs already leaves the pupil alone; this action must keep that promise. |
| OneNote, Word or Chrome is also on that screen | They stay open. The Board comes to the front. You can press OneNote/Word/Chrome to bring those back. |
| Classroom display missing | **“No classroom display detected.”** No move to the laptop as a silent fallback. |
| Board is not running | “Open the Teaching Board first.” Do not start a second Board. |

The Board’s current **Display 1 / Display 2** list is only a slot number. It
must use the same durable Classroom display role as OneNote, so docking or
sleeping a screen does not send the lesson to the laptop.

### Freeze, live class, and the earlier Next crash

- Do not create a second pupil window. Move the existing one.
- Do not turn pupil page Next/Previous as a side effect. An earlier native
  **Next** press crashed (`0xC0000374` in `pythonw.exe` on 25 October 2026).
  A later Next/Previous pass did **not** prove a root-cause fix. This work
  must not add a new navigate-on-show path.
- The Board pupil is part of the teacher application, so the usual “do not
  focus our own window” paste guard must not block this move. Placement
  still must not mark the Board as a Word/OneNote insert target.
- Status on the classroom screen is enough; do not steal typing focus from
  a document the teacher is editing unless they pressed Board on purpose.

## 4. Phased work and what “done” means

Local computer checks, a Windows retest, a firmware trial and a classroom
lesson are four different finishes. A written plan or a green Linux test
does not close the later ones.

### Phase H1 — Host only (Linux stubs; no flash)

Build the app list, Word/Chrome/Board actions, companion buttons, and
optional off-by-default shortcuts. Teaching Board Display 1 / Display 2
becomes the Classroom display role.

**Acceptance**

- Linux tests with the existing fake monitor/window stand-in pass (see
  tests below).
- OneNote behaviour stays as it is today, including the exact missing-
  display sentence and “this is not Paste Ready”.
- Word and Chrome refuse non-allowlisted launch commands.
- Chrome with several windows and no “last used” time asks; it does not
  pick a window at random.
- Board action uses the Classroom display role, does not Resume a frozen
  pupil, and does not call page Next.
- Hardware listeners stay off unless you enable them. Create & Paste keys
  are unchanged.

### Phase W1 — Windows retest at home (no flash)

Retest on the real two-monitor home desk with disposable OneNote, Word and
Chrome windows, and with the Teaching Board pupil on the second screen.

**Acceptance**

- Closed / already open / maximised / minimised / several windows for each
  app.
- Chrome with two profiles and several windows.
- Unplug the classroom screen: exact warning; nothing jumps to the laptop.
- Plug it back in and Identify if asked; then the button works again.
- Frozen Board stays frozen after Board is called; Resume still works
  afterwards.
- After an app button, Paste Ready still needs its own press and still
  refuses the companion/Board window as the insert target.
- Failed focus still leaves the window on the right screen and tells you to
  click it once.

### Phase F1 — Firmware trial (only after you approve)

Add Classroom Apps as a **new ninth page**. Keep Custom Keys and Create &
Paste untouched. Emit F18–F21 as one-shot keys. Raise `NUM_PAGES` from 8
to 9; do not shuffle existing page indexes.

**Acceptance**

- Written approval for this ninth-page candidate, a new matched 16 MiB
  recovery (not the old page 7 receipt), scoped trial write and read-back.
- Labels readable; each button sends the key in the table once; hold does
  not repeat.
- Companion, with shortcuts enabled for the trial, places the right app.
- Create & Paste still has its basic physical pass. Custom Keys still
  match their current three chords. Status shows 7/9, 8/9 and 9/9.
- Previous from System opens Classroom Apps; next from Storage opens
  Classroom Apps; next from Classroom Apps wraps to System. USB `page 7`
  still opens Create & Paste; `page 9` opens Classroom Apps.
- BLE disconnect stops a held key. Stable registry still write-locked.
- Physical restore is a separate record if you choose to roll back.

### Phase C1 — Classroom

Work topology (laptop, classroom panel, any extra display). A short live
lesson using Board and at least one of OneNote/Word/Chrome.

**Acceptance**

- The remembered Work classroom screen is the panel the class sees, even if
  Windows has renumbered the displays.
- Calling Board during Freeze does not publish private teacher edits.
- Calling an Office app does not close or rewrite the Board lesson.
- No new Next crash, hang or lost lesson during the rehearsal.
- This phase alone may close classroom acceptance for these buttons. H1/W1
  do not.

## 5. Tests to add (Linux first)

Reuse the existing fake monitor backend and the Classroom display tests.
Keep them stub-backed so they run on Linux.

- Allow-list: OneNote URI/path, Word path, Chrome path, optional Chrome
  profile; refuse `notepad`, `cmd`, extra Chrome flags.
- Window choice for each app: one window; most recent of several; chosen
  window; chosen window gone with one left; chosen gone with several left.
- Chrome-only: many windows, no last-used time → ask, do not guess.
- Shared Classroom display: missing screen → exact warning for every app,
  including Board.
- Board: hidden pupil is shown; frozen snapshot unchanged; no Next/Previous
  call; Board window is not marked Paste Ready.
- Placement: already on the target and maximised is a no-op; window dying
  mid-move is a safe failure.
- Shortcuts: F19/F20/F21 and their chords edge-detect like F18; they stay
  off unless enabled; they do not fire Create & Paste modes.
- Regression: Compose, Dictate, Paste Ready, Images, Library and the
  current OneNote action still pass their existing suites.

Windows W1 checks are manual (or a small native smoke), recorded separately
from Linux.

## 6. Risks

| Risk | Why it matters | What we do |
| --- | --- | --- |
| Chrome window lottery | A private profile could appear on the class screen | Ask when unsure; allow a pinned window; optional profile later |
| Silent fallback to the laptop | Pupils see nothing, or see a private screen | Exact missing-display warning; no remap without Identify |
| Board treated like OneNote | Focus rules currently refuse our own windows, which is correct for paste | Separate Board move path; still not an insert target |
| Freeze accidentally resumed | Class would see unfinished edits | Board button never calls Resume or Freeze |
| Recreating the pupil window | Can lose Freeze or tickle the old Next crash | Move the existing window only |
| Filling Create & Paste’s sixth slot | Breaks the approved full-width Paste Ready | Leave page 7 alone; add a ninth page later |
| Flashing too early | Risks the working page 7 trial | Desktop first; scoped trial only after you approve |
| Shortcut clashes | F5/F4/F3 alone are common keys | Always Ctrl+Alt+Shift; leave the option off |
| Calling this M7 done | M7 is still “change buttons from the computer at runtime” | This is a fixed labelled page, not general profile editing |
| Ninth page changes wrap and *n*/8 labels | Teachers who swipe past Storage expect System; USB `page N` and sleep-restore follow `NUM_PAGES`; the Create & Paste USB handshake must stay on page 7 | Own trial approval and 16 MiB recovery; recheck wrap, Custom Keys, page 7 USB link and 7/9–9/9 labels |

## 7. Decisions (1 November 2026)

Douglas answered the three open questions. They are no longer open.

1. **Board button — decided.** It only brings the Teaching Board pupil
   window forward onto the classroom display. It does not hide OneNote,
   Word or Chrome.
2. **Handheld buttons — decided.** After a later approved firmware trial,
   Classroom Apps is a **new ninth page**. Custom Keys stay unchanged.
   Create & Paste stays page 7 (index 6).
3. **Chrome — decided.** Default is the most recent Chrome window. The
   chosen-window list remains an option, the same as OneNote. A named
   Chrome profile can wait; start allowlisted `chrome.exe` only if no
   window exists.

Maximise stays on by default for each app, as OneNote already does. Missing
classroom display stays a hard stop with the existing sentence. There are
no remaining open decisions for this plan.

## What this plan is not

- Not permission to flash, register, or change the write lock.
- Not a change to Paste Ready, Compose, Dictate, or image insertion.
- Not OneNote page navigation, Word COM, or Chrome URL opening.
- Not general runtime button editing (still a later M7 design).
- Not classroom acceptance.

Related records: [master plan M7](2026-10-21-companion-media-agent-master-plan.md),
[board upload safety](board-upload-safety.md),
[Create & Paste trial](2026-10-24-create-paste-device-trial.md),
[unified desktop plan](2026-10-28-unified-desktop-plan.md) and
[guide](2026-10-28-unified-desktop-guide.md),
[monitor investigation](research/2026-11-01-device-shortcut-monitor-investigation.md),
[project integration](research/2026-11-01-monitor-shortcut-project-integration.md).
The current OneNote action lives in `tools/compose/monitor_shortcut.py`,
`window_monitor_manager.py` and the Classroom display tab. Device pages live
in `src/macropad_config.cpp`. The Board pupil selector is still “Display N”
in `tools/compose/board_candidate.py`.
