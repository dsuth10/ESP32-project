# Teaching Board: agreed design and development plan

25 October 2026. **The user confirmed the overall design and requested development
to begin.** Q1–Q15 and the bounded B0–B5 development plan below are agreed.
Initial work proceeds in isolated desktop slices: B0 renderer evidence and B1
renderer-independent document/command/store foundations in parallel. Final
renderer adoption, paid generation, deployment, firmware writes and release keep
their separate decisions and acceptance gates. This plan complements the existing
[companion programme](2026-10-21-companion-media-agent-master-plan.md) and
[today's workboard](2026-10-25-development-workboard.md); existing image-release
and acceptance gates remain open independently.

## Outcome and design tree

A teacher prepares or requests an editable lesson board, presents it to pupils,
and changes or annotates it during teaching. The companion retains the lesson
and can export it. Hermes proposes bounded changes; the Windows application
owns validation, durable state, presentation and undo.

```text
Teaching Board
  Teaching workflow: prepared + live (Q1)
    Teacher controls + optional pupil display + single-display mode (Q2)
      Audience annotation/navigation; teacher text/layout editing (Q10)
      Atomic updates + unchanged/read-only pupil Freeze snapshot (Q7, Q15)
    Explicit AI edits with undo; replacement/deletion preview (Q3)
      Selected remote context only (Q11)
      Dedicated typed + PC-microphone Board command/input (Q14)
  Reusable autosaved editable lessons (Q4)
    Fixed widescreen pages + editing zoom/pan (Q5)
    Mouse/keyboard/pen/touch/eraser (Q6)
    Text/images/shapes/arrows/ink initially (Q8)
      Image/text paste/drop/import and library/provider reuse (Q12)
    Local/offline manual board + portable package/PDF (Q9)
  Concrete three-page lesson acceptance (Q13)
  Overall shared-design confirmation: given 25 October -> isolated development
```

## Decision register

| ID | Decision | State |
| --- | --- | --- |
| Q1 | Support both prepared lessons and live composition during teaching. | Confirmed |
| Q2 | Teacher control view, optional separate pupil display, and usable single-display mode. | Confirmed |
| Q3 | Ordinary explicitly requested AI edits apply directly with undo. Whole-board replacement/deletion requires preview and confirmation. | Confirmed |
| Q4 | Autosave named editable lessons; reopen and duplicate them for reuse. | Confirmed |
| Q5 | Fixed pages, default widescreen, with zoom/pan while editing. | Confirmed |
| Q6 | Initial mouse, keyboard, pen, touch and eraser support. Handwriting recognition and pressure-sensitive brushes come later. | Confirmed |
| Q7 | Present completed changes atomically, with undo and optional Freeze. | Confirmed |
| Q8 | Initial text, images, basic shapes, arrows and ink. Audio/video/live interactive content later. | Confirmed |
| Q9 | Local/offline manual editing, portable lesson package and PDF export. Automatic board sync is a later extension. | Confirmed |
| Q10 | Pupil display supports pen/finger annotation, erasing and page navigation while live; text/layout editing stays in teacher view. | Confirmed |
| Q11 | Send active-page text/layout and selected image metadata by default. Lesson-wide context or screenshots only when explicitly needed. Exclude private notes and unrelated History. | Confirmed |
| Q12 | Explicit image/text paste, drop or import; reuse saved-library and approved generated images initially. Full PDF/PowerPoint/Word import later. | Confirmed |
| Q13 | Use the three-page Year 5 water-cycle workflow below as the first end-to-end acceptance scenario. | Confirmed |
| Q14 | Typing and PC-microphone requests through a dedicated desktop Board command. Preserve Compose/Dictate; handheld Board gestures later. | Confirmed |
| Q15 | Freeze holds the pupil snapshot unchanged and read-only, disabling pupil ink/navigation. Resume presents completed teacher changes; clearly indicate frozen/live in teacher view. | Confirmed |

The coordinator's interview is the decision source. This register summarises
confirmed intent; it does not treat an attached report or a worker's recommendation
as new user authority. The user's subsequent overall confirmation on 25 October
authorised beginning development against this design and its bounded prototype plan.

## Capability boundary

The first board supports page creation/navigation, arranging/resizing objects,
editable text, saved images, shapes/arrows and drawing/erasing. Teachers retain
text/layout control; the pupil view presents the lesson and supports the accepted
annotation/navigation behaviour while live. Freeze preserves the displayed pupil
snapshot and disables pupil drawing, erasing and navigation. Teacher changes can
be prepared meanwhile; Resume presents the completed changes atomically. The
teacher view clearly indicates whether the pupil display is frozen or live.

The same command model should support manual and validated agent edits. Proposed
technical guards include stable page/object IDs, expected document revisions,
atomic command batches and one undo entry per requested AI edit. These are design
requirements to implement and verify; their design alone is not proof they work.
An old Hermes response must not silently overwrite newer teaching edits.

Reuse immutable media version references and local blobs; changing a library's
canonical selection should not silently change saved lessons. Preserve provenance
and explicit provider-spending decisions. A missing saved image must not silently
trigger web search or paid generation. Board context is separate from unrelated
History. Existing Compose, Dictate, Images and Paste Ready keep their own roles;
typing and PC-microphone requests use a dedicated desktop Board action. Handheld
Board integration comes later.

Manual editing, reopening and presentation should work offline. Remote composition
requires its own connection and requested context; loss of Hermes must leave the
manual board usable. Portable export must preserve the used media and editable
document; PDF is a presentation/export format, not a substitute for the editable
lesson. Define export contents and validate them before delivery. Existing media
sync does not already synchronise board pages or ink.

## Technical options, still open

The [renderer research](research/2026-10-25-teaching-board-renderer-options.md)
compares the present Tk canvas, Qt/PySide6 Graphics View and local web/pywebview.
**No final renderer is selected.** Essential pen/touch/eraser support makes an
actual input trial a selection gate. Qt and web are priority candidates for that
comparison; Tk remains the integration baseline with unverified richer input.
Compare Qt and web in the authorised bounded renderer spike before selecting
the final stack.

A separate versioned board store and renderer-independent page/object model are
candidate seams. For Qt/web, an isolated board process is an option to test before
assuming coexistence with Tk's GUI loop. Persistence, bridge validation, display
selection/mixed DPI, package prerequisites, accessibility and dependency/licence
audit remain engineering work. Refer to the linked research for primary sources
and the distinction between documented APIs and untested integration.

## First accepted lesson scenario

In an isolated desktop candidate, create three Year 5 water-cycle pages using
saved images. Edit labels/arrows, rearrange/resize objects, annotate and erase on
the pupil display, navigate pages, request one AI change and undo it. Close/reopen
the lesson with layout/ink retained; export a portable lesson and PDF and inspect
their contents. During Freeze, pupil ink/navigation must be disabled and teacher
changes must remain hidden until Resume presents the completed changes. Exercise
both typed and dedicated PC-microphone Board requests.

Local tests must also cover stale agent results, interrupted save/recovery and
missing media without paid fallback. Display removal, actual pen/touch and
single-/dual-display behaviour need physical checks. Passing local tests or a
healthy Hermes endpoint does not establish classroom acceptance.

## Agreed implementation increments

| Slice | Reviewable result | Evidence before moving on |
| --- | --- | --- |
| B0 | Qt/local-web isolated probes completed with native launches and synthetic fixture checks. | [Trial/evidence](2026-10-25-teaching-board-renderer-trial.md) reviewed. Qt is a provisional integration candidate; physical input/display, text metrics and packaging/licence gates remain before final selection. |
| B1 | Renderer-independent local page/object commands, revisions, save/reopen and undo foundations implemented. | 32 focused model/store tests passed; independent read-only review complete. Manual editor/runtime autosave integration remains separate. |
| B2 | Actual B1/session controller and separate provisional Qt teacher/pupil candidate implemented/reviewed locally. | 14 session tests, 13 native candidate tests and seven smoke checks passed separately. [Candidate limits](2026-10-25-teaching-board-candidate.md), physical input/display/DPI/package acceptance and final renderer choice remain open. |
| B3 | Local fixture adapter implemented/reviewed: 36 focused tests passed; live Hermes composition/UI and dedicated typed/PC-microphone actions remain later. | Selected context, exact identity/revision/token binding, atomic undoable edits, exact external destructive confirmation and actual adapter byte/extraction boundaries verified locally. No live Board task or voice acceptance claimed. |
| B4 | Explicit imports and portable/PDF export using saved media. | A bounded [file/saved-library image insertion candidate](2026-10-25-teaching-board-image-insertion.md) now extends B2. Its local checks and participant acceptance are recorded separately. Wider paste/drop/text imports, editable package reopen, media/provenance and PDF visual checks remain open. |
| B5 | Complete accepted water-cycle lesson with the teacher. | User-observed teaching workflow, saved/exported results, failures/recovery and remaining classroom gates recorded. |

With overall confirmation recorded, B1's renderer-independent document, validated
commands, revisions, save/reopen and undo work can proceed alongside B0. Actual
pen/touch and second-display checks remain explicit acceptance gaps when the
required hardware is unavailable; they do not block independent local
engineering. Final renderer selection remains evidence-gated, and synthetic
input or window tests must not be described as those physical passes.

B-slices are approved desktop Board work, not replacements for programme milestones.
Firmware changes are unnecessary for the initial desktop Board design. The
original S3 firmware/recovery reference, write-locked registration and `main`
remain governed by [board safety](board-upload-safety.md).
