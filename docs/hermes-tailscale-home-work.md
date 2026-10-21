# Permanent Hermes connection over Tailscale

21 October 2026 — required deployment plan and acceptance runbook, **not completed configuration**.

This installation will reach the same existing Linux Hermes from the Windows companion at home and work. Groq stays the primary embedded assistant. Hermes is an additional integrated capability for this user; core writing and other teachers' installations need not depend on it. The original S3 firmware stays stable/write-locked.

## Meaning of permanent

Saved private endpoint and protected credentials on every authorised Windows installation; Linux/Tailscale/Hermes restart recovery; clear readiness status; bounded recovery after a network change; authenticated access from real home and off-LAN work/hotspot contexts. This does not mean unsolicited agent jobs or automatic transfer of all conversations.

Tailscale runs on the Windows and Linux computers. No ESP32 Tailscale client, subnet router, exit node or firmware change is required for this desktop-to-server design. The destination must still run its service. [Device connections](https://tailscale.com/docs/how-to/connect-to-devices)

Historical authenticated LAN communication and the previous inactive Linux Tailscale observation are consultation evidence. Neither proves current service state or off-LAN access. No network settings change through this document.

## Topology and responsibilities

| Component | Connection/role |
| --- | --- |
| Original S3 | Existing BLE controls and local Wi-Fi receiver; no Hermes/provider credentials. |
| Windows companion | Input, Groq-primary workflow, local History/cache, permissions and Office insertion. |
| Linux Hermes | Stable private HTTPS origin over Tailscale; explicitly requested bounded agent tasks. |
| Linux media API | Separate HTTPS origin/port, bearer key and durable storage; images, metadata, conflicts and budget ledger. |

Use a full tailnet DNS identity rather than changing LAN addresses. MagicDNS generates device FQDNs; renaming the host is a reviewed connection change. Actual private values stay in ignored configuration. [MagicDNS](https://tailscale.com/docs/features/magicdns)

**Proposed listener arrangement, pending inventory:** tailnet-only HTTPS port 443 proxies to Linux Hermes loopback port 8642; a separate HTTPS listener, such as 8443, proxies to the media API on loopback port 8765. Check existing listeners and Serve rules first. Separate origins preserve the current Hermes helper's origin-only base-URL contract and avoid overlapping `/v1` routes.

Tailscale Serve supplies a private reverse proxy; retain bearer authentication at both applications and limit effective tailnet access. Public Funnel and router port-forwarding are outside this design. [Serve](https://tailscale.com/docs/features/tailscale-serve), [access control](https://tailscale.com/docs/features/access-control)

Serve's documented `--bg` mode persists across restarts; it does not supervise Hermes or the library server. Verify installed-version flags, reboot behaviour and existing configuration. Change only this project's listeners. [Serve CLI](https://tailscale.com/docs/reference/tailscale-cli/serve)

## Delivery sequence

1. **Inventory.** Confirm physical Linux host, authorised tailnet, Windows installations, versions, listeners/Serve rules, current jobs and protected settings. Use the Hermes collaboration skill for bounded agent tasks, and local/admin steps where needed. Track only sanitised status publicly.
2. **Preserve rollback.** Privately back up affected service/Serve/access configuration and old non-secret endpoint settings. Inventory existing LAN clients. Stage replacement before retiring their route; avoid resetting all Serve rules or replacing the whole tailnet policy.
3. **Connect privately.** Verify Linux/Windows enrolment, scoped access and full DNS/service reachability. Peer visibility alone is insufficient. The companion computer runs Tailscale; the phone's VPN is not the bridge in this design.
4. **Make services persistent.** Set supervised Hermes startup/restart, protected service credentials, process ownership and stable storage. Record Linux sleep/power, Tailscale device-key expiry, proxy persistence and operational owner. Bind backends to loopback only after dependants/new proxy are verified.
5. **Authenticate and inspect readiness.** Check TLS identity, protected-route denial without a valid key, authenticated capabilities and a useful bounded response. `/health` is liveness; interpret authenticated detailed readiness when supported, including degraded HTTP 200 responses. [Hermes API](https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server)
6. **Migrate development-client settings safely.** Existing `.local/linux-hermes.json` and DPAPI credential belong to that Windows account/computer. The configure script is first-time-only and refuses overwrites. The implemented [endpoint-update helper](../.agents/skills/hermes-collaboration/scripts/update-linux-hermes-endpoint.ps1) preserves old settings, validates/tests an authenticated HTTPS origin, atomically switches only the URL and retains the encrypted credential. Forward switch and rollback refuse unresolved dispatches. Follow [deployment instructions](companion-deployment.md); no live endpoint has been switched.
7. **Reconcile in-flight requests.** Existing requests are endpoint/credential-bound. Finish/reconcile LAN-bound runs before switching. Never redispatch an uncertain request under a new identity or endpoint. Preserve receipts privately and poll the original run through its valid connection where needed.
8. **Accept the implemented companion adapter.** Settings and the Hermes tasks panel now provide protected setup, test/status, selected context, durable dispatch identity, progress/cancel/results and safe retries. Groq Ask stays separate. No coding-agent skill runner is required. Validate the adapter against the permanent endpoint; local fixtures are recorded in the [integration checkpoint](2026-10-21-hermes-integration-checkpoint.md).
9. **Accept both locations.** Complete the matrix below and independently test the media API. Save final private configuration, ownership and recovery steps. Only then mark the permanent-route milestone complete.

The development skill provides health/capabilities, prepare/submit, poll/events, stop and exact one-time approval handling through its [scripts and instructions](../.agents/skills/hermes-collaboration/SKILL.md). It neither configures Tailscale nor integrates itself into the companion UI.

## Secrets, privacy and authority

Keep receiver, Hermes, media and image-provider credentials separate. Current Hermes/media APIs each use their own bearer key; per-client application keys are not implemented. Provision every Windows installation securely: DPAPI files cannot simply be copied to another account/computer. Revoke lost-device tailnet access; rotate shared application keys and update remaining clients if exposure requires it. No keys in arguments, chat, logs or Git.

Send Hermes only selected task/context. Private transport does not constrain the remote agent's tool authority: retain bounded tasks, run-scoped approvals and local validation of proposed actions. Linux access does not authorise Windows cursor control or stable-device flashing.

Groq, explicit Hermes tasks, media sync and image generation have separate privacy boundaries. Local-only mode suppresses all remote routes, including private-tailnet services. Outages keep cached assets available and must not silently redirect a private task elsewhere. Reconnection can resume status/sync, but cannot replay uncertain agent actions, document insertions or paid generation.

## Required acceptance matrix

| Check | Pass condition | State |
| --- | --- | --- |
| Home | Stable private HTTPS origin reaches intended authenticated Hermes and useful scoped work. | Pending |
| Off-LAN hotspot | Same setup reaches the same Hermes with LAN access unavailable. | Pending |
| Actual work | Approved work connection/hotspot works; restrictions recorded, not bypassed. | Pending |
| Service separation | Wrong service keys denied; correct service identity/capabilities checked. | Pending |
| Access denial | Unapproved device and missing/wrong bearer key rejected. | Pending |
| Restart/expiry | Linux/Windows reboot, service restart and required reauthentication recover as documented. | Pending |
| Offline/degraded | UI distinguishes tunnel, TLS, authentication, readiness and task errors; other functions follow their own availability. | Pending |
| In-flight interruption | Reconcile the same task after disconnect without duplicate effects. | Pending |
| Local-only | No remote HTTP/provider/agent/sync calls. | Pending |
| Library separately | Two real Windows stores sync over deployed private HTTPS, including conflicts and server restore. | Pending |
| Stable device | No firmware update needed for transport; stable lock retained. | Required throughout |

One laptop moved between networks can prove Hermes connectivity; library sync additionally needs independent Windows stores/installations. A local two-cache test is not a two-host deployment. Record direct/relay connection and actual latency; relay can serve routes without direct connectivity. [Connection types](https://tailscale.com/docs/reference/connection-types)

## Completion record

Fill during deployment: date, versions, private host attestation/configuration location, owner, reboot/restore evidence, home/hotspot/work results, failure/revocation checks and unresolved limits. Public reports contain sanitised outcomes only. **Current state: local integration/migration/deployment tooling implemented; permanent private route not yet configured or accepted off-LAN. Windows Tailscale and authenticated existing HTTP/LAN readiness were checked on 21 October; that is not private HTTPS or same-host acceptance. A read-only remote inventory reached a security guard and was cancelled without approval or host changes.**
