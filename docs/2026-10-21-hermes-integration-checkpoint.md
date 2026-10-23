# Hermes integration development checkpoint

21 October 2026. Historical implementation evidence, originally built from
`f512a9f` on the temporary `codex/companion-hermes-integration` continuation.
This work and the saved workspace have since been consolidated into
`codex/companion-media-agent`, which is now the single development branch.
`main` remains the stable reference; the original S3 firmware remains unchanged
and write-locked. Earlier checkout descriptions below refer to the checks at
the time, rather than the current two-branch layout.

## Implemented

- A product-owned Hermes adapter and explicit task panel, separate from Groq
  Ask/Manage. Selected task/context only; no automatic History transfer,
  remote approvals, document insertion or remote job on startup.
- Protected Hermes settings, connection diagnostics and capability checks.
  Origin-only HTTPS, no redirects/proxy discovery, bounded replies/events,
  and remote idempotency capability required before dispatch.
- Durable previews, immutable payload hashes, endpoint/credential binding,
  run receipts, polling/events, cancellation requests and deliberate result
  queueing. Uncertain retries retain their original identity; stale locks
  require reconciliation. Terminal results survive stale/unsupported events.
- Crash-recoverable settings/public-DPAPI transactions with an OS-released
  process lock. Saving waits for sync quiescence; new work cannot start during
  the transition. Local-only disables remote routes and pauses only the
  feature-owned voice receiver. Existing independent production listeners stay
  outside this feature's authority.
- Safe developer endpoint migration and guarded rollback without replacing
  credentials; unresolved dispatches block migration in either direction.
- A separate loopback Linux media service template, source-hashed staging,
  private environment example and verified no-overwrite backup/restore. The
  reviewed installer checks prerequisites/collisions, copied hashes, systemd
  validation and authenticated readiness before marking its new instance active.
  Receipt-bound rollback only stops/disables that instance and preserves data.
- Source-preview install/update/rollback/removal with archive/hash validation,
  Windows path and ancestor-junction guards, edited-source preservation and
  separate user data. Packaging excludes private consultation reports.

## Verification and limits

The complete local command passed **263 tests, 3 skipped and 8 subtests**:

```powershell
python -m pytest tools/compose/tests tests server/tests server/deployment/tests .agents/skills/hermes-collaboration/scripts/test_linux_hermes_client.py .agents/skills/hermes-collaboration/scripts/test_migrate_linux_hermes_endpoint.py -q -p no:cacheprovider
```

The three skips are Windows symbolic-link creation fixtures. Native action-bound checks passed at both supported sizes in this final combined run. Real Windows
directory-junction packaging guards were exercised successfully. These totals
include existing image, writing, history, board and media suites; do not add the
earlier 164-test checkpoint to them.

Native Tk checks exercised both panel sizes, 920 × 740 and 720 × 640, and
Settings' modal grab/scrolling. Native nested-notebook checks also verify every Hermes action remains within the supported window bounds. A real Windows DPAPI round trip used synthetic
credentials. Full companion startup/shutdown used disposable data, disabled
hardware/receiver inputs and instrumented HTTP methods: zero HTTP calls.
These checks do not establish teacher accessibility or physical speech.

The recovery fixture starts the real media HTTP API, stores a PNG and version
event, stops/joins the writer, backs up, restores into a new folder, starts a
fresh API and retrieves the exact metadata/blob. This proves a local fixture
recovery path; Linux ownership, systemd operation, reboot and two-host sync
remain separate acceptance gates.

## Current connection evidence

Windows Tailscale was running with an online Linux peer. The existing configured
Hermes API returned authenticated readiness and advertised run submission,
status, idempotency, stop and events. Its configured route uses HTTP and does
not match the Tailscale peer. No private HTTPS endpoint was migrated.

A bounded read-only Linux inventory reached a remote security guard on an
inline diagnostic. No approval was granted. The exact run was stopped and
subsequently confirmed cancelled. Event retrieval returned HTTP 404 despite
the advertised capability; the runtime now preserves polling/terminal results
when an event route is unavailable. No Linux service or tailnet change occurred.
Private request/status/stop receipts remain ignored in the original checkout;
no endpoint, key or private hostname is copied into this record.

## Verified host identity and administrator prerequisite

The user independently checked the intended Linux computer's public SSH
fingerprint. The existing LAN Hermes endpoint's SSH identity matches that
attestation; the previously visible Linux Tailscale peer presents a different
identity and is excluded from deployment. No key was accepted, no SSH login
occurred and no trust record was changed. Continue using the existing
authenticated LAN Hermes collaboration client, not the unrelated peer.

That verified LAN agent subsequently reported its own fingerprint match,
Tailscale absent from the checked paths, tailscaled inactive, no listeners on
443/8443/8765, and the existing Hermes listener on 8642. Its non-interactive
privilege check failed. The authenticated API remains usable for bounded
development; installing/enrolling Tailscale needs a local Linux administrator.

An ephemeral, syntax-checked three-stage bootstrap helper was prepared in the
ignored development area from the wizard template. It validates the physical
host attestation, downloads the official Tailscale installer for human review,
then asks the human to run local sudo/enrolment. It does not configure Serve,
SSH trust, ACLs, exit nodes, application services or firmware. This is a manual
administrator prerequisite, not a completed transport deployment.

## Remaining delivery gates

M1: attest the intended Linux host/owner, inventory existing listeners and Serve
configuration with approved simple commands, review scoped HTTPS/service
changes, deploy, then prove restart/denial/reconnection at home, hotspot and
work. The [deployment kit](companion-deployment.md) is ready for that review.

M2: accept the adapter against that permanent route and real bounded tasks.

M3: install the library service, provision separate protected credentials and
durable storage, prove actual Linux restore and two actual Windows stores.

M4/M5: explicitly authorised paid quality/refinement/billing checks, real
Word/OneNote focus/selection/undo/save-reopen, both microphones and original S3
regressions. No paid provider operation or firmware trial occurred here.

M6/M9: installed teacher pilot, dependency/school/accessibility checks, ownership
and licence clearance, reproducible signed packages and public-release approval.
This is a tested source preview, not a completed public image release.
M7/M8 remain the later programme described by the master plan.

Use [the programme dashboard](2026-10-21-companion-media-agent-master-plan.md),
[connection runbook](hermes-tailscale-home-work.md) and
[installation guide](companion-installation.md) for the next checks.

## Main reconciliation: 24 October 2026

Reconciled `main` commit `4f07c0b` into `codex/companion-media-agent`.
The shared configuration loader now retains feature defaults, assistant/History
options, protected credentials and process overrides. Existing Hermes/server
environment files supply Groq settings only; they cannot activate feature
listeners or redirect Hermes/media. Hermes tokens remain protected-settings-only.

Imported CUDA readiness checks and isolated GPU transcription, including CPU
fallback when automatic GPU selection fails. GUI Compose/Dictate and Paste Ready
can restore a remembered external window on an explicit gesture, checking its
process and title. Automatic asynchronous delivery retains the original control
lock and does not pull focus back after a window switch. Image destination and
caret guards remain unchanged. Fixed the imported thread-ID lookup to use
Windows kernel32 rather than user32. Window titles are not added to logs.

Fresh local verification:

```powershell
python -m pytest tools/compose/tests tests tools/tests server/tests server/deployment/tests .agents/skills/hermes-collaboration/scripts/test_linux_hermes_client.py .agents/skills/hermes-collaboration/scripts/test_migrate_linux_hermes_endpoint.py -q -p no:cacheprovider --tb=short
```

**302 passed, 3 skipped, 14 subtests passed.** The skips are Windows symbolic-link
creation fixtures. This command includes board-safety tests; it supersedes, rather
than adds to, earlier test totals. Regression cases cover configuration precedence,
protected Hermes tokens, changed-focus queueing, failed explicit focus restoration,
and tracking the last external window while hardware inputs are disabled.

At home, the guarded read-only preflight matched the connected device to the
registered S3; its stable write lock remains set. No firmware or registration
change occurred. Windows lists the MacroPad Bluetooth device with status OK;
that listing alone does not verify a physical button event.

The native feature companion launched with all five main tabs and both assistant
panels present, with a responding UI event loop. Session-only hardware hotkeys
were enabled after checking for duplicate companion processes. Feature data is
separate; receiver startup, media sync, Hermes dispatch and paid images were kept
disabled for this launch. Groq configuration is available. Physical recording,
speech quality, foreground insertion and classroom acceptance remain open.
Remote transport and Linux deployment were not changed or revalidated here.
