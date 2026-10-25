# Hermes readiness — 25 October 2026

Read-only M1 preflight on `codex/companion-media-agent`, following the
[permanent-route runbook](hermes-tailscale-home-work.md) and
[Hermes collaboration skill](../.agents/skills/hermes-collaboration/SKILL.md).
Dates use Australia/Brisbane time.

## Today's observations

| Component | Fresh observation | What this establishes |
| --- | --- | --- |
| Existing development API health | HTTP 200; explicit `ok`; helper reported `ready=true`, `readiness_known=true`. | Current service readiness through the configured development route. |
| Authenticated capabilities | HTTP 200; service identifies as `hermes-agent`; advertised feature names include `run_submission`, `run_status`, `run_stop`, `run_events_sse` and `runs_idempotency`. | Authenticated API identity and advertised route names. No run was submitted and no advertised action was exercised. |
| Development-client configuration | URL configured; protocol HTTP; destination is a private-LAN literal rather than a tailnet DNS identity; protected credential file exists. | The development client still uses the existing LAN route. Credential contents were not inspected or printed. |
| Windows Tailscale | Backend `Running`, self online, zero health warnings; Windows service `Running`. | Local Windows service and tailnet-client state. No peer list, peer identity, address or Linux route was exposed or attested. |
| Desktop runtime configuration | Exact current home-launcher-to-data-root ownership was not re-established. The default feature-launcher root has no public settings file. | Today's preflight does not establish the active home pilot's Hermes URL, enabled state or credential readiness. |

Yesterday's [checkpoint](2026-10-24-end-of-day-checkpoint.md) recorded Hermes
disabled and no Hermes URL configured in the home pilot. That remains dated
evidence, separate from today's authenticated development-client result. Local
settings candidates were not treated as proof of the active runtime's identity.
Protected desktop credentials were not decrypted for this inventory.

## Environment distinction

Initial sandboxed health and capabilities checks returned sanitised `URLError`
results; the sandboxed Tailscale status query was also unreadable. The same exact
read-only helper checks and local service/status query succeeded through the
normal approved execution route outside the sandbox. These initial failures
therefore do not establish a Hermes outage or inactive Tailscale service.

Checks used the existing `invoke-linux-hermes.ps1 health` and `capabilities`
commands, `tailscale status --json` reduced in memory to local-state fields,
Windows service status, and sanitised URL/public-settings presence inspection.
The existing helper used its protected credential internally; no credential XML,
token, endpoint value or peer inventory was dumped. No new private connection
identity was copied into tracked files.

## Exact remaining transport blocker

There is still no configured and accepted private HTTPS/Tailscale route from
Windows to the independently identified intended Linux Hermes host. A healthy
LAN service and an online Windows Tailscale client do not prove that route or
that the same physical Linux host is reachable from another network.

The [last intended-host inventory](2026-10-21-hermes-integration-checkpoint.md)
reported no Tailscale executable in checked paths, an inactive `tailscaled`, and
no non-interactive administrator access. A different visible Linux tailnet peer
had failed the independent identity match and remains excluded. Today's bounded
checks did not re-inventory Linux installation, enrolment, privilege or SSH
identity; those historical observations must not be presented as fresh facts.

The next deployment step remains a reviewed local administrator handoff on the
intended Linux computer: establish its enrolment and identity, preserve rollback,
verify persistent private HTTPS/service configuration and scoped access, then
test authenticated access before migrating any Windows endpoint. Existing
in-flight requests must be reconciled before a migration. Follow the runbook;
do not substitute a different peer or accept a new identity to bypass this gate.

## Acceptance remains open

- Same intended Linux host over permanent private HTTPS at home and off-LAN.
- Persistent Linux services/proxy, restart recovery, denial and revocation checks.
- Exact home-pilot runtime configuration and accepted bounded real task workflow.
- Separate Linux media/budget deployment, restore and two actual Windows stores.
- Physical Paste Ready and classroom acceptance of the new metadata-only handoff.

No remote agent run, SSH connection, endpoint migration, network/service change,
installation, paid image request, firmware write, commit or push was performed
by this preflight. No deployment or physical acceptance gate is closed.
