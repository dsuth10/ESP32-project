# Unified desktop settings and image repair

28 October 2026. User-authorised repair on `codex/companion-media-agent`, following
the [diagnosis](2026-10-28-unified-desktop-image-settings-diagnosis.md).

## Behaviour

The embedded Voice workspace now hands keyboard focus to explicitly clicked
editable Tk controls before their normal widget bindings run. It does not force
focus on a timer, into separate modal windows, while a control owns a grab, or
while shutdown/settings protection blocks input. The existing external Office
target exclusions and guarded insertion behaviour remain in force.

**Board settings…** explicitly selects saved Voice settings or another protected
feature profile, reloads the saved selection, or returns to local-only operation.
The Board displays its effective mode and image configuration requirements.
Settings are applied between operations without changing the lesson, history,
Freeze snapshot or pupil view. A remembered selection contains a profile folder
and service fingerprints for recovery, with no raw key or service URL. It lives
in the feature companion profile, persists across saved-lesson switches/relaunches
and is excluded from lesson exports. Keys remain in Windows-protected settings.
Applying or reopening settings never submits an image/model request.

Missing or unreadable remembered settings leave a usable local-only Board with a
visible explanation. Active recordings, workers and unreviewed page previews
retain their original configuration until their operation has finished.
Invalid service settings also retain the recovery controls. Unfinished receipts
can reconnect to restored original service settings; endpoint or credential
replacement is blocked until the original work is reconciled.
New paid-attempt receipts pin their own immutable budget-service fingerprint,
independent of mutable preferences shared across lessons. Older receipts without
a fingerprint have an explicit local review route for the exact saved job and
original provider outcome. It clears only the local automatic-attempt barrier;
allocations/accounting stay unchanged and no identity is adopted or job replayed.

Concurrent metadata backfill and image acquisition now converge on the same exact
catalogue version. On an insert collision, indexing re-reads the committed winner
and checks its immutable identity, title, tags, metadata and provenance. Review
decisions and availability are preserved; a conflicting version is still rejected.
This repairs the reproduced post-generation catalogue race without repeating a
provider request or relaxing catalogue idempotency.

Image errors distinguish a blocked image from missing chart data. Automatic Board
illustrations explain their Google Gemini/1K restriction and validate prerequisites
before creating an image job: generation enabled, key/model/options, a positive
allocation of at most **50 AUD cents**, and shared budget configuration. Actual
model and ledger availability remain unverified until checked. Every dispatched
attempt retains the existing reservation, uncertain-outcome and first-use preview
rules. OpenAI/larger Google images remain separate Voice image-library actions.

## Validation record

The coordinator's end-to-end fixture uses real protected-settings selection,
Board UI/controller/resource acquisition and persistence. Its model, image
provider, budget ledger and credential cipher are deterministic stand-ins. It
verifies one dog-image attempt, an unchanged pupil page before acceptance, explicit
first-use preview, publication, Undo/Redo, save/reopen, remembered configuration
and no replay. This is local engineering evidence, not Google quality/billing or
classroom acceptance.

The production shared shell also passed a disposable local-only GUI check:
masked Google-key entry and a numeric allocation accepted real keystrokes, Save
protected and reopened the dummy values, Board settings selected/reloaded that
saved profile, and the frozen pupil snapshot stayed unchanged. Normal Save and
close exited the owned Voice process and hid the pupil window. The focused native
probe additionally verified Tab/Shift+Tab, copy/paste, editable and readonly
dropdowns, multiline text, workspace return, external-window return and selection
preservation. Transient Tk modal typing was limited by automation targeting;
modal opening and grab/non-interference checks passed separately.

The independent review repaired invalid-service startup fallback, recovery
reconnection, cross-library pending-attempt binding and older-receipt local review.
The catalogue race was reproduced with two callers forced to miss the same
version before either committed; the original implementation failed and the
repaired implementation passed, including separate library instances and a
negative case with a genuinely conflicting immutable title.

Final results (separate suites, not an additive release total):

| Check | Result | Limit |
| --- | --- | --- |
| Complete Board tests plus unified desktop | 597 passed, 2 skipped | Offline fixtures, including settings/recovery, dog-image preview, concurrent indexing, persistence and export. |
| Gemini/provider routing plus companion embedding/focus | 96 passed | Simulated transport, synthetic credentials and local focus/lifecycle cases. |
| Packaging, settings transitions, protected settings and configuration loading | 41 passed, 1 skipped | Disposable install/update/rollback data; Windows file-symlink creation remains privilege-dependent. |
| Native host suite | 9 passed | The existing Windows COM diagnostic still appears despite exit code 0; no broad native-stability claim. |
| Actual Windows DPAPI round trip | Passed | Disposable dummy key only; plaintext excluded from public settings and protected-file bytes. |
| Complete production shared-shell GUI | Passed | Disposable local-only profile; actual masked/numeric typing, protected save, Board selection/reload, Freeze preservation and orderly child/Board/pupil shutdown. |

Some earlier broad runs caught a Windows sharing-denial diagnostic and the
post-generation indexing race. The sharing-denial test passed its targeted rerun;
the indexing race was fixed with a deterministic regression before the final
complete Board pass. No temporary diagnostic instrumentation remains in the
application or end-to-end test.

See the [teacher guide](2026-10-28-unified-desktop-guide.md) for the
save-Voice-settings then reload-Board workflow.

## Scope

The source repair preserves the stable firmware, registered identities, main,
existing lessons and credentials. No real image-provider call, physical audio
recording, remote task, deployment or firmware write is part of this repair.
Live Google access, budget-service deployment, physical Office/handheld/projector
and classroom acceptance remain separate programme gates.

The verified local handover archive is
`.local/classroom-companion-settings-repair-2026-10-28.zip`; its independent receipt
records the archive hash. It is a source preview, not an installed deployment or
stable release. Restart an already-running application to load the repaired code;
no user window was forcibly closed and no unsaved user settings were discarded.
