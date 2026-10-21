# Authorised Hermes consultation

21 October 2026 — planning and read-only connection checks

## Authorisation and scope

The user explicitly asked Codex to communicate with their Hermes agent to help develop the Linux/private-cloud part of the classroom companion. The initial request was bounded to architecture review. It contained project requirements and no credentials, classroom content or conversation archives. It instructed the agent to make no file, service, network, installation, scheduling or paid-image-generation changes.

## Verified connection facts

- The existing local API answered an authenticated `GET /v1/capabilities` with HTTP 200 and identified itself as `hermes-agent`.
- It advertised chat, session-chat, run submission, run status and cancellation capabilities.
- The checked saved model was `llama3.2:latest` with the existing local Ollama-launch provider. The authenticated gateway and receiver health checks were live; these are separate facts from model quality.
- Tailscale on this Windows computer reported Running/online and one online Linux peer. No local remote-Hermes peer registrations were found. A probe of the standard Hermes health port on that Linux peer did not establish connectivity. Existing SSH profile matching did not establish a verified route to it.
- These checks do not establish that the local gateway runs on, proxies to, or has shell access to the intended Linux machine. No existing credentials were printed or changed, and no SSH keys were installed.

## Actual review results

The first authenticated chat request returned HTTP 200 but contained malformed tool-like text instead of an architecture review. It reported no client-facing tool calls. That text was not executed or accepted as instructions; it was not evidence that any requested planning task was completed. In particular, no task scheduling was requested or performed by Codex.

A second request selected the already-installed `qwen3.5:latest` model for that turn only. It returned HTTP 200 and a structured architecture review. It explicitly reported its runtime OS as unknown, which is appropriately retained as unknown. The saved Hermes default/provider configuration was not changed.

Useful recommendations, independently consistent with the design, were: separate the application-owned library API from Hermes's own service surface, retain immutable versions and an explicit canonical pointer, use a durable outbox and revision checks, retain cached media offline, and keep Windows cursor/clipboard control in the desktop application.

Some statements required correction before integration:

- Tailscale was incorrectly characterised as unauthenticated layer-2 transport. Its identity/access-control plane and encrypted WireGuard connections provide authenticated network access. Application-level authorisation remains a separate design responsibility. [Tailscale identity](https://tailscale.com/docs/concepts/tailscale-identity), [Tailscale encryption](https://tailscale.com/docs/concepts/tailscale-encryption).
- Write idempotency prevents duplicate effects; it does not alone resolve competing updates. Expected revisions and explicit canonical-conflict handling are still needed.
- Groq is a hosted API provider here, not an LLM that the user installs. The selected A$30 allowance concerns future image generation, not a Groq software installation.
- Some returned “unanswered” questions had already been resolved by the user. Automatic first-release sync, Groq-primary/Hermes-optional and the image budget remain the confirmed requirements, regardless of the agent's uncertainty.

The consultation therefore proves a usable authenticated communication path to the local Hermes gateway, with model-dependent response quality. It is not proof of dependable autonomous development, a functioning Linux peer link, or completed media infrastructure. HTTP success must be assessed separately from useful and correct work.

## Next useful collaboration step

Obtain the existing Linux connection reference without requesting secrets in chat, verify the intended host and read-only service capabilities, then agree a bounded server task and its permitted workspace. Initial work can inventory service ownership, API exposure, persistent storage and backup options without changing the host. Implementation should return a diff and test/recovery evidence for central integration. No public port exposure, Tailscale policy change, service restart or deployment was performed during this consultation.

## Linux LAN endpoint follow-up

The user supplied the Linux API's LAN connection reference. A direct Windows-to-Linux request to `/health` returned HTTP 200. A request to `/v1/capabilities` without a bearer key returned HTTP 401. This supersedes the earlier unsuccessful probe of the Tailscale address: the supplied LAN route is reachable from Windows. Remote-peer registration is unnecessary for direct API calls; absence of peer registrations never established that the Linux API was unavailable.

The checked Windows process, native Hermes environment file and companion configuration contained no Linux-specific bearer-key configuration. The existing local gateway key was not assumed to be a credential for another server. An ignored local PowerShell setup script was prepared to accept the Linux key through a hidden prompt and save a Windows user/machine-bound encrypted credential. No key has been requested in chat. Authenticated Linux capabilities and an actual Linux-agent response remain unverified until that credential is configured. LAN reachability also does not establish the intended Tailscale/home-work route.

## Authenticated Linux access

The user completed the hidden Windows credential prompt. The client decrypted the user/machine-bound credential only in memory and used it for the supplied Linux endpoint; no bearer value was printed or placed in a command argument. Authenticated `/v1/capabilities`, `/v1/models` and `/v1/toolsets` all returned HTTP 200. The platform identified itself as `hermes-agent`, advertised durable idempotent run submission, status and cancellation, and listed terminal/file tools as enabled. This establishes authenticated API access, not successful execution of every advertised tool.

A bounded read-only hosting-inventory request was accepted with HTTP 202. It permits a few narrowly scoped checks of OS/runtime versions, selected installed modules, available disk space, user-level systemd and Tailscale status. It excludes secrets, config contents, logs, personal data, recursive discovery, installations, service/network changes, paid generation and contact with other agents. Findings and any tool restrictions must be assessed from the completed run before incorporation. The request and run receipts are retained privately under the ignored `.local` directory.

## Completed Linux-agent inventory and evidence

The first run finished with a server design recommendation but no verified environment facts. Hermes's security scanner blocked its combined inline Python diagnostic. A reviewed one-time approval attempt returned HTTP 409 because the run had already completed; no approval-policy change was made. A second bounded request used simple separate read-only commands and completed successfully. Retained tool events were checked against its final answer, rather than treating HTTP success or model assertions as sufficient evidence.

| Check | Observed result | Practical consequence |
| --- | --- | --- |
| `uname -sm` | Linux x86_64 | Terminal tools executed in a Linux environment; physical-host identity and tool backend were not separately attested. |
| `python3 --version` | Python 3.14.7 | Verify intended server dependencies against the selected deployment runtime before installing anything. |
| `sqlite3 --version` | Command not found, exit 127 | The SQLite command-line utility is unavailable on this PATH; this does not establish whether Python's SQLite module is available. |
| `python3 -m pip show fastapi uvicorn` | Terminal tool refused it as a presumed long-running server command | Package availability remains unknown; no installation was attempted. |
| `df -BG --output=avail .` | `348G` available | Approximately 374 GB free on the current working filesystem; persistence, backup and final storage location remain unverified. |
| `systemctl --user is-system-running` | `running`, exit 0 | A user-level systemd manager is available in this execution environment. |
| `systemctl is-active tailscaled` | `inactive`, exit 4 | No active Tailscale service was established by this check; it does not prove every possible Tailscale installation or route is absent. |
| `command -v docker podman` | No result, exit 1 | Neither executable resolved on the checked PATH; containers are not a prerequisite for the proposed service. |

The runtime receipt identified the serving model as `openai/gpt-6-luna` through the existing OpenRouter provider. No provider/model configuration was changed and no paid image generation was requested. The tool trace contained skill lookup and diagnostic terminal operations; no file writes, installations, restarts or deployment actions were observed.

The agent recommended a separate Python media API with SQLite metadata, immutable content-addressed blobs, canonical revisions, idempotent writes, delta sync and atomic shared budget reservations. This aligns with the master plan, but the API does not yet exist. The next implementation unit should be a locally tested server schema/API using synthetic assets, followed by a deliberately configured Linux deployment and two-desktop sync verification. Linux-host identity, package/runtime compatibility, persistent storage/backup, application credentials and a working private home/work route still need verification before deployment.
