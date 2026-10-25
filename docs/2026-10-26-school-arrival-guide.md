# School arrival guide: Teaching Board and the Linux Hermes

**For a separate Windows school PC using a phone mobile hotspot — 26 October 2026**

## Read this first

Changing the school PC to `codex/companion-media-agent` does **not** by itself connect it to the home Linux Hermes. At the start of this work, the remote feature branch still lacked the day's new Board agent/library work; that is historical delivery status, not a claim about the later handoff. Use the full feature SHA in the coordinator's final verified delivery message, alongside the [school readiness plan](2026-10-25-school-readiness-plan.md), verify the live remote against it, and follow the branch steps below. A commit cannot contain its own SHA, so the delivery message supplies that exact value. Do not assume an old clone or a plain checkout contains the latest delivered source.

The school connection is **not ready**. A fresh read-only check on 25 October confirmed the existing development Hermes API can answer a useful authenticated task over the private home LAN. The same check found Tailscale is not installed on the intended Linux host (no package, daemon or service) and found no active Serve/Funnel route; the current authenticated client still uses the LAN HTTP service. The API gateway is listening on all interfaces at port 8642, but that does not make it a safe or private hotspot route. The Linux owner needs interactive administrator help to install/enrol Tailscale and configure/verify private HTTPS before leaving home. The host also suspends when the lid is closed while idle; for a school trial, keep it on AC power with the lid open and confirm it stays awake. Windows Tailscale running at home did not prove Linux enrollment or off-LAN access. The phone being on a tailnet or sharing mobile internet is not a substitute for Tailscale on both the school PC and intended Linux host. See the [school readiness plan](2026-10-25-school-readiness-plan.md) and separate [Linux school handoff](2026-10-26-linux-hermes-school-handoff.md).

Until both gates are met, use the Teaching Board in local/offline mode with already prepared lesson files. Keep image generation/refinement disabled at school unless the one authoritative shared A$30 monthly budget ledger is actually reachable and verified. A standalone school loopback ledger would create a second budget and could allow duplicate spending. No firmware change or flash is needed for this PC/network move; leave the original S3 trial and its stable registration alone.

## Before leaving home

Complete these prerequisites on the home PC and in the separate Linux-owner handoff:

1. **Finish the Linux handoff.** The intended Linux computer's owner must get interactive administrator help to install/enrol the actual host in the approved tailnet, configure persistent private HTTPS and scoped access to Hermes, verify restart/reconnect and an independently verified rollback, and keep the host awake on AC with its lid open for the school trial. The LAN API's availability on port 8642 and the separate dashboard listener on port 9119 are not substitutes for this private route. The intended host must be the same one used at home. Do not use an alternate peer, public Funnel, router port-forward, or identity change. Keep private host details in the approved private handoff/configuration, not this guide or Git.
2. **Verify the route from a real off-LAN client.** A Windows PC with Tailscale on the authorised tailnet must reach the intended host over private HTTPS; authenticated health must be ready, and capabilities must identify the expected Hermes service. Confirm denial without a token, scoped task access, restart/reconnect and outage behaviour. A green Tailscale status alone, HTTP 200 alone, or an authenticated home-LAN request does not pass this gate. Record only sanitised results and the private configuration location.
3. **Confirm the exact Board delivery.** Use the coordinator's final verified feature-branch checkpoint. Confirm the live remote includes the Board implementation, both per-PC setup paths, and launcher changes. Copy its full SHA from that delivery message for the school verification below. The earlier `4f3c7e6…` remote observation predates that delivery.
4. **Prepare teaching materials.** Export the required editable lesson package and a PDF, then copy them by an approved removable/offline method. Verify the copy opens. Keep a known-good lesson and PDF available independently of cloud connectivity. Portable lesson packages carry the lesson's used resources/provenance; they do not sync home History, prompts, profiles, provider jobs, settings, credentials, or the home media library.
5. **Record rollback facts.** Note the known-good `main` SHA and the delivered feature SHA. Preserve the home lesson/database and raw SQLite files in their normal private backup process; do not use OneDrive or another live-sync folder for a database. Never delete History, the feature data directory, or an unresolved job to make the branch switch clean.

If the Linux handoff has not proven private HTTPS over an off-LAN connection, mark Hermes **not ready for school**. Do not copy a home endpoint/token and hope it works. Offline teaching remains available.

## On the school PC: check the machine and working tree

Use the school PC's approved local repository folder. Confirm Python 3.12 or 3.13 is installed and the school permits use of Git, Python packages, Tailscale and the intended private service. Connect the PC to the phone hotspot for internet access, then install/sign in to Tailscale on **the PC itself**, using the approved tailnet identity and device policy. Do not enable an exit node or change school network policy to force access.

Before Git operations, close any running companion and Board windows. If the normal `main` companion is open, save its work and exit it first. The home/main companion and the new feature companion may share the code checkout, so never switch branches while either process is running. After switching to the delivered feature branch, run `setup_companion_feature.bat` once: this separately provisions the full companion in `tools/compose/.venv` and starts it. It is needed because the companion Settings UI is the supported way to create this PC's protected keys/configuration. The Teaching Board has its own isolated Python environment and still needs its own setup step below.

In PowerShell, from the school clone root, inspect first:

```powershell
git status --short --branch
git branch --show-current
git rev-parse HEAD
git remote -v
```

Stop before switching if there are modified, staged, or untracked files you do not recognise; if another app/listener is still using that checkout; if the branch is not the expected starting branch; or if the current work is ahead/diverged. Save and resolve authorised work first. Do not use `git reset --hard`, `git clean`, or a forced checkout to make the PC match. If there is no clone, clone the repository using the school's approved Git method and begin on its normal `main` reference.

Set the full delivered feature SHA from the verified delivery message and compare it with the refreshed remote branch:

```powershell
$FeatureSha = 'PASTE_THE_FULL_DELIVERED_FEATURE_SHA_HERE'
git fetch origin
$RemoteSha = git rev-parse origin/codex/companion-media-agent
git show --no-patch --format="%H %s" $FeatureSha
$RemoteSha
```

Confirm `$RemoteSha` exactly equals `$FeatureSha`, and the commit is the one reported in the handoff. If it does not, stop and resolve delivery; do not substitute a guessed SHA or use a moving target. Once the working tree is clean and the expected commit is verified, switch to the feature branch. A new local branch can track the remote directly:

```powershell
git switch --track origin/codex/companion-media-agent
git rev-parse HEAD
```

If the local branch already exists, switch only after checking it is clean and not ahead/diverged, then update it with fast-forward only:

```powershell
git switch codex/companion-media-agent
git pull --ff-only origin codex/companion-media-agent
git rev-parse HEAD
git status --short --branch
```

Confirm `HEAD` equals `$FeatureSha`. If the pull refuses a fast-forward, stop and reconcile; do not reset or force it. `main` remains the reference branch; do not merge the feature branch into it as part of school setup.

Now provision the feature companion and its Settings UI:

```powershell
& .\setup_companion_feature.bat
```

This installs the companion dependencies into the isolated `tools/compose/.venv` and launches the feature companion. It is not the Board setup command and does not provision the Board's separate environment. After entry of school-local Settings below, close/reopen the feature companion as directed. Keep its data under the separate feature root; closing the old main companion before the switch prevents old code/listeners from using the checkout.

## Create the isolated Board and local data

Use the Board-specific setup and launcher delivered in the checkpoint:

```powershell
& tools/compose/setup_teaching_board_candidate.ps1
& tools/compose/run_teaching_board_candidate.ps1
```

The setup script creates the ignored `.local/teaching-board-renderer-env` in its final path with an exclusive setup lock and ownership marker, then checks key imports and `pip check`. On failure it removes only a newly created environment after validating its ownership marker; an existing environment is preserved. The launcher also runs this setup automatically if the environment is missing. This setup does not copy Python from home, change the stable system Python, configure Hermes, or set up Tailscale. If Windows execution policy blocks the script, use the school's approved IT policy/process; do not bypass it or modify policy yourself. If package setup fails, capture the error and use the portable school setup handoff rather than installing into another Python environment.

Launch the school Board with its own persistent school-local lesson folder and SettingsRoot from the feature companion:

```powershell
& tools/compose/run_teaching_board_candidate.ps1 `
  -SettingsRoot "$env:LOCALAPPDATA/ESP32ClassroomCompanion-Feature" `
  -DataRoot '.local/teaching-board-candidate/school-20261026'
```

The `DataRoot` is a safe repository subfolder reserved for this PC's lesson. Later launches should reuse that same path to reopen the lesson. If `media.sqlite3` for the intended library is already available locally, it may be passed through the launcher's optional `-LibraryRoot '<folder containing media.sqlite3>'`; this reads the chosen source and does not configure sync. Do not guess a path or use another machine's live database. Do not point Board storage, `ESP32_COMPANION_DATA_DIR`, `SettingsRoot`, or a library root at home OneDrive/Dropbox, the main companion database, another user's profile, or a network-synchronised live database. Each Windows PC keeps independent local data; move a lesson using the explicit portable editable package or PDF export/import.

For a deliberate synthetic three-page demo, use a fresh candidate subfolder:

```powershell
& tools/compose/run_teaching_board_candidate.ps1 -Demo -DataRoot '.local/teaching-board-candidate/school-water-cycle-demo'
```

Do not use `-Demo` with an existing populated path: the demo refuses to overwrite an existing lesson. The launcher constrains data to the reserved candidate root and rejects link/junction redirection. Keep the school lesson separate from home lesson data.

If the Board-specific setup script/launcher is not present at the delivered SHA, stop and resolve the code delivery before continuing.

## Configure a school-local Hermes credential, only after route acceptance

DPAPI-protected runtime credentials are bound to a Windows account and computer. **Never copy** `credentials.dpapi`, credential XML or whole home environment/configuration files as a way to provision the school PC. A copied encrypted file may not decrypt on this PC. Obtain the authorised key/token through your approved secure credential method and enter it afresh in the feature companion's masked/hidden Settings fields while signed into the intended Windows account. Never transfer a token through Git, this chat, an unencrypted note, a lesson package or a command argument. The new PC also needs a configured Groq API key: Board resource classification uses the primary assistant even when a later composition task uses Hermes. Store it in the protected school-local Settings flow. Use only the private HTTPS origin supplied in the Linux handoff; keep that private configuration out of public/tracked documents.

Use the feature companion Settings UI to enter the school Groq key and, only after Linux route acceptance, the private HTTPS Hermes origin and school-local protected Hermes token. Keep Groq as the primary assistant. The standalone development Hermes skill/client has a separate protected credential/configuration; the companion Settings flow does not create those helper files. If using that developer helper, configure it separately through its documented hidden prompt, never by copying home DPAPI material. A Google image-provider key is not needed for text or offline lesson work. Do not enter or enable image-provider credentials, generation/refinement, or image jobs at school until the one shared budget ledger is confirmed reachable and authoritative. The feature companion's data root is `%LOCALAPPDATA%\ESP32ClassroomCompanion-Feature`; do not modify stable/main settings. Restart the isolated companion after settings changes where prompted, then use Hermes tasks diagnostics to check health/capabilities before sending any task.

This configures the companion runtime route only. It does not create the separate developer-helper credential, deploy the Linux service, enable/configure image sync, prove the school media endpoint, or prove a shared budget. `localhost` and `127.0.0.1` address the school PC, not the home PC or Linux server. The home media service on loopback (port 8765 had an unrelated file server during the home session; the media test used port 18765 temporarily) is not reachable through the hotspot. Do not start an independent school ledger or assume the home port is accessible.

### Prove the school route before using a task

Use these read-only PowerShell checks on the **school PC**, after authorised
Tailscale installation/sign-in. Enter the actual origin supplied privately by
the Linux owner, not a copied example or home LAN URL. No API key is entered in
these commands:

```powershell
$TsExe = Join-Path $env:ProgramFiles 'Tailscale/tailscale.exe'
$TsState = (& $TsExe status --json | ConvertFrom-Json)
$TsState.BackendState
$TsState.Self.Online
$HermesOrigin = (Read-Host 'Actual private Hermes HTTPS origin from the Linux handoff').TrimEnd('/')
$HermesUri = [Uri]$HermesOrigin
if ($HermesUri.Scheme -ne 'https' -or $HermesUri.UserInfo -or $HermesUri.Query -or $HermesUri.Fragment -or $HermesUri.AbsolutePath -ne '/') {
    throw 'Use the verified HTTPS origin only, with no key or API path.'
}
Resolve-DnsName $HermesUri.DnsSafeHost
& $TsExe ping --c 3 $HermesUri.DnsSafeHost
Test-NetConnection -ComputerName $HermesUri.DnsSafeHost -Port $HermesUri.Port
```

Expected: backend `Running`, self online `True`, the intended name resolves,
Tailscale ping receives a peer response, and the HTTPS port is reachable. These
are network checks only. Use **Hermes tasks → Test connection** for authenticated
readiness/capabilities, with the secret already in masked Settings. Keep raw peer
names and addresses private; share only a sanitised pass/fail summary.

Check in order and stop at the first failure:

1. Tailscale on the school **PC** is connected to the approved tailnet and the intended Linux device is present under its independently confirmed identity. Phone tethering supplies internet only.
2. The private tailnet DNS name resolves on this PC. If it does not, check Tailscale sign-in, device approval and the private DNS configuration with the owner; do not replace it with an unverified IP or accept a different peer.
3. Open the supplied private HTTPS origin using the app's connection check. TLS certificate and hostname must validate; do not click through certificate warnings or fall back to HTTP/LAN/private-IP endpoints.
4. Authenticated health reports explicit healthy/ready status, then authenticated capabilities identify `hermes-agent`. A status code alone is not readiness.
5. Only after all four pass, submit one small, non-sensitive, bounded task explicitly authorised for Hermes. Confirm the run identity, inspect its result, and then verify that a disconnect/reconnect resumes that same run without creating another. Keep Ask/Groq separate from explicit Hermes task submission.

Do not send prompts, conversation History, private lesson notes, credentials, or full home project data to Hermes. Supply only the selected page/objects or task details required. A successful connection is transport evidence; the task result is separate evidence.

## One short classroom acceptance pass

Before pupils arrive, rehearse with a disposable local lesson and the actual display/Office targets you intend to use:

- Open the school-local Board lesson; confirm its page, text and images render. Open the portable copy and PDF as an offline fallback.
- Type a short edit; check it saves. Create/edit a text object, add a shape or arrow, move/resize it, and Undo/Redo. Verify a small image remains proportional by default.
- If using an external pupil display, confirm the correct display is selected. Freeze, make a private teacher edit, confirm the pupil view does not change, then Resume and confirm the complete update appears. Do not claim projector/DPI acceptance from a laptop-only check.
- If using ink/touch/pen, make one mark, erase it, undo/redo and navigate pages. Check Freeze disables pupil editing/navigation as designed. Physical stylus eraser, palm rejection, projector-specific DPI and classroom acceptance remain separate checks.
- If a physical S3 control is part of the lesson, test only the already approved installed trial and its documented safe workflow. This guide does not authorise flashing, registration changes, or another firmware write.
- If using a Word/OneNote Paste Ready action, target a disposable document and verify one insertion, undo, save, close and reopen. A queued item or clipboard action alone is not proof that the image was embedded and saved.
- If using PC microphone input, record a short explicit Board recording, review its transcript before sending, and then use the typed equivalent if it fails. This does not prove handheld microphone audio.

Capture the date, app/commit, selected display, exact lesson/package, connection mode (offline or private HTTPS), and pass/fail for each physical check. Keep student information and secret values out of screenshots/logs. Local engineering, deployed service checks, physical application checks and classroom acceptance are different evidence categories.

## Troubleshooting and safe fallback

| Symptom | Likely boundary to check | Safe next action |
|---|---|---|
| Feature branch does not contain the Board files/setup script | School clone or remote SHA differs from the delivered checkpoint | Stop; compare the readiness-plan SHA, verify branch status and resolve delivery. Do not `pull` main or force-update the feature branch. |
| `git switch` refuses or status is dirty/diverged | School checkout has local work or is not at the expected base | Save and inspect the work, then reconcile explicitly. Do not clean/reset or overwrite local lessons. |
| Setup reports missing Python/pip/module/library | Board environment is not provisioned or school network blocks package access | Use the delivered setup script and approved package/network route. The candidate remains offline-capable; use exported PDF if packages cannot be installed. |
| Name resolution fails | PC Tailscale/DNS/device approval or tailnet policy | Confirm the PC itself is signed in, DNS suffix/permissions with the owner, and the intended host identity. Do not trust an alternate peer or raw address. |
| Timeout/offline on hotspot | Tailscale peer path, mobile carrier restrictions, hotspot firewall, Linux sleep/service or HTTPS listener | Verify basic internet, Tailscale PC status, and that the Linux host remains awake on AC with lid open; ask the owner for scoped route diagnostics. Do not expose a public port or switch to home LAN HTTP. Use local mode meanwhile. |
| TLS/certificate warning | Wrong hostname, missing HTTPS proxy/certificate or intercepted school traffic | Stop; do not bypass certificate validation. Ask the Linux owner/school network contact to resolve the intended private HTTPS name/certificate. |
| HTTP 401 | Missing, incorrect or unavailable school-local protected token | Re-enter the token through masked Settings on this PC and intended Windows account; never inspect/copy DPAPI files. |
| HTTP 403 | Tailnet ACL, service scope or token permission denies this device/action | Ask the authorised owner to review the intended scope. Do not widen ACLs or use another credential. |
| HTTP 404 | Wrong service/origin/path or stale endpoint | Compare the privately supplied origin and expected service with the handoff. Don't guess paths or substitute the media service URL. |
| Health 200 but not ready or wrong capability identity | Wrong/degraded service or readiness unknown | Treat as failure; don't dispatch. The current expected identity is `hermes-agent`. |
| Hermes works but library/budget unavailable | Separate media API is not deployed/accepted, or its credential/route is unavailable | Keep local saved assets; do not generate/refine images or create a school-local budget ledger. |
| Existing home data/settings do not appear | Expected: app settings, credentials and history are computer/account local | Use the school-local settings flow and portable lesson files. Do not copy home SQLite or DPAPI data. |

### Rollback

For a code issue, close the app, preserve the school's feature data and lesson exports, and switch code only after the checkout is clean and the selected known-good commit is verified. The school setup may retain the installed Board environment; it is ignored local material, not a Git change. To return to the stable reference, use the verified `main` SHA recorded before switching, with a clean source tree. Do not delete `%LOCALAPPDATA%\ESP32ClassroomCompanion-Feature`, lesson stores, History or receipts as part of code rollback, and do not copy a prior computer's database over the school one. If unresolved tasks exist, reconcile them against their original endpoint/identity before any endpoint or code migration; never dispatch an uncertain task a second time under a new identity.

For a network failure, disable Hermes use in the school-local Settings or leave the app local-only, keep using saved lessons/PDF and cached local images, and resume only after the same Linux host's private HTTPS route has recovered and passed health/capabilities again. Never roll back to an unverified LAN endpoint. No board firmware rollback or write is part of this procedure.

## Record what the school trial actually proves

Report separately: (1) the source commit and local setup/build result, (2) Tailscale/TLS/authenticated Hermes and media/budget deployment checks, (3) actual display/input/Office/S3 interactions, and (4) teacher/classroom acceptance. Mark skipped or blocked checks as pending; a documentation guide, candidate opening, API health response or local demo does not close a deployment or classroom gate.

Reference documents: [current programme](2026-10-21-companion-media-agent-master-plan.md), [development workboard](2026-10-25-development-workboard.md), [candidate operating guide](2026-10-25-teaching-board-agent-candidate.md), [school readiness plan](2026-10-25-school-readiness-plan.md), [permanent Hermes/Tailscale runbook](hermes-tailscale-home-work.md), [Hermes collaboration skill](../.agents/skills/hermes-collaboration/SKILL.md), and [Linux school handoff](2026-10-26-linux-hermes-school-handoff.md).
