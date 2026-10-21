# Companion Linux deployment tools

21 October 2026 — implementation aid for M1 and M3. **No Linux service,
Tailscale configuration, endpoint, or remote host was changed by this work.**
The permanent route and media deployment acceptance gates remain open in the
[master programme](2026-10-21-companion-media-agent-master-plan.md) and
[home/work runbook](hermes-tailscale-home-work.md).

## Hermes endpoint migration on Windows

Use `update-linux-hermes-endpoint.ps1` only after the new private HTTPS Hermes
origin is reachable and the authorised operator has reviewed the candidate.
The script reads the existing DPAPI credential and pipes it to Python stdin;
the token is not accepted as a command argument, written into endpoint backups,
or printed. The helper tests authenticated `/health` and `/v1/capabilities`,
refuses redirects, requires explicit healthy/ok/ready status, and writes only
`base_url` to `.local/linux-hermes.json` through an atomic replacement. A
verified, user-private old-config backup is retained under
`.local/hermes-endpoint-backups/`.

Before migration, stop preparing/submitting Hermes requests and reconcile every
request with a dispatch identity. The helper refuses a dispatch lock, an
identity without a response receipt, an uncertain receipt, or a run without a
recorded terminal state. Pause all client instances using this endpoint during
the switch so another run cannot start around the final reconciliation check.
Reconcile using the old endpoint and its original
request identity first. A completed or failed run receipt is retained locally.
If the candidate passes readiness but migration later needs reversal, pass the
reported backup path to the PowerShell script with `-RollbackBackup` and the
candidate endpoint with `-ExpectedCurrent`. Rollback verifies the active URL,
backs it up, and refuses to overwrite an unexpected newer setting.

```powershell
.\.agents\skills\hermes-collaboration\scripts\update-linux-hermes-endpoint.ps1
.\.agents\skills\hermes-collaboration\scripts\update-linux-hermes-endpoint.ps1 `
  -RollbackBackup '.local\hermes-endpoint-backups\linux-hermes-<stamp>.json' `
  -ExpectedCurrent 'https://<private-tailnet-origin>'
```

Do not move the DPAPI credential to another Windows account or computer. Each
authorised installation needs its own protected credential. Endpoint migration
does not configure Tailscale, change access rules, or complete M1 acceptance.

## Linux media service staging

The systemd template runs the separate media service as the dedicated
`companion-media` account, on `127.0.0.1:8765`, with persistent data in
`/var/lib/companion-media-%i`. It reads its bearer token from
`/etc/companion-media/%i.env`; that file must be provisioned by the host owner
with root ownership and mode `0600`. Do not put a token in a command line, Git,
this document, shell history, or a deployment report. The listener template is
for one isolated instance; inventory port 8765 and the Hermes listener before
choosing whether the port or instance name needs reviewed adjustment.

On a Linux staging checkout, first review the exact bundle list and target:

```sh
python3 server/deployment/stage_media_service.py --destination /var/tmp/companion-media-stage
```

Only after reviewing that output and confirming the destination is new, add
`--apply-reviewed` to stage the files there. This command writes only that
new staging directory; it does not install files, create accounts, enable a
unit, create a secret, modify a firewall, or start a service. The deployment
owner must separately review the staged files, package Pillow and dependencies
in a controlled virtual environment, create the dedicated account and private
data/environment directories, install the unit, then verify ownership and
configuration before starting it. Keep the database and `blobs/` on a local
filesystem and do not share them with Windows clients.

### Required inventory before Tailscale Serve changes

Run these read-only checks on the intended Linux host and save private output
for the change record:

```sh
tailscale version
tailscale status
tailscale serve status --json
tailscale serve get-config --all
sudo ss -ltnp
systemctl --no-pager --type=service --state=running
```

Record existing listeners, owners, Hermes/API ports, Serve paths, HTTPS
eligibility, Linux/Tailscale versions, active jobs and current endpoint clients.
Review current tailnet policy and access rules with its owner. Do not use
`tailscale serve reset`, `tailscale funnel`, public port forwarding, or blanket
ACL replacement for this deployment. If an existing Serve config is present,
preserve it and plan only an additive, reviewed route. The Hermes and media
services have separate origins, tokens and lifecycle.

After inventory and approval, start the media service and verify its local
`/health`, authenticated `/v1/capabilities`, missing/wrong-key denial and
durable state path. For remote access, Tailscale Serve is an HTTPS proxy for
tailnet devices and applies tailnet access-control rules; it requires HTTPS to
be enabled in the tailnet. The current CLI reference documents `serve status
--json`, `serve get-config --all`, `--https`, `--bg`, and the `reset` command;
the latter clears the current Serve configuration and is deliberately excluded
from this procedure. Check the installed version's help and actual existing
configuration before making a scoped route change. See [Tailscale Serve CLI](https://tailscale.com/docs/reference/tailscale-cli/serve)
and [Tailscale Serve access and setup](https://tailscale.com/docs/features/tailscale-serve).

The candidate arrangement uses a distinct HTTPS port for media, such as 8443,
proxying only to `http://127.0.0.1:8765`; keep Hermes on its separately
inventoried HTTPS origin. A current CLI syntax example is:

```sh
sudo tailscale serve --https=8443 --bg http://127.0.0.1:8765
```

Treat this as a reviewed example, not a command to run blindly: confirm the
version's accepted syntax, existing listener/rules, target service readiness,
tailnet HTTPS setup and owner approval first. The documented `--bg` mode
persists Serve across Tailscale restart/reboot; it does not supervise the media
application, which is why it has a separate systemd unit. No Serve command has
been run by this implementation.

## Backup, verification and restore

The media data set is the SQLite metadata/budget database plus content-addressed
files under `blobs/`. Stop the media systemd instance before backup so both
parts represent one point in time. Backups contain private teaching images and
metadata: choose an access-controlled encrypted destination and retain it
according to the owner's policy.

```sh
sudo systemctl stop companion-media-library@<instance>.service
python3 server/deployment/media_backup.py backup \
  --data-dir /var/lib/companion-media-<instance> \
  --destination /secure/backup/media-<date> --service-stopped
python3 server/deployment/media_backup.py verify --backup /secure/backup/media-<date>
sudo systemctl start companion-media-library@<instance>.service
```

The utility refuses an existing backup path, verifies SQLite integrity, checks
every blob name against its SHA-256 content, writes a private manifest, and
verifies the completed staged copy before publishing it. Restore verifies the
backup again and only writes to a new destination:

```sh
python3 server/deployment/media_backup.py restore \
  --backup /secure/backup/media-<date> \
  --destination /var/lib/companion-media-restore-check
```

This does not replace a live data directory. To prove recovery, restore to a
new isolated path, verify the manifest and database, start a separately
configured test instance bound to loopback on an unused port, then confirm
representative metadata and image retrieval before recording the result. Keep
the production unit stopped during any operator-approved cutover and retain a
recoverable pre-change backup. Delete temporary recovery data only under the
host owner's retention procedure. The utility rejects symbolic links and
junctions found in the data set and backup path; the host owner must also ensure
parent directories are trusted and not reached through platform-specific aliases.

## Acceptance still required

Local fixture tests cover URL validation, dispatch reconciliation refusal,
authenticated readiness preflight, atomic switch and guarded rollback, and
backup integrity/no-overwrite restore. They do not establish Linux installation,
private TLS identity, Tailscale reachability, reboot persistence, access denial,
off-LAN operation, or two actual Windows libraries converging. Record those
gates separately using the acceptance matrix in the permanent-route runbook.
