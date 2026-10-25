# Companion development workboard — 25 October 2026

Continuation of the [24 October checkpoint](2026-10-24-end-of-day-checkpoint.md)
under the [consolidated programme](2026-10-21-companion-media-agent-master-plan.md).
The user requested supervised sub-agent development, continuing yesterday's work
while discussing decisions and an AI teaching board. The user subsequently
confirmed the complete Board design and requested development to begin on
25 October. This record tracks
engineering, deployment and physical acceptance separately. It is not release,
paid-generation, remote-task or firmware-write authority.

## Starting state and verified delivery

- Branch: `codex/companion-media-agent`; `main` remains the reference.
- Initial working tree was clean. Local HEAD was `1d35c77`, the saved enclosure
  pilot and end-of-day checkpoint commit.
- Local tracking ref `origin/codex/companion-media-agent` was `c88afff`, leaving
  17 local commits ahead, including the later OneNote, provider, page 7 and CAD
  work. Its reflog last recorded a successful push at 09:53 AEST on 24 October.
- Yesterday's checkpoint records a request to commit and push; it does not
  record successful delivery of those 17 commits. Today's shell `git ls-remote`
  failed before contacting GitHub (`getaddrinfo() thread failed to start`), but
  the authenticated GitHub connector then compared `c88afff` with the live
  companion branch and returned `identical`, zero commits ahead/behind. Remote
  branch HEAD was then `c88afff`; all 17 later commits were local.
  No push or commit occurred in this audit.
- At the B0/B1 review, today's source/documentation changes were uncommitted,
  additional to those 17 earlier unpushed commits.

The user subsequently explicitly authorised a Luna sub-agent to commit this
branch and bring GitHub current at a logical development checkpoint. The
coordinator dispatched that bounded delivery after B1 and B0 review. Luna audited
the pending files and 17 older outgoing commits, then committed the reviewed
source/docs as `1b6f10d` and the Graphify refresh as `0d1dab3`. The normal feature-
branch push completed; live remote, local HEAD and tracking ref were verified
equal at `0d1dab3`. The checkpoint was clean at delivery; no `main` merge occurred.

The prior delivery discrepancy is resolved. B2 development now follows that
verified commit and creates new local working changes; the earlier clean result
does not describe those later changes. Private identities, settings, images,
receipts, environments and recovery files remain excluded.

## Workstreams and dependencies

| Priority | Workstream | Established evidence | Next bounded action | Completion evidence still needed |
| --- | --- | --- | --- | --- |
| 1 | M1: permanent route to the same Linux Hermes | Today's [read-only preflight](2026-10-25-hermes-readiness.md) confirms authenticated development HTTP/LAN readiness and Windows Tailscale online/running; it does not attest the Linux tailnet route or active home runtime. | Establish the intended Linux host's current enrolment, identity, administrator route and persistent HTTPS prerequisites; prepare a scoped change with rollback. | Same authenticated host over private HTTPS from home and off-LAN/work, scoped access denial, reboot/reconnect and rollback. |
| 1, local work in parallel | M2/M4: saved-image librarian | Opt-in bounded catalogue preparation and validated saved-result preview are now implemented locally; Dictate/Compose remain separate. | Review the completed local slice and its tests; accept one real structured Hermes recommendation after the permanent route is ready. | After M1, one real saved-image search → preview → queue → physical Paste Ready workflow; no implicit web/generation fallback or duplicate dispatch. |
| 2 | M3/G7: separate media/budget deployment and sync | Server/client, deployment kit, backup/restore tools and local two-cache checks exist; live Linux deployment is missing. | Review service/storage/backup ownership, current listeners and exact staged package. Keep Hermes and media origins, tokens and lifecycle separate. | Persistent service, private HTTPS, restore with fresh retrieval and convergence/conflict recovery across two actual Windows stores/installations. |
| 2 | M4/G6: provider accounting and teaching quality | Twelve authorised attempts yielded ten saved Gemini images, including four refinements; immutable parents and private backup/restore passed. | Review retained receipts/failed holds and prepare quality/accounting review without another paid call. | Teacher content approval, provider invoice reconciliation and explicitly resolved failed allocations. Existing allocations are estimates. |
| 2 | M5: current-candidate acceptance | All five page 7 controls have basic physical passes. Compose/Dictate work in Word/OneNote using PC audio; Images searches saved images; generated kangaroo Paste Ready passed in Word. Earlier disposable-image Word/OneNote undo/save-reopen passed. | Use existing saved assets for a short disposable-document matrix: current-candidate placement/proportions, selection/focus changes, one insert per press, undo/redo/save-reopen, restart. Test handheld audio separately. | Complete generated/refined-image matrix in both apps, handheld microphone audio, Windows reboot, S3 regressions and classroom acceptance. |
| 3 | Enclosure | Saved Blender exports and a separate editable SolidCraft base/lid pilot, STEP/STL exports and measured geometry checks exist. Today's [dimension/feature reconciliation](dimensions/solidcraft/2026-10-25-dimension-feature-reconciliation.md) records source conflicts. | Establish an explicit Z stack and physical board/battery/connector/fastener dimensions before detailed modelling; inspect the native MCP connection without replaying fixed save/build sequences. | Chosen design/workflow, confirmed dimensions and detailed geometry, then actual printed fit. Current pilot is not print-ready. |
| 3 | M6/M9: install, adoption and release planning | Source-preview install/update/rollback/removal and licensing/adoption research exist. | Prepare accessible pilot checklist, dependency/licence map and reproducible package requirements alongside M1–M5. | Signed packaging, approved licence/ownership map, school/network permission and installed teacher pilot; explicit stable/public release decision. |
| Parallel approved development | Desktop Teaching Board B0–B5 | B0/B1 delivered at `0d1dab3`. B2 controller/candidate and B3 local fixture groundwork implemented, tested and independently reviewed locally. Subsequent file/saved-library image insertion is recorded in its [bounded follow-up](2026-10-25-teaching-board-image-insertion.md). | Verify the image-add workflow, then deliver the reviewed working set at the next logical checkpoint. | Final renderer selection, complete editor/remote AI/voice/export and real input/display/lesson acceptance remain separate. |

Teaching-board discovery found a Python/Tkinter desktop and Pillow preview,
with no initial editable board model. Immutable media IDs/blobs are reusable;
current media sync only covers image-version/canonical events. The user then
confirmed Q1–Q15 and the overall design, authorising development. B1's separate
local document, revision-bound commands, save/reopen and undo foundations now
proceed alongside B0 renderer probes. Unavailable pen/touch or second-display
hardware leaves explicit physical acceptance gaps while independent local
engineering continues. Final renderer selection still requires evidence.
The [renderer comparison](research/2026-10-25-teaching-board-renderer-options.md)
records Tkinter, Qt and web/pywebview trade-offs. It describes the initial
research pass; subsequent authorised probes and implementation have their own
evidence. No final renderer has been selected.

M1 blocks claims of permanent Hermes or deployed-sync acceptance; it does not
block isolated local development. M3 can be staged/tested locally meanwhile.
The approved Teaching Board work does not displace existing image-release gates.
Enclosure fit and classroom application acceptance have independent evidence.

## Decisions already settled

- ES3C28P ESP32-S3 is the sole supported application target. CYD records are
  historical. `main` and the preserved original firmware remain the baseline.
- The board currently runs the explicitly approved page 7 application trial.
  Original 16 MiB backup and candidate read-back were verified; stable
  registration remains write-locked. Recovery was simulated, not physically
  performed. Another firmware write is a separate scoped decision.
- Groq remains primary. The same existing Linux Hermes is the required
  additional agent at home/work, over a persistent private Tailscale route.
- Hermes may propose bounded catalogue operations. The application owns the
  catalogue, validation, previews, queue and Windows insertion/caret checks.
  Dictate and Compose remain separate from image orchestration.
- Saved-library retrieval is the default. No match does not silently trigger
  web search or paid generation. New provider requests retain explicit spending
  decisions; yesterday's twelve-attempt trial is exhausted.
- Media/allowlisted metadata sync excludes History, full prompts, conversations,
  jobs, credentials and network settings. Service and provider secrets remain
  separate and private.
- Current A$30 monthly design allowance and retained trial allocations are not
  invoices or a guaranteed billing cap. The trial held A$2.40 in total, including
  A$0.40 from two failed attempts; invoice amounts remain unverified.
- Teaching-board foundations: support prepared lessons and live composition;
  a teacher control view with optional separate pupil display and single-display
  mode; ordinary explicitly requested AI edits apply directly with undo, while
  whole-board replacement/deletion requires preview and confirmation; autosave
  named, editable lessons that can be reopened and duplicated. The user answered
  yes to all four foundations in today's interview.
- Teaching-board round two: fixed pages defaulting to widescreen, with zoom/pan
  while editing; initial mouse, keyboard, pen, touch and eraser support, with
  handwriting recognition and pressure-sensitive brushes later; atomic,
  undoable pupil-display updates plus optional Freeze; initial text, images,
  shapes, arrows and ink, with audio/video/live interactive content later;
  local/offline manual editing, a portable lesson package and PDF export, with
  automatic board sync as a separate later extension. The user accepted all five
  recommendations.
- Teaching-board round three: the audience display permits direct pen/finger
  annotation, erasing and navigation, while layout/text editing stays in the
  teacher view; Hermes context follows the request, using active-page/selected
  metadata by default and whole-lesson/screenshots only when explicitly needed,
  excluding private notes and History; initial import covers local images/text
  through paste, drop and file import plus the saved library, with whole-document
  import later; first acceptance is a three-page Year 5 water-cycle lesson. The
  user accepted all four recommendations.
- Teaching-board Q14–Q15: initial AI requests use typing or a dedicated PC-mic
  Board command, preserving existing Compose/Dictate, with handheld Board
  integration later. Freeze keeps the audience snapshot fully unchanged and
  read-only, including audience ink/navigation; Resume presents completed edits,
  and the teacher has a visible Freeze indicator. Both recommendations are
  confirmed.
- Overall Teaching Board design and the B0–B5 development plan: the user answered
  yes and requested development to begin on 25 October. This settles shared
  understanding; release, deployment, paid generation and firmware gates remain
  separate.

## Open decisions and facts to establish

Find environment facts through inspection rather than asking the user to
rediscover them. Bring the user concrete choices where intent is required.

| Area | Facts to establish | User decision when the facts are ready |
| --- | --- | --- |
| Hermes transport | Intended host's current enrolment/service/Serve state, access ownership and available administrator route. | Review a scoped persistent route/deployment change if required; approved work-network use. |
| Media service | Existing listeners, durable storage, backup destination/retention and two Windows installation identities. | Service/storage/backup ownership and retention policy. |
| Provider | Safe receipts, failed-hold state, invoice/access availability and saved candidate images. | Teaching quality approval, accounting resolution and any new paid trial. |
| Enclosure | Current saved model, known board/connector/battery/fastener dimensions and limits of historical measurements. | Preferred editable workflow and physical case design/fit choices. |
| Teaching board | [Agreed design](2026-10-25-teaching-board-design.md), [renderer research](research/2026-10-25-teaching-board-renderer-options.md) and isolated model/probe implementation in progress. | Final renderer choice after evidence; integration/physical lesson acceptance. Confirmed product scope is not reopened by toolkit choices. |
| Public release | Dependency/content provenance, licence constraints and package prerequisites. | Licence choice, ownership clearance, pilot sign-off and release approval. |

## Evidence and acceptance ledger

**Local engineering:** recorded device-trial core suite was 345 passed with one
Windows symlink skip; end-to-end/native-layout cases passed separately. Yesterday's
final focused selection was 46 passed. These suites overlap and are not added.
CAD scripts/requests parsed; native model and geometry checks passed. This audit
does not rerun them or imply a clean single-process full suite.

Today's saved-image slice adds a maximum twelve-record metadata catalogue,
explicit Hermes dispatch, full allowlisted-snapshot and local SHA-256 validation,
stale-run rejection and preview-only recommendation handling. The source worker
reports **39 passed, no skips**, including both native layouts. Independent
read-only review found and resolved a gallery/version-selection inconsistency;
no remaining actionable defect was found in that slice. No live Hermes task,
deployment or physical insertion was performed for this local result.

Exact focused command:

```powershell
python -m pytest tools/compose/tests/test_hermes_catalogue.py tools/compose/tests/test_media_gui_integration.py tools/compose/tests/test_hermes_settings_ui.py tools/compose/tests/test_hermes_layout.py -q -rs --basetemp .local/pytest-hermes-catalogue-review
```

This slice asks Hermes for a **metadata-only recommendation** and validates the
returned selection locally. Its prompt requests no remote tool use; it does not
establish a server-enforced restricted-tool agent.

Existing Hermes service regressions passed separately: **20 passed in 2.74 s**
outside the sandbox, using:

```powershell
python -m pytest tools/compose/tests/test_hermes_service.py -q -rs --basetemp .local/pytest-hermes-catalogue-service-unsandboxed
```

The initial sandbox run had 14 loopback/network-unavailable failures and six
passes; no source workaround was introduced. The separate results above retain
their own scope. The renderer comparison is research evidence and does not
establish a renderer selection or physical acceptance.

**Deployment:** today's [read-only Hermes preflight](2026-10-25-hermes-readiness.md)
passed development health (HTTP 200, explicit `ok`, `ready=true`) and authenticated
capabilities (HTTP 200, `hermes-agent`); Windows Tailscale backend/service were
running, self online, zero warnings. The development endpoint remains HTTP on
the private LAN. Exact active home-launcher/data-root ownership and runtime
Hermes configuration remain unknown today; yesterday's disabled/no-URL observation
stays dated evidence. Initial sandbox network/status failures were superseded by
the successful exact read-only checks outside the sandbox. No remote run, SSH,
endpoint/network/service change or deployment occurred. Private HTTPS/Tailscale
same-host/off-LAN acceptance, persistent media deployment, two-host sync, server
restore and reboot remain open. Git delivery is separate: the 17 earlier local
commits and reviewed B0/B1 checkpoint have now reached the feature branch at
verified `0d1dab3`; new B2 working changes are not covered by that delivery.

**Teaching Board B1, local foundations:** `board_model.py` and `board_store.py`
implement typed page/object snapshots, pinned media references, atomic
expected-revision batches, monotonic undo/redo, bounded durable history,
checksummed current/previous checkpoints and locked stale-writer rejection.
The focused model/store command passed **32 tests in 0.66 s**:

```powershell
python -m pytest tools/compose/tests/test_board_model.py tools/compose/tests/test_board_store.py -q -rs --basetemp .local/pytest-board-b1
```

Independent read-only QA found no remaining actionable defect after aggregate
payload/type validation and captured-save-revision hardening. Tests include
failed-batch/history invariance, concurrent/stale edits, interrupted replacement,
corrupt/missing/oversized-current recovery, orphan non-promotion and conflicting
writers. B1 itself provides explicit model/store APIs; B2 below adds the isolated
candidate editor/autosave/local image seam. Board microphone and live Hermes
composition remain unintegrated. An in-memory edit remains unsaved until a
successful captured checkpoint; saving must not claim a newer concurrent edit
was persisted.

**Teaching Board B0, local feasibility:** the [renderer trial](2026-10-25-teaching-board-renderer-trial.md)
and [runnable probes](../tools/compose/prototypes/teaching_board_renderer/README.md)
record Qt/PySide6 6.12.0 and pywebview 6.2.1/WebView2 launches in an ignored,
isolated environment. Each opened two actual native windows and passed six
synthetic fixture checks; two displays were enumerated. Final web checks also
passed window-bound pupil-role refusal and full frozen-snapshot invariance after
review fixes. The shared fixture and add/update/remove commands passed actual
B1 validation, while the probes still use a temporary memory-only adapter.

Independent review inspected source, result records and synthetic captures.
No remaining checkpoint-blocking defect was found. Qt wraps text where the web
canvas compresses a line; layout metrics/fidelity remain unresolved. Qt is only
the provisional next integration candidate, not the selected final stack. No
physical mouse/pen/touch/eraser delivery, projector placement or mixed-DPI recovery
was accepted, and no production editor/store integration was performed.

The reviewed B0 probes/evidence and B1 foundations formed the delivered checkpoint.
B2 now integrates those real foundations, rather than promoting the temporary
probe adapter. A separate session/controller owns audience snapshots, pupil
authority and save/dirty/recovery state; a separate provisional Qt candidate
provides the editor/views. Remote Board AI, voice and export remain B3/B4. B2
source and evidence require independent review before the next checkpoint.

**B2 session/controller:** `board_session.py` uses an owned copy of the actual B1
model and its store. It pins the complete pupil view during Freeze, constrains
pupil operations to live navigation/unlocked ink, rejects stale revision/session
tokens and exposes dirty state, captured durable revision, safe save failures and
previous-checkpoint recovery. Its bounded local image resolver checks immutable
references and byte hashes without retrieval/generation. Independent read-only
review found no actionable defect; **14 tests passed in 0.19 s**:

```powershell
python -m pytest tools/compose/tests/test_board_session.py -q -rs --basetemp .local/pytest-board-b2-session
```

**B2 provisional Qt candidate:** [candidate guide/evidence](2026-10-25-teaching-board-candidate.md)
records actual B1 model/store/session integration, a separate teacher/pupil
editor, token-bound gestures/forms, autosave/reopen/history, read-only Freeze and
strict isolated-root/pinned-media handling. Independent source/evidence review
found no remaining checkpoint-blocking defect after bounds, stale-form, save-only
gesture-refresh and session-lifetime fixes. The focused native suite passed
**13 tests, no skips, in 0.63 s** outside the sandbox for a real junction check:

```powershell
& .local/teaching-board-renderer-env/Scripts/python.exe -m pytest tools/compose/tests/test_board_candidate.py -q -rs --basetemp .local/teaching-board-candidate/pytest-candidate-final
```

The separate one-command native smoke opened two real windows, passed seven
synthetic session/store checks and exited successfully. Teacher/pupil captures
were visually reviewed. Applied commands autosave after 300 ms; property/name
drafts require their explicit Apply/Rename actions. At that checkpoint, image
support resolved only the pinned synthetic demo asset; the later
[image-insertion slice](2026-10-25-teaching-board-image-insertion.md) adds the
file/library chooser. Remote Board AI, microphone actions and export remain later. These
results do not establish physical pen/touch/eraser, projector/DPI, accessibility,
packaged installation, final renderer choice or classroom acceptance.

**B3 local fixture groundwork:** `board_hermes.py` prepares explicitly scoped
active-page text/layout and selected image metadata, then validates completed
saved-result proposals against the request UUID, context digest, lesson,
revision and session token. It applies one atomic undoable session batch.
Page removal, clearing/replacing all original objects (including reused IDs)
requires an external controller confirmation bound to the exact reviewed
proposal digest. Model-supplied confirmation fields are rejected; unsupported
whole-lesson replacement/deletion never executes.

Independent read-only review found no remaining actionable defect after
same-ID replacement and result-cap hardening. **36 focused tests passed in
0.98 s**, using actual local `HermesService.prepare/preview` fixtures and real
result extraction, with no HTTP request:

```powershell
python -m pytest tools/compose/tests/test_board_hermes.py -q -rs --basetemp .local/pytest-board-b3-review-final
```

The 48 KiB context limit fits `HermesService`'s 200,000-byte context boundary;
the 20,000 UTF-8-byte proposal limit fits its 20,000-character result extraction.
Oversized input requires narrower scope, not silent truncation or broader
authority. The generic Hermes panel's 12,000-character input limit is a separate
UI constraint; Board requests are not wired through it. No numeric live-backend
size limit or real Board-response acceptance was established. The trusted future
controller must obtain the immutable selection from `HermesService.preview`;
raw model output cannot supply context/status or confirmation authority. Prompt
instructions do not enforce remote tool restrictions. Live dispatch, Board UI,
PC-microphone commands and their physical/deployment acceptance remain open.

The B2 candidate and B3 local groundwork form the next reviewed working-set
checkpoint after delivered `0d1dab3`. Source/docs writes pause for root's freeze
and the separately authorised Luna delivery; no new push is claimed here.

**Physical:** basic page 7 controls and PC-microphone writing passed as described
above. Handheld audio, broader generated/refined-image Office checks, wireless
return feedback, printed enclosure fit and classroom release remain open.

Evidence: [device trial](2026-10-24-create-paste-device-trial.md),
[home acceptance](2026-10-24-home-acceptance.md),
[Gemini trial](2026-10-24-gemini-live-trial.md),
[provider plan](2026-10-24-gemini-image-provider-plan.md),
[permanent-route runbook](hermes-tailscale-home-work.md),
[today's Hermes preflight](2026-10-25-hermes-readiness.md),
[renderer trial](2026-10-25-teaching-board-renderer-trial.md),
[B2 candidate](2026-10-25-teaching-board-candidate.md),
[deployment kit](companion-deployment.md),
[SolidCraft pilot](dimensions/solidcraft/README.md),
[source-preview lifecycle](companion-installation.md),
[licensing research](research/2026-10-21-licensing-research.md) and
[adoption research](research/2026-10-21-adoption-research.md).

## Later participant Teaching Board feedback

The [manual feedback record](2026-10-25-teaching-board-manual-feedback.md) now
captures the user's A–R report and the exact private checklist has been updated.
A–E, G–M and P–R were reported as passes; F is a qualified functional pass with
image distortion requiring default aspect locking. N/O remain incomplete because
the save/close/reopen workflow was unclear. Pen, touch and second-display passes
are now participant evidence; stylus-eraser/palm-rejection and broader display
coverage are not inferred. The historical confirmed Next crash remains recorded;
the current navigation pass does not establish its root cause or a verified fix.

Requested next changes are mouse resize handles, default image aspect lock with
unlock (and the same default when video is supported), quick Ink/Erase buttons,
live text/property edits without repeated Apply clicks, and discoverable
save/rename/copy/reopen semantics. These entries record requirements, not completed
implementation or retests. No classroom, deployment or release gate is closed.

The user subsequently confirmed all three feedback design recommendations;
[the feedback record](2026-10-25-teaching-board-manual-feedback.md#confirmed-design-decisions)
captures resize/aspect policy, live-edit/grouped-Undo/quick tools and independent
Save a copy. The new source implements these candidate controls and a staged,
self-contained copy backend. Copy/reopen requires Resume while frozen; save is
still allowed without publishing the teacher's private edits. Independent
copy-flow review found no remaining actionable defect after that guard and
visible reopen guidance were added.

The integrated seven-suite native Board check passed **133 tests, no skips, in
4.54 s** outside the sandbox; the exact command is in the
[candidate guide](2026-10-25-teaching-board-candidate.md#local-verification-and-remaining-acceptance).
It includes the focused nine-test copy-backend suite. Separately, the coordinator
recorded **36 B3 fixture tests in 0.49 s** and an actual two-window smoke with
seven synthetic checks under
`.local/teaching-board-candidate/feedback-native-smoke-20261025-1536/`.
Counts overlap and are not added. Participant lesson/processes were not changed
for these checks. New controls require restart and fresh physical retests; N/O
remain incomplete and the historical native Next crash root cause/fix remains
unestablished. No deployment, classroom or release gate is closed.

## Saved-lesson discovery follow-up

The user subsequently reported missing named saves. A real native Save a copy
and folder-opening reproduction failed because the button opened only the
active UUID lesson folder; both independent saved checkpoints existed. The
[discovery fix](2026-10-25-teaching-board-saved-lessons-fix.md) adds a shared
repo-local saved-lessons folder with title-labelled reopen entries, preserves
existing stores and uses readable folders for future copies. Four participant
entries were populated; 21 existing checkpoint/media/launcher hashes were
unchanged. The integrated Board suites passed 141 tests in 5.30 s, no skips;
the generated Windows launcher passed a separate targeted check. Participant
retesting, N/O and the historical crash gate remain open.

## Teaching Board image insertion follow-up

The user prioritised **Add image** from the saved library or a local file,
followed by reliable placement, resizing, Undo and reopening. The
[bounded implementation/evidence guide](2026-10-25-teaching-board-image-insertion.md)
records the teacher chooser, preview, exact immutable library version selection,
read-only source access and lesson-owned bytes/provenance. Existing aspect
controls, Freeze, save/reopen/history and independent copies are reused.

Independent native integration passed **198 tests, no skips, in 7.89 s** before
the final library-search correction. Review found older assets were excluded
before matching in libraries over 500 entries; the fix searches before limiting
results and keeps an older canonical version selectable. The final focused image
selection passed **22 tests, no skips, in 5.47 s**; counts overlap and are not
added. The final sandbox run emitted a non-fatal native COM warning; the earlier
native integration and separately reviewed visible picker/teacher/pupil launch
were warning-free. No actionable review finding remains in this slice.

Synthetic lifecycle evidence includes source deletion, mouse/numeric aspect
resizing, Undo/Redo after reopen, independent copied media/history and a separate
Python-process reopen. These checks do not close participant N/O, new-control
physical retests, the historical crash investigation or classroom acceptance.
Wider B4 paste/drop/text imports, portable/PDF export and B3 live AI/voice remain
open. No participant lesson/process, firmware or deployment was changed.

## Working method for today's continuation

| Owner | Current bounded assignment |
| --- | --- |
| Coordinator | Priorities, user discussion and progress, evidence review and integration decisions against the agreed design. |
| `hermes_image_workflow` | B2 session and B3 local fixture adapter complete/tested/reviewed; all source writes paused for checkpoint. No remote/UI/microphone route. B0/B1 and earlier work delivered. |
| `programme_reconciliation` | Current docs reconciled; independent B2/B3 source/evidence QA complete. All writes paused for checkpoint; no source edits or commit/push. |
| `teaching_board_discovery` | B2 provisional Qt candidate/launcher/evidence complete: 13 focused passes, seven native smoke checks and read-only review; source writes paused. Physical input/display/final selection remain open. |

Review source changes before integration; record local, remote and physical
results separately. Recompute the next frontier after each result or user
decision. Deployment/physical blockers leave independent local work available.
