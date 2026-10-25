# Linux Hermes school handoff

Prepared 25 October 2026 for a school-day check from a different Windows PC
using that PC's phone-hotspot connection. This is a runbook and copy-ready
task brief. No Linux host, tailnet, endpoint, Windows credential or service was
changed while preparing it.

## Readiness at handoff

The companion branch has an implemented bounded Hermes adapter, protected
Windows settings, run identities, status/events/stop handling and offline
fixtures. This is local implementation evidence only. Permanent private HTTPS,
the same Linux host from an off-LAN network, the new school PC's protected
credential, and real task acceptance remain open.

Fresh Windows development-client checks from 25 October recorded authenticated
HTTP 200/readiness `ready=true`, service identity `hermes-agent`, and advertised
run submission/status/stop/events/idempotency capabilities. That client still
uses an HTTP private-LAN address; its private value is intentionally omitted.
The Windows Tailscale client was running and online with no reported health
warnings. The home launcher profile's Hermes setting was disabled. These facts
do not establish the Linux tailnet route or school-PC configuration.

Earlier, the intended physical Linux host was independently attested by the
owner using its SSH identity. A different visible Linux tailnet peer did not
match and remains excluded. A fresh read-only own-host inventory on 25 October
now reports Tailscale absent, no installed daemon service/version, and
enrolment unknown. No active Serve/Funnel route was found, but saved Serve
configuration was not inspected. The inspected gateway/API-capable listener
was on TCP 8642 and bound to all interfaces; a dashboard listener was on TCP
9119 and also bound to all interfaces. Active gateway/dashboard services have
autorestart, and user lingering is enabled. The exact authenticated Hermes API
target port is still being confirmed; do not proxy the dashboard port as if it
were the API.

The Linux owner had no non-interactive sudo route; installation needs a local
interactive administrator prompt. The host was AC-connected, but its idle and
lid-close policies suspend it. Keep it connected to AC and the lid open while
it must be reachable; do not change global sleep policy as part of this route
setup. A completed LAN read-only task returned useful output; it made no Linux
changes. Do not treat this as off-LAN acceptance. Do not accept the other peer
or use the old 21 October Tailscale observation as current.

The Linux media-library/budget service is separate from Hermes and is **not
assumed deployed**. Do not install, start, proxy, or test it as part of the
Hermes handoff. Image-provider calls and monthly budget are Windows-owned and
must not be triggered by this task.

## Copy-ready message for the existing Linux Hermes

Paste this into a **local Hermes session open on the physical Linux computer
the owner has identified as the intended host**. Do not submit it through the
Windows companion's remote Hermes task panel: the task must inspect and prepare
its own machine. The bounded setup authority below is given up front, so Hermes
should proceed after the stated gates instead of asking again for generic
confirmation. It must pause only for a human action that only the Linux owner,
tailnet administrator, or school network owner can perform.

```text
The owner authorises you to prepare the existing Hermes on THIS physical Linux
computer for the companion's persistent private HTTPS connection over
Tailscale. You may perform the bounded, reversible setup below after checking
this host. Start with a bounded inventory, then complete every safe step that
is within your existing Linux administrator capability. Do not ask again for
generic approval for this scoped work. Stop only when an action genuinely
requires the owner/admin to sign in, approve the required HTTPS-name disclosure
or policy change, provide administrator authorisation locally, or resolve a
host/route conflict.

First human action: ask the owner locally, “Please approve the local
administrator prompt so I can install Tailscale on this machine, then complete
the private tailnet browser sign-in; after enrolment I will set up the scoped
private Serve route to Hermes.” Ask for no password in this session. Continue
installation with the official signed package route for the detected Linux
distribution; pause for the owner to enter admin credentials locally and to
complete browser sign-in to the existing authorised tailnet on this machine.
The owner, not Hermes, selects/confirms the correct private account in the
browser. Do not create a new tailnet, use an auth key, or enrol a different
node.

Identity gate:
- Inspect this host's OS/architecture, Tailscale installation/version and
  state, active Serve configuration, Hermes process/supervisor, and listening
  sockets needed to identify the real local Hermes backend port. Inspect only
  relevant units/listeners; do not run a broad machine audit.
- The owner previously attested the intended physical Linux host using
  independent SSH identity evidence and is using this local session on that
  computer. Work on this machine only. Do not print or change SSH keys, known
  hosts, endpoints, usernames, fingerprints, credentials, environment files,
  command lines containing arguments, or private paths.
- Never connect to, enrol, or substitute another online Linux peer. If this
  local machine does not match the owner's intended machine or its live Hermes
  process cannot be identified unambiguously, make no network/route changes
  and report the exact mismatch.
- Do not dump complete process lists, service files, environment, logs, or
  Tailscale peer inventories. Summarise only the facts requested below.

Setup authority and ordered work:
1. If Tailscale is missing, identify the Linux distribution and install the
   official Tailscale package using its official signed package/repository
   instructions for that distribution. Do not use an unverified download or
   `curl | sh`, do not run a blanket OS upgrade, and do not replace other
   packages. Enable/start only the Tailscale daemon needed for this host.
2. If Tailscale is installed but not enrolled, start the documented sign-in
   flow for this host. Pause for the owner to complete the private browser
   login locally to the existing authorised tailnet. Never request, accept,
   or store a reusable auth key/password in this chat, a task, an argument, or
   a log. Confirm the authenticated node is this local machine; never choose
   the mismatched peer or create a new tailnet.
3. Preserve all existing Serve routes. Before editing, inspect the installed
   CLI help and save the complete current Serve config to a new, access-
   restricted private backup outside any repository. Never overwrite an
   existing backup. Identify and verify the existing Hermes API listener using
   its real local service/unit and an authenticated health/readiness check. A
   fresh inventory saw the gateway/API-capable service on TCP 8642 and the
   dashboard on 9119, both bound to all interfaces; 8642 is only the preferred
   candidate, not yet a confirmed HTTPS proxy target. Confirm the authenticated
   API is on 8642 now before proxying only
   `http://127.0.0.1:8642`. If the API is elsewhere or ambiguous, use the
   authenticated actual API port after verification; never use dashboard 9119
   as a substitute or assume a planned/old port. Keep existing LAN clients
   working; do not change listener bind addresses as part of this task.
4. Add only a Tailscale Serve HTTPS mapping for the local Hermes backend on an
   available HTTPS port, using the installed version's documented syntax and
   persistent background mode. Keep Serve tailnet-private; keep the application
   bearer authentication. The current API-capable listener is reported on all
   interfaces: do not change its bind address in this task, because existing
   LAN dependants have not been inventoried. A loopback Serve target does not
   remove that separate LAN exposure; report it as an existing condition for
   later owner review. If Tailscale and Hermes are already persistent, preserve
   them; enable the existing appropriate service units where safe. Do not
   replace the Hermes runtime or create a second copy. If no safe existing
   supervisor can persist Hermes, stop and report a minimal proposed service
   change instead of inventing one.
5. Check that tailnet access is scoped to the owner's approved Windows device.
   Do not change ACLs. If the device is not enrolled or policy blocks it, tell
   the owner/tailnet admin the exact missing action; do not widen access.
6. Verify local liveness, explicit detailed readiness, protected capabilities,
   missing-key denial and wrong-key denial. For denial tests use a deliberately
   fake key only; never print, rotate, or probe with the configured real key.
7. Do not reboot automatically. This host suspends when idle and when its lid
   closes: require it to stay AC-connected with the lid open while remote
   availability is needed. Once there are no active runs and the owner is
   present for school-hotspot acceptance, test a scoped Tailscale/service
   restart, then the Windows hotspot path. Test host reboot only in an
   owner-scheduled maintenance window; do not interrupt another user.
8. After route setup, provide the exact private HTTPS origin to the owner in
   this local session and write it to a new owner-private handoff note outside
   the repository with owner-only permissions. Do not include the origin or
   local backup path in tracked files, public reports, telemetry, or a remote
   task payload. This origin is what the owner will enter on the school PC.

Hard limits:
- Never use Tailscale Funnel, public router/port forwarding, a subnet router,
  an exit node, a global Serve reset, a blanket ACL replacement, or another
  machine. Never weaken authentication or change the Hermes API key.
- Use administrator privileges only through the owner's normal local
  authorisation prompt. Never collect or relay a password. Do not change
  firewall rules or host identity, or restart a service while it has active
  runs.
- If MagicDNS or tailnet HTTPS is missing, pause and ask the owner/tailnet
  administrator to enable only those features in the tailnet console. Explain
  the HTTPS disclosure at that point: Tailscale publishes the device name and
  tailnet DNS name in the public Certificate Transparency log. This is the
  specific consent needed for HTTPS, not a request to re-approve the whole
  bounded setup. Resume the scoped setup after the owner completes that action.
- Do not alter ACLs. Ask the tailnet admin only for a precise rule allowing the
  approved Windows device to reach this Hermes HTTPS service. Do not widen a
  general rule or substitute a public route.
- Do not change any Windows setting or credential. The Windows owner will
  provision the school PC's own DPAPI-protected credential and endpoint after
  Linux readiness is verified. Never ask the owner to paste a secret into chat.
- Do not access Office, the S3 board, Windows files, image providers, provider
  budgets, media-library/budget databases, or teaching content.

Return a brief sanitised status plus a separate private owner handoff. The
sanitised status may contain:
1. `physical_host_match`: confirmed / not confirmed / blocked, and which
   independent owner check is still needed (no identity values).
2. `linux`: OS family/architecture, Tailscale installed/version/state,
   Hermes service running/persistence state, actual local backend port, and
   current Serve route count plus whether the required HTTPS port is free.
3. `access_gates`: MagicDNS, tailnet HTTPS, HTTPS-name disclosure consent,
   tailnet enrolment, ACL owner approval, and admin privilege, each
   confirmed / missing / unknown.
4. `changes`: exact scoped change descriptions and the exact rollback commands
   for only the newly added route/service unit. Do not restore or reset other
   users' Serve configuration.
5. `checks`: local Hermes health and detailed readiness; protected
   capabilities; unauthenticated and deliberately wrong-key denial without
   printing or reusing a real key; TLS/Serve reachability; and whether
   persistent Serve/service startup is configured. A capability advertisement
   is not proof that a capability has been exercised.
6. `blockers`: only concrete actions the Linux owner, tailnet admin, school
   network owner, or Windows app operator must perform.

In `PRIVATE_OWNER_HANDOFF`, show the exact private HTTPS origin and where the
owner-only backup/note were saved. This is a local owner handoff, not a
tracked/public report. Never put credentials there. The owner needs this origin
to configure the school PC.

After local readiness passes, run at most one useful, bounded, read-only
Hermes task against the local API: ask it to return a short JSON summary of
its own OS family/architecture and the service readiness/capability names. Do
not read files, use shell authority, access external services, or return
secrets. Save one durable request identity and exact payload before dispatch.
Verify same-ID replay returns the same run ID and does not create a second
effect. If dispatch or response is uncertain, poll/reconcile that same
identity/run; never create a replacement identity. State separately what was
advertised and what was actually tested.

The final report must say whether the route has been reached from the new
Windows PC through its phone hotspot. Do not claim that check passed until the
owner performs it there. The phone does not bridge Tailscale for Windows.
```

## Linux-side read-only inventory

The task above asks Hermes to make a bounded inventory on its own host. If a
Linux owner runs the inventory directly, these are separate read-only checks;
capture detailed output only in a private local record and share a sanitised
summary. A missing command, denied permission, or scanner refusal means
**unknown**, not absent.

```sh
uname -sm
tailscale version
tailscale status
tailscale serve status --json
ss -ltnp
systemctl --no-pager --type=service --state=running | grep -Ei 'tailscale|hermes' | head -n 20
```

Do not add `sudo` if it is unavailable. Do not dump service unit contents,
environment files, complete process arguments, or raw peer/config output into
the task or tracked documents. Check the actual backend using the already
identified unit/port only; do not scan ports. The project deployment guide has
the wider inventory and rollback notes in
[`companion-deployment.md`](companion-deployment.md#required-inventory-before-tailscale-serve-changes).
Before any Serve edit, consult the installed CLI help and save the current
configuration with that version's `tailscale serve get-config <file> --all`
syntax to an owner-selected private, non-existent backup file. That snapshot
is a change-preparation write, not part of the read-only inventory above.

## Setup and school-PC acceptance sequence

1. **Match the host.** The local task runs only on the physical machine the
   owner identified as intended. A service API's `platform` field or another
   online peer name is not physical identity evidence. If local identity or
   Hermes listener is ambiguous, do not route another host.
2. **Preserve and add narrowly.** Inventory all existing Serve entries and the
   real Hermes listener, then save the private pre-change snapshot. The owner's
   prompt authorises the single additive Hermes route and reversible local
   Tailscale/service setup. Pause only for the actual human actions named in
   the prompt: administrator authorisation, local tailnet browser sign-in,
   tailnet-console HTTPS/MagicDNS enablement with CT disclosure consent, or a
   precise ACL rule from the tailnet administrator. Keep media on a separate
   origin if deployed later; no media route is part of this task.
3. **Verify local service.** Confirm Hermes is ready on its real loopback
   listener and restarts under its existing supervisor. Health is liveness;
   detailed readiness must be explicit. Confirm authenticated capabilities
   include run submission, status, stop/events and idempotency as supported.
   A capability advertisement is not proof of endpoint operation.
4. **Verify the route from Windows.** The school PC itself must run its
   authorised Tailscale client while connected through the phone hotspot. The
   phone does not act as a bridge. Confirm the HTTPS DNS identity reaches the
   same independently matched Linux host, the certificate validates, and
   authenticated health/readiness/capabilities work. Do not use the LAN URL as
   fallback. A healthy LAN route or Windows `Tailscale Running` alone is not a
   pass.
5. **Verify denials.** Confirm no-key and wrong-key protected requests are
   denied without printing the configured key. Tailnet policy should permit
   only the approved Windows devices. Do not replace ACLs to make a test pass;
   owner/admin reviews policy separately. Do not try a third party's device.
6. **Run one useful bounded task.** As authorised in the local prompt, run a
   single local API task that returns a concise JSON summary of the service's
   OS family/architecture and readiness/capability names. Use no files, secrets,
   Board content, shell authority or external calls. Save the exact request
   identity before dispatch. Verify same-ID replay returns the same run ID and
   does not create a second effect. If a response is uncertain, poll/reconcile
   that identity and exact run; do not submit another ID. Do not infer tested
   idempotency from an advertised capability.
7. **Restart/reconnect.** Do not reboot during school use. After an owner
   schedules a maintenance window, test Linux and Tailscale restart/reboot
   recovery, then repeat the hotspot HTTPS/auth/readiness check. Test a
   deliberate disconnect/reconnect and confirm status recovers without replay.
   `tailscale serve --bg` is documented as persistent across terminal close,
   Tailscale restart and reboot; the Hermes application still needs its own
   persistent supervisor. Verify both independently.
8. **Keep the Windows boundary.** Windows owns Groq-primary chat, Board
   preparation/validation, Office caret and clipboard actions, local History,
   local credentials, teacher approvals, image calls and shared provider budget.
   Hermes may return bounded text/proposals; it does not control Word/OneNote,
   paste, choose a paid provider, allocate image budget or change firmware.
   School app policy, hot-spot data, managed-device controls and permission to
   use the tailnet remain with the Windows/school owner.

Do not claim M1 ready until the same authenticated Linux Hermes has passed the
home and off-LAN hotspot checks, scoped denial, persistence/reconnect and
rollback evidence. Do not claim M3: the Linux media service, its separate
storage/token/budget ledger, backup/restore, and two real Windows libraries
remain a separate deployment and acceptance path.

## Official operational references

- [Tailscale Serve CLI](https://tailscale.com/docs/reference/tailscale-cli/serve):
  `serve status --json`, `serve get-config --all`, versioned route syntax,
  exact route removal, and persistent background mode.
- [Enabling HTTPS](https://tailscale.com/docs/how-to/set-up-https-certificates):
  MagicDNS and HTTPS approval; device and tailnet DNS names appear in the
  public Certificate Transparency log when certificates are provisioned.
- [Hermes consultation lessons](../.agents/skills/hermes-collaboration/references/consultation-lessons.md):
  dated host observations, identity mismatch, refusal handling, and run/event
  idempotency evidence limits.
- [Permanent-route runbook](hermes-tailscale-home-work.md): authoritative M1
  topology, migration, privacy, and acceptance matrix.
