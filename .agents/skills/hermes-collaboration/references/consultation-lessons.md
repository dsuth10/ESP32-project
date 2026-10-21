# Consultation lessons

These notes record what was observed during the authorised October 2026 consultation. They help plan the next interaction; verify any state that may have changed.

## Current direction after the consultation

The [consolidated programme](../../../../docs/2026-10-21-companion-media-agent-master-plan.md) now requires the same Linux Hermes over permanent private Tailscale for home/work. Follow the [connection runbook](../../../../docs/hermes-tailscale-home-work.md) for staged deployment/acceptance and safe endpoint migration. Existing observations below remain dated evidence; do not convert prior LAN success or an inactive-service observation into a current network-state claim. No credential, endpoint or request identity was changed by this documentation update.

## Connection and identity

- Direct API calls to the supplied Linux LAN endpoint worked. Remote-peer registration was unnecessary. Earlier, a local Hermes gateway was reachable too, but that did not mean it ran on or proxied to Linux.
- The authenticated Linux API identified itself as hermes-agent and returned capabilities, models and toolsets. This confirms authenticated API access, not that every advertised tool works or that the responding process is the intended physical host.
- Tailscale was reported online on Windows at the time, while the Linux user-level check found tailscaled inactive. LAN reachability was observed; a working Tailscale route between home and work remains unverified. Do not publish or expose a service to solve that uncertainty.

## Response quality and evidence

- An authenticated HTTP 200 from the local gateway contained malformed tool-like text rather than a useful review. A later model selection returned a structured review. Always assess useful, correct work separately from HTTP status.
- A later bounded Linux inventory showed Linux x86_64, Python 3.14.7, about 374 GB available on the checked filesystem, and a running user-level systemd manager. The physical host, persistent storage location and backup plan were not attested.
- The serving runtime identified openai/gpt-6-luna through the configured OpenRouter provider. This is evidence about that run, not a stable model setting.
- A combined inline Python diagnostic was refused by the security scanner. A subsequent read-only inventory used separate, simple commands. This did not authorise bypassing the scanner: narrow or simplify a blocked check once, then report it unknown if still blocked.
- A refusal of python3 -m pip show fastapi uvicorn was a terminal-tool policy response, not evidence that the packages were absent. The sqlite3 command being missing likewise says nothing about Python’s sqlite module.
- The Linux check found tailscaled inactive. This does not prove every possible installation or route absent. Keep the LAN result and Tailscale result distinct.
- An approval attempt returned HTTP 409 because its run had already completed. No approval-policy change was made. Check the current run and approval identity immediately before any approval.

## Design and scope

- Keep the application-owned media-library API separate from Hermes’s own API. Preserve immutable versions and an explicit canonical pointer; idempotency prevents duplicate effects but does not resolve competing edits, so use expected revisions and explicit conflict handling.
- Use a durable outbox, cached media for offline use, and sync media plus metadata only. Windows retains ownership of cursor and clipboard control.
- Recommendations for SQLite metadata, immutable content-addressed blobs, canonical revisions, delta sync and shared budget reservations are design suggestions, not deployed infrastructure.
- Private Linux hosting, package compatibility, persistence and backup, application credentials, and the intended private home/work route still require verification before deployment.

## Sources and privacy

The tracked consultation record is `docs/research/2026-10-21-hermes-consultation.md`; publish only sanitised findings. Raw connection details and run receipts belong in ignored `.local/` records. Audit unpublished history as well as the current file before pushing. Do not copy endpoint values, credentials, private usernames or paths into this skill or other tracked source.


## Later host verification and helper staging

Observed on 21 October 2026; these are dated results, not assumptions for the next session.

- The established authenticated LAN API reached the intended Linux Hermes. The user independently attested its SSH fingerprint. A visible online Linux tailnet peer presented a different fingerprint. That peer was not accepted as the same host, no SSH host key was accepted, and the LAN API remained the valid development route. Resolve identity before configuring a permanent endpoint.
- A bounded own-host inventory found no Tailscale executable in the checked paths, an inactive `tailscaled`, and unavailable non-interactive sudo. This did not remove API access or prove that every possible installation was absent. Privileged setup needed a local administrator handoff.
- Tell Hermes to inspect its own host explicitly. Separate host identity, installation, listener, privilege and service-readiness questions so a blocked check does not invalidate independent evidence.
- Inline diagnostic code and a grouped shell existence check triggered scanner refusals. One narrower follow-up used a simple directory check, the dedicated file writer, then separate syntax and hash commands successfully. Do not treat that success as permission to route around a future refusal.
- A bootstrap helper was staged without replacing an existing file; shell syntax and matching SHA-256 were reported. It was not executed for privileged setup. Keep actual paths, hashes and execution receipts private, and verify them again before use.
- A pending command disappeared when its run completed before approval. The client refused the stale approval. Re-poll immediately before granting a one-time approval; do not revive a completed run or substitute a broader approval.

## API lifecycle observations

- Capabilities advertised run submission, status, idempotency, stop and SSE events. An events request for a finished cancelled run returned HTTP 404 while its run status remained readable. Treat event availability and run existence separately, preserve the status result and avoid duplicate dispatch.
- Completed responses used the `output` field. Review the bounded content and actual evidence, rather than interpreting an empty `message` field as missing work.
- A stop request first returned `stopping`; cancellation required a subsequent terminal-state poll. Include `interrupted` among terminal states.
- A companion runtime and endpoint migration helper were implemented and tested on the continuation branch. Their existence is branch-specific and does not prove installed services, persistent private transport, or home/work acceptance. Consult the current consolidated programme rather than copying a historical implementation claim.
