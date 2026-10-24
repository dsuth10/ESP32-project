# End-of-day checkpoint — 24 October 2026

Work remains on `codex/companion-media-agent`; `main` is the reference.
The user requested that today's companion work and case/enclosure work be
committed and pushed to the existing GitHub branch.

## Companion and device

The [Create & Paste trial](2026-10-24-create-paste-device-trial.md) records the
approved application-only S3 flash, independently verified read-back and private
16 MiB recovery backup. All five page 7 controls have a basic physical pass.
The user confirmed Compose and Dictate in Word and OneNote, Library navigation,
Images voice search/filtering and generated-image insertion through Paste Ready.
Broader classroom, handheld-audio, voice creation/refinement and release gates
remain open. Protected settings, generated images, receipts and recovery binaries
remain private in ignored local storage.

The [Gemini trial](2026-10-24-gemini-live-trial.md) records twelve provider
attempts and ten saved images, including four refinements. Provider invoice
reconciliation remains separate from the recorded usage estimate.

## Hermes: next integration priority

The user wants Dictate and Compose to stay separate from image orchestration.
Investigate using the existing Linux Hermes as an image librarian/orchestrator
with bounded catalogue search, retrieval and preparation tools. Keep the indexed
catalogue application-owned and preserve explicit paid-generation decisions.
Windows retains cursor targeting and final insertion through Paste Ready.
This direction has been discussed; the image-agent integration is not implemented.

A fresh read-only check returned explicit healthy status and authenticated
`hermes-agent` capabilities, including run submission/status/stop and idempotency.
Windows Tailscale was running and online. However, the configured development
client uses an HTTP private-LAN endpoint; the home pilot has Hermes disabled and
no Hermes URL configured. These checks do not establish a Tailscale route to the
intended Linux host or off-LAN acceptance. No remote agent task was dispatched,
endpoint migrated or network setting changed during this check.

Follow the [permanent-route runbook](hermes-tailscale-home-work.md). First verify
the same Linux host over the permanent private route; then connect one complete
saved-image workflow: search, preview, queue and physical Paste Ready.

## Case and enclosure work

Preserved the Blender OBJ/MTL/PLY battery-only enclosure exports and the separate
[SolidCraft pilot](dimensions/solidcraft/README.md), including the editable native
model, STEP/STL exports, previews, modelling requests and local MCP tooling.
The pilot record distinguishes measured CAD checks from printed fit and user
acceptance. The enclosure is not yet print-ready; connector openings, mounting,
battery restraint and lid fastening remain to be completed.

## Final local verification

- Forty-six focused device-feedback, media-voice and image-provider-routing tests
  passed. Initial sandbox attempts were blocked by temporary-directory and
  loopback restrictions; the complete selection passed outside the sandbox.
- Both new CAD Python scripts parsed, and all four modelling-request JSON files
  parsed. No modelling sequence was replayed over the user's saved design.
- Pending files and unpushed Git objects were scanned for common credential,
  private-network and device-identity patterns, including native CAD archive
  contents. The only matches were synthetic device identities in guard tests.
  Private local files remain excluded from Git.

These checks supplement the earlier build/test and physical acceptance records;
they do not establish permanent Hermes deployment, printed enclosure fit or a
stable classroom release.
