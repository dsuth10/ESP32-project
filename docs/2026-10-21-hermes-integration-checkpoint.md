# Hermes integration development checkpoint

21 October 2026. Built from `f512a9f` on
`codex/companion-hermes-integration`, an isolated continuation of
`codex/companion-media-agent`. The original feature worktree belongs to another
chat; the original working folder remains on main with its existing changes.
No main merge, original-worktree overwrite or S3 firmware write occurred.

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
- A separate loopback Linux media service template, reviewed staging tool,
  private environment example and verified no-overwrite backup/restore.
- Source-preview install/update/rollback/removal with archive/hash validation,
  Windows path and ancestor-junction guards, edited-source preservation and
  separate user data. Packaging excludes private consultation reports.

## Verification and limits

The complete local command passed **249 tests, 3 skipped and 4 subtests**:

```powershell
python -m pytest tools/compose/tests tests server/tests server/deployment/tests .agents/skills/hermes-collaboration/scripts/test_linux_hermes_client.py .agents/skills/hermes-collaboration/scripts/test_migrate_linux_hermes_endpoint.py -q -p no:cacheprovider
```

The three skips are Windows symbolic-link creation fixtures. Real Windows
directory-junction packaging guards were exercised successfully. These totals
include existing image, writing, history, board and media suites; do not add the
earlier 164-test checkpoint to them.

Native Tk checks exercised both panel sizes, 920 × 740 and 720 × 640, and
Settings' modal grab/scrolling. A real Windows DPAPI round trip used synthetic
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
