# Consultation lessons

These notes record what was observed during the authorised October 2026 consultation. They help plan the next interaction; verify any state that may have changed.

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

The full consultation record is docs/research/2026-10-21-hermes-consultation.md. It includes historical endpoint and environment details. Keep it linked locally and out of public reports. Do not copy endpoint values, credentials, private user names or paths into this skill or other tracked source.
