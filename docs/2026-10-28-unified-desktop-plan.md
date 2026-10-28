# One teacher window: Classroom Companion and Voice Companion

28 October 2026. User-authorised implementation on `codex/companion-media-agent`.
This plan adds a shared desktop interface to the current programme; it does not
close its deployment, provider, physical-input or classroom acceptance gates.

## Intended result

One teacher application window has two clearly labelled workspaces:

1. **Teaching Board**: the existing complete teacher editor, lesson controls,
   dedicated Board requests, reusable resources, profiles and exports.
2. **Voice companion**: the existing Compose & Dictate, Ask/Manage, Hermes tasks,
   History & saved text, Image library and Settings interface.

The existing pupil presentation stays a separate optional window, including its
display selection, live annotation/navigation and complete Freeze snapshot.
Switching teacher workspaces never changes, hides, resumes or republishes the
pupil lesson. Private teacher conversations never become presentation content.

## Design decision and preservation contract

The existing Board uses Qt; the voice companion uses Tk. First prove native
Windows hosting of the existing Tk window inside a Qt workspace. Retain separate
event loops/processes behind a small host interface. This preserves the complete
voice interface and its existing workflows, rather than duplicating every panel
and its state in a second toolkit. Native hosting must be demonstrated, not
assumed from a mock. If it cannot be made reliable, stop this integration route
and record the evidence before choosing a full Qt interface migration.

The shell owns navigation and orderly application shutdown. The Board owns its
lesson/session/pupil display. The voice process owns its providers, protected
settings, microphone pipeline, History, image jobs, receiver and device listeners.
Use bounded local process messages for lifecycle and non-content status only;
do not introduce remote control, arbitrary execution or a second agent route.

Preserve:

- Every existing control within both workspaces, including modal previews and
  file dialogues; retain the standalone launch routes for recovery.
- Current lesson identities, revisions, Undo/Redo, autosave, saved-request
  recovery, media provenance, portable packages, charts and PDF output.
- Voice focus/selection checks, Paste Ready, Word/OneNote insertion distinctions,
  explicit paid attempts, immutable image versions and uncertain-job recovery.
- Separate Board lesson/resource storage and companion History/media/settings.
  Open the existing feature companion profile without copying or merging data.
  Do not read or write stable reference data. Board provider configuration stays
  explicitly selected; settings changes do not silently reroute Board work.
- Existing cloud/local policies, Groq primary, bounded Hermes requests, private
  credentials, service separation and firmware guards.
- S3-only support. No firmware, registration, deployment, provider trial, model
  download, stable release, merge or push is part of this change.

## Delivery slices and owners

| Slice | Work | Owner | Required evidence |
| --- | --- | --- | --- |
| U1 | Inspect architecture; prove Windows Tk-in-Qt hosting, sizing and lifecycle. | Native-host sub-agent | Actual foreign native child window under the teacher shell; failure visible without a duplicate process. |
| U2 | Add embedded companion entry and bounded lifecycle protocol; exclude shell/pupil windows from external document targets. | Companion-runtime sub-agent | Standalone regression checks; host/pupil focus cannot capture/paste teacher content; shutdown veto survives. |
| U3 | Add Qt teacher shell, two workspaces, pupil preservation and coordinated save/close. | Coordinator | Switching retains both workspaces and frozen pupil state; veto leaves both usable; successful exit closes owned processes. |
| U4 | Add process-safe microphone ownership at the existing audio-capture seam. | Coordinator | Concurrent requests cannot open two streams; worker-thread stop and process exit release ownership. |
| U5 | Add one launcher/setup route, dependency checks and exact package entries; retain standalone paths. | Coordinator | Clear missing-dependency failure; no automatic download at normal launch; secret-free package verification. |
| U6 | Independent regression and implementation review, native smoke evidence and handover. | Review sub-agent and coordinator | Relevant suites pass; actual native shell/child/pupil checks; limits and manual acceptance recorded separately. |

Workers share this checkout with disjoint file ownership. The coordinator reviews
and integrates their final changes; unrelated existing Graphify output is left
untouched. Later review findings are repaired before handing over the candidate.

## Integration details

### Window and focus ownership

Use the existing Board widget inside the teacher shell and a native child-window
container for the existing voice window. Retain its nested tabs. Do not create
two independent floating teacher windows and label that integration complete.
Ensure child file/message dialogues remain usable above the teacher window.

Register the shell process as internal in the companion's focus tracking;
the separate pupil window belongs to the same process. Exclude these windows
from remembered Office destinations and selected-text capture. Retain genuinely
external Word/OneNote destinations and explicit Paste Ready behaviour. The
shell must not silently turn Compose/Dictate into Board-editing commands.

### Lifecycle

Preflight closure without destroying either workspace: finish/save pending
Board edits and allow an unsaved-change veto; ask the voice workspace whether
settings/recording/active operations prevent closure. Veto leaves the lesson,
voice runtime and pupil display intact. Route Board's embedded Save and close
button through the shell. Commit closure only after both sides agree. Never
force-terminate an active paid attempt to make the window disappear.

If the voice child exits unexpectedly, keep the Board and pupil lesson alive,
show a useful error and allow an explicit restart after that owned process exits.
Never launch a replacement while the earlier child is still running. Opening
the shell does not clear persisted queues or replay uncertain jobs.

### Microphone

Both workflows retain their existing microphone controls and transcripts.
Acquire one OS-backed file lease before opening the PC microphone so Board
recording and background companion hotkeys cannot race. Release after stream
closure, including start failure and stop from another thread. OS process exit
must release the lease. Show a useful busy message; do not forward recordings
or transcripts between workspaces.

### Data, configuration and installation

Default Board location remains the existing isolated review lesson; default
companion storage remains the existing feature profile. Explicit overrides are
available for isolated testing. No schema migration or data import is required.
Keep separate standalone launchers and a new unified launcher. Normal launch
checks local dependencies and explains setup if missing; setup is explicit and
uses the checkout's isolated environment. Preview packaging includes new sources,
launchers and this guide without settings, data, keys, logs or private evidence.
The provisional Board data/runtime remains per checkout or installed source
release. Source-preview updates retain old files but do not migrate Board data
into the new release; automatic installed-update continuity remains unaccepted.

## Acceptance matrix

Automated/native local evidence:

- Real Qt teacher shell contains the complete existing Tk companion; resize,
  switching and process lifecycle work; the pupil remains a separate window.
- Board edits, autosave/reopen, Undo/Redo and Freeze/Resume retain their existing
  model/session behaviour through the shared shell.
- Voice buttons and all existing panels remain reachable; trusted host/PID
  validation rejects mismatched native windows and internal focus targets.
- Shutdown veto (settings/recording/unsaved failure) leaves both workspaces alive;
  normal closure stops the owned voice runtime and Board timers/session.
- Microphone contention, cross-thread release and process-death release pass
  without recording real audio or making model calls.
- Child start failure/crash is visible; explicit restart cannot duplicate it.
- Existing companion, Board, package and setup checks appropriate to the changes
  pass. Record exact results once run, not anticipated totals.

Separate manual acceptance remains: actual Word/OneNote focus/paste, microphone
and handheld input, Tk modal dialogues, pen/touch, Windows scaling, second display
and projector, sleep/reconnect and normal lesson rehearsal. Live Hermes, sync,
paid image quality/cost, signed distribution and classroom acceptance remain
the original programme gates. Local synthetic checks do not close them.

## Rollback

Use the preserved standalone Board and companion launch routes. The unified
interface does not convert their stored files, so lessons, History, image
versions, protected settings and recovery records remain usable independently.
Do not resolve a regression by disabling insertion/provider/firmware safeguards.

## Implementation evidence

Delivered locally on the feature branch:

- `tools/compose/unified_desktop.py`: Qt teacher window, Board/Voice workspaces,
  in-window saved-lesson selection, independent pupil display and coordinated
  non-destructive close preflight.
- `companion_host.py` / `companion_embedded.py`: complete existing Tk companion
  hosted as a verified native child, bounded local lifecycle messages, hidden-tab
  remapping, resize, retry, close consent and normal standalone detach recovery.
  Windows virtual-environment launch retains the chosen environment while
  avoiding the redirector process that would break strict PID ownership checks.
- `audio_lease.py` / `audio_capture.py`: OS-backed shared microphone ownership,
  visible contention, start-failure release and cross-thread stop support.
- `desktop_instance.py`: lesson/profile ownership before opening; standalone
  Board and unified windows share lesson locks. Save-copy/import/saved-lesson
  transitions claim their targets before opening them. Lock files sit outside
  prospective lesson directories so atomic copy/import still works.
- Existing focus tracking excludes the teacher and pupil processes from
  document selection/capture, automatic delivery and remembered Office targets,
  including after normal host detach. The original external-target checks remain.
- `start_companion.bat` / `start_classroom_companion.bat` and the new PowerShell
  launch/setup routes: one main entry, read-only dependency discovery, explicit
  setup and preserved standalone recovery. Preview packages carry both
  workspaces and select the right unified/legacy entry on update and rollback.

Recorded checks (separate suites, not an additive release total):

| Evidence | Result | Limit |
| --- | --- | --- |
| New shell, microphone, native-host and unified-package checks | 44 passed | Synthetic input, temporary data; includes actual native Tk hosting. |
| Existing complete Board regression suite | 504 passed, 1 skipped | Offline fixtures and native Qt; no physical pen/touch or projector claim. |
| Companion core/service regression suite | 326 passed | Local HTTP fixtures, synthetic provider responses and no physical recording. Native Tk layout fixtures run separately. |
| Existing native companion layout/UI cases, each in a bounded subprocess | 14 passed; no skips/timeouts/crashes | Hermes layout 2, image/settings/responsiveness 8, History/library 4. Synthetic provider responses only. |
| Final source-preview package suite | 22 passed, 1 skipped | Install/update/rollback/removal and injected transient/persistent Windows publication denial. |
| Windows launcher checks plus existing Board candidate checks | 18 passed | Three read-only Windows PowerShell dependency checks; no installer/provider call. |
| Full native combined application smoke | 13 checks passed | Real existing ComposeApp, synthetic lesson and local-only disposable profile. |

The native smoke verified one teacher window, a separate pupil window, hidden
voice controls while the Board is selected, native child ancestry when shown,
resize and repeated tab return, private edits with a preserved frozen pupil
snapshot, saved lesson and orderly child/Board/pupil shutdown. Window-scoped
captures were inspected at `.local/unified-desktop-evidence/smoke-unified-9a276b9086/`;
`result.json` records exact checks. Normal EOF detach recovery was checked
separately under `.local/unified-host-probe/`. Hard process-kill/power-loss
recovery is not established by those checks.

Initial restricted-sandbox loopback failures were rerun with local fixture
networking available. The complete Board/launcher checks also required ordinary
Windows script/junction access outside the restricted sandbox. No transport or
path-validation safeguard was weakened for tests. The final package checks
include bounded retry of a reproduced Windows directory-publication denial;
persistent denial preserves the current verified release and launcher.

An existing mixed native Tk-layout/threaded-service test sweep encountered a
Windows native breakpoint rather than a Python assertion; a combined layout
process also stalled and only that verified, synthetic fixture was stopped.
Service fixtures passed separately, and all fourteen native layout/UI cases
passed in their own bounded subprocesses. Per-case outputs, exit codes and
timings are retained in `.local/native-layout-isolated-20261028/result.json`.
The combined pytest process instability remains unresolved; isolated results
and the actual complete-application smoke are reported separately. This does
not close physical native-input/dialogue or hard-crash acceptance gates.

Final reviewed package publication uses up to five bounded retries (0.75 s total
delay) for specific Windows access/sharing denials while the destination remains
absent. A persistent denial never activates the new release. The standalone
package suite passed after injected transient/persistent failure verification.

U1–U6 are implemented, integrated and independently reviewed locally. The source
preview contains 166 allowlisted files, verified by SHA-256, with no credentials
or local data included. The handover archive is
`.local/classroom-companion-unified-preview-2026-10-28-final.zip`; its independent
receipt records the archive digest. This remains a source preview rather than a
signed installer or a release approval.

No provider calls, real microphone recording, remote Hermes task, firmware
write, deployment, stable release, merge or push was performed. Existing
Graphify changes were left untouched. Physical Office/handheld/input/display,
modal/keyboard/DPI, installed-update continuity and classroom gates remain open.
