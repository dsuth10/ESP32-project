# School readiness: delivered Windows branch and permanent Linux Hermes route

Prepared 25 October for Monday 26 October 2026. The user will use a **different
Windows computer over a phone mobile hotspot**, not the home LAN. This plan owns
the supervised readiness work; the [arrival guide](2026-10-26-school-arrival-guide.md)
owns the morning sequence and the [Linux handoff](2026-10-26-linux-hermes-school-handoff.md)
contains the exact message to paste into Hermes on the physical Linux machine.

## Outcome and actual starting facts

The school computer must load the delivered `codex/companion-media-agent`
source, use its own isolated dependencies/data/protected credentials, and send
bounded tasks to the **same existing Linux Hermes** through private HTTPS over
Tailscale. Groq remains primary; Windows retains Board/Office/provider authority.
This is independent of the phone/home LAN address and requires no S3 flash.

Fresh checks on 25 October established:

| Area | Verified result | Consequence |
| --- | --- | --- |
| Git delivery before this readiness work | Live remote and local HEAD were `4f3c7e60285fc9bc9f7f4a62ffd150e0994fa232`; latest Board source/docs were uncommitted | Deliver a reviewed new feature checkpoint before a separate PC pulls it |
| Existing Hermes API | Authenticated HTTP 200, explicit ready, `hermes-agent` capabilities; a useful own-host read-only run completed | Home-LAN API and bounded Linux tool execution work |
| Configured development origin | HTTP on a private home-LAN address, port 8642 | That configuration is not the permanent school route |
| Home Windows Tailscale | Running, online, zero health warnings | Establishes only this Windows client's state |
| Linux inspection via existing API | Tailscale executable/package absent; daemon/service unavailable; no active Serve/Funnel found; saved route state unknown | Linux installation and enrolment remain necessary |
| Linux administrator capability | Non-interactive sudo unavailable; interactive authentication required | The user must assist the local Linux agent with the real administrator prompt |
| Linux Hermes persistence | Gateway/API on 8642 and dashboard on 9119; active/enabled, restart configured, user lingering enabled | Verify the API gateway locally before proxying 8642; dashboard 9119 is not the API target |
| Linux power | AC connected and AC idle action does nothing; lid close suspends; battery idle suspends | Keep the host on AC with its lid open while remote access is needed |
| Application profile used for the home full test | Hermes disabled; Groq/Google configured; authenticated home budget available | School credentials and Hermes enablement do not arrive through Git |
| Media/budget deployment | The verified full test used the existing home Windows ledger on loopback; permanent remote media/budget not accepted | Do not create a second school A$30 ledger; keep paid school images off until one authoritative service is reachable |

The Linux report is an authenticated agent observation, not a new independent
physical-host attestation. The owner still identifies that physical machine.
No private endpoint, node identity, fingerprint, credential or raw service path
belongs in this document. No Linux installation, enrolment or proxy change was
made by the read-only inspection. Its run completed; no replacement run was
created after the event-stream timeout.

## Work packages and owners

| Order | Owner | Concrete work | Completion gate |
| --- | --- | --- | --- |
| W1 | Coordinator | Reconcile source/docs, keep main as reference, test and deliver the feature checkpoint | Clean reviewed feature commit, successful normal push, remote SHA independently matches |
| W2 | Luna setup worker | Portable Board setup using installed Python 3.12/3.13, final-path owned venv, dependency verification, explicit roots | Fresh offline fixture setup and existing-env checks; no stable environment replacement |
| W3 | Coordinator | Explicit school profile loading fails clearly on missing/undecryptable DPAPI settings; optional read-only library CLI | Regression tests and native launch with the actual CLI flags |
| W4 | Luna setup worker + coordinator | Include Board launch/setup scripts, requirements, example and guides in allowlisted preview package | Archive/hash verification and private-file exclusion tests |
| W5 | Luna guide workers | Detailed separate-PC/hotspot arrival guide and a bounded on-host Linux Hermes setup brief | Commands/API names checked against current source; no assumed remote deployment |
| L1 | Linux Hermes locally + user | Inspect the intended host; install Tailscale via the appropriate official package route; administrator authentication and existing-tailnet sign-in | Client installed, service running, this host enrolled/online; independent physical identity confirmed |
| L2 | Linux Hermes locally + tailnet owner as needed | Preserve current Serve config, confirm API gateway 8642, add one persistent private HTTPS route, retain bearer authentication | Private origin and valid TLS; authenticated readiness/capabilities; missing/wrong key denied; scoped rollback recorded |
| L3 | Linux Hermes locally + user | Verify existing Hermes supervisor and power/restart behaviour | Service persistence separately checked; host remains awake on AC/lid open; controlled reboot only when safe |
| S1 | User on school Windows | Pull delivered feature SHA, install isolated environments, enrol PC in approved tailnet, enter school-local protected settings | Correct source, local dependencies, permitted device, local credential decrypts |
| S2 | User on hotspot | DNS → Tailscale peer path → HTTPS → auth/readiness → useful task → Board composition | Same intended host works while the PC is off the home LAN; no duplicate dispatch |
| S3 | User | Disposable lesson/Office/input/display rehearsal and offline exports | Actual accepted workflow recorded separately from local engineering/network readiness |

W1–W5 are work for this branch. L1 needs an action on the physical Linux machine;
the current remote agent cannot supply interactive administrator authentication.
S1–S3 need the actual school computer and hotspot. Those gates remain open until
their evidence exists; writing this plan or pushing code cannot close them.

## What the user does on Linux before leaving home

1. Open the existing local Hermes session on the **intended physical Linux
   machine**, rather than choosing another online tailnet peer.
2. Paste the copy-ready message in the [Linux handoff](2026-10-26-linux-hermes-school-handoff.md).
   It authorises the bounded setup, preserves existing service/routes and asks
   for human help only for the actual local administrator/sign-in/console steps.
3. Complete the administrator prompt locally. Never put the password/API token
   into this chat or a command argument. Complete the private Tailscale login in
   the browser using the existing approved tailnet.
4. Have Hermes give you the **actual private HTTPS origin** on that local screen
   or an owner-only handoff note. Retain the existing API identity and scoped
   access. A public Funnel URL, old LAN IP, dashboard URL or guessed peer fails.
5. Require local API/TLS/auth tests and a route-specific rollback. Leave the
   machine on AC with the lid open. Schedule reboot tests around active work;
   do not restart the API out from under unfinished runs.
6. Before relying on it, disconnect a test Windows client from the home LAN,
   connect it to the phone's mobile-data hotspot with its own Tailscale active,
   and run the route tests below. A phone VPN by itself does not enrol the PC.

Tailscale provides connectivity; the destination still needs its own running
service. [Official device connection guide](https://tailscale.com/docs/how-to/connect-to-devices).
Serve provides a tailnet-only proxy subject to access rules and HTTPS setup.
[Official Serve guide](https://tailscale.com/docs/features/tailscale-serve).

## School acceptance: distinguish connectivity from working tasks

Use the actual private origin supplied locally; no example URL in a document is
the deployment. The [arrival guide](2026-10-26-school-arrival-guide.md) gives the
Windows commands and provisioning steps.

1. **Internet and school PC:** approved mobile hotspot works; Tailscale is running
   on this Windows computer, signed into the correct approved tailnet.
2. **Identity/DNS/peer path:** the verified Linux host resolves and is reachable.
   A relayed path can be a valid result; direct versus relay is timing evidence,
   not service/API proof. Record it privately.
3. **HTTPS and service:** valid certificate for the private origin, no redirect
   to another origin, explicit authenticated readiness, capabilities identify
   `hermes-agent`. Confirm protected no-key/wrong-key denials.
4. **A real small task:** in the companion's Hermes tasks panel, prepare/review
   and send: `Reply with HERMES SCHOOL LINK OK. Do not access files, run tools or
   contact external services.` Retain its request/run IDs and inspect its result.
5. **Needed Linux tools:** send a separately explicit bounded read-only request
   to report the local Tailscale service state and Hermes API health using only
   relevant local diagnostics, with no secrets or changes. This tests permitted
   Linux tool execution, not merely an HTTP endpoint or model text response.
6. **Board integration:** enter a non-sensitive typed Year 5 text request in the
   dedicated Board assistant. Confirm the complete validated page, one Undo,
   Freeze invariance, save/reopen and pinned local image reuse. Groq still needs
   its own Windows key for the primary resource-classification stage; enabling
   Hermes does not supply that key to the school PC.
7. **Reconnect/restart:** after disconnect/reconnect, refresh the existing
   request/run instead of resubmitting. Reopen the application and inspect the
   saved task. Linux reboot/persistence tests are a separate controlled gate.

No paid image request is needed for these tests. Enable Google generation at
school only after the same authoritative media/budget service, its correct
credential and existing reservations are verified from that PC. This is a
separate M3 deployment, not a side effect of making Hermes reachable.

## What Hermes may run and what remains in Windows

Hermes may perform the authorised Linux installation/configuration and bounded
Linux tasks under its actual tool permissions. A task requiring a missing local
administrator prompt stops at that precise step. Do not weaken its scanner or
grant persistent blanket approvals to make a test pass.

For teaching, Hermes returns bounded text or typed page proposals. The Windows
application validates scope, exact resources, revisions, layout and confirmation;
it owns atomic presentation/Undo/Freeze and local persistence. Windows also owns
Office focus/caret/clipboard, protected credentials, image-provider dispatch and
shared allocation handling. The Linux agent is not a remote Windows desktop
driver, image-budget authority or firmware uploader.

## Delivery and evidence record

Before readiness work, the latest Board local suite passed 445 tests with one
optional PDF extraction skip; native and PDF evidence is recorded in the
[Board build plan](2026-10-25-teaching-board-agent-build-plan.md). The school
setup work adds a real fresh-venv offline fixture, package coverage and explicit
missing/undecryptable school-profile checks. The final integrated selection
passed **485 tests, one optional pdfplumber skip, and four subtests in 32.40
seconds**. A separate real native run through the shipped PowerShell launcher
and its new read-only library option passed seven smoke checks with two native
windows. The initial sandbox launch was denied by its authorisation manager;
the exact command passed outside that sandbox without an execution-policy
override. This is not a school installation or physical-input pass. The exact
delivery SHA is reported in the coordinator's handoff after the normal push.

The completed Linux read-only inspection and fresh LAN health/capability checks
are real service evidence. They do not establish private HTTPS, Linux Tailscale
enrolment, hotspot access, school Windows permissions or classroom acceptance.
Private raw receipts remain under ignored `.local/`; no secret or runtime data
is included in the feature checkpoint. `main` and the board write lock remain
unchanged.
