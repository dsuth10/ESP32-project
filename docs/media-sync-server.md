# Private media sync service

**Feature-branch candidate; deployment pending.** The permanent private Tailscale connection to the same Linux host from home/work is now required. Follow the [connection runbook](hermes-tailscale-home-work.md) and [master plan](2026-10-21-companion-media-agent-master-plan.md). This API is separate from Hermes; the product runtime Hermes adapter is implemented locally and awaits permanent-route acceptance. The [deployment kit](companion-deployment.md) adds staged service files and verified backup/restore.

The service in `server/media_library_server.py` stores immutable PNG, JPEG and
WebP blobs and an append-only media event log. Each Windows installation keeps
its own `MediaStore`; its SQLite database, History, prompts, credentials,
network settings and job records are never transferred. The event allowlist
contains only `version` and `canonical` records. Unknown fields are rejected.

## Local development

Python 3.10 or later and Pillow are required. Set a long random token and a
dedicated data directory in the environment, then run the server from the
repository root:

```powershell
$env:MEDIA_SERVER_TOKEN = '<random bearer token>'
$env:MEDIA_SERVER_DATA_DIR = 'C:\media-library-data'
python server/media_library_server.py
```

The default bind is `127.0.0.1:8765`, which is suitable only for local testing.
The server refuses to start when the token or data directory is missing. The
health endpoint returns only `{ "status": "ok" }`; all `/v1` routes require
the bearer token. Request contents and credentials are not written to logs.

For local client testing, use `http://127.0.0.1:8765` and construct
`SyncClient(store, url, token, allow_private_sync=True)`. The client disables
ambient proxy/netrc discovery and rejects redirects. A non-loopback HTTP URL is
rejected.

## Private host deployment boundary

This Python server does not provide TLS. For another device, bind it to a
private interface only when the host firewall and private-network policy are
already configured, then place it behind the selected private HTTPS proxy.
For this installation, plan loopback backend binding behind Tailscale Serve
after verifying existing dependants and access rules. Use the tailnet DNS name with HTTPS from Windows clients. Do
not expose the service through public port forwarding, Tailscale Funnel, or an
unauthenticated proxy. Tailscale access controls and the application bearer
token are separate protections. No network, ACL, firewall, service, or live
host configuration is changed by this implementation.

Set `MEDIA_SERVER_HOST`, `MEDIA_SERVER_PORT`, `MEDIA_SERVER_TOKEN`, and
`MEDIA_SERVER_DATA_DIR` in the deployment's protected service environment.
`MEDIA_SERVER_BUDGET_LIMIT_CENTS` optionally changes the monthly AUD estimate
allocation; it defaults to 3,000 cents.
Keep the SQLite file and `blobs/` on the host's local filesystem, include both
in the server backup plan, and restrict their filesystem permissions to the
service account. Do not share the SQLite file with desktop clients.

## API

- `GET /health`: unauthenticated, minimal process liveness only.
- `GET /v1/capabilities`: authenticated contract version, blob limit and event
  kinds.
- `PUT /v1/blobs/{sha256}` and `GET /v1/blobs/{sha256}`: raw bytes, maximum
  20 MiB. The server verifies SHA-256 and Pillow-decoded image format; metadata
  events must match the blob's MIME type, dimensions and byte size.
- `POST /v1/events`: one `{event_id, kind, payload}` event. Repeating the same
  ID and payload is idempotent; reusing an ID with different content returns
  HTTP 409. Version events require their blob first. Parent versions must
  already exist. A canonical payload may carry `canonical_title`; the label
  and version pointer change together under the same expected-revision check.
  The image version's own title stays attached to its immutable metadata.
  Source URLs must be HTTP(S) page URLs without credentials, query data or
  fragments; local file paths are rejected.
- `GET /v1/events?after=N&limit=200`: events in stable increasing cursor order.
  Limits are 1–500. Clients advance their durable cursor only after the event
  and referenced blob have been committed locally.
- `GET /v1/budget`: current server-month allocation totals in integer AUD
  cents. Brisbane time defines the month; UTC is used if the host has no
  `Australia/Brisbane` zone data.
- `POST /v1/budget/reservations` with `operation_id` and positive integer
  `amount_cents`; `POST /v1/budget/reservations/{id}/commit` consumes the
  reserved estimate by default; `/release` releases only a known pending,
  unsubmitted reservation. `/uncertain` retains an ambiguous attempt against
  the allowance. The default monthly allocation is A$30 (3,000 cents).

The budget ledger coordinates conservative AUD allocations between devices.
It is not an invoice, a currency conversion, or a guarantee of provider billing.
Do not release an attempt after a timeout that could mean the provider accepted
the request; mark it uncertain and reconcile it explicitly.

## Client integration

`tools/compose/media_sync.py` provides `SyncClient.sync_once()` and
`budget_status()`, `reserve_budget(operation_id, amount_cents)`,
`commit_budget(operation_id, amount_cents=None)`, and
`release_budget(operation_id)`. Remote use requires both a token and explicit
`allow_private_sync=True`; `local_only=True` suppresses network work. Conflict
responses leave the local event in the outbox for explicit resolution.
Transport success means only that media metadata and bytes reached the library
service. It does not confirm a Word or OneNote insertion.
