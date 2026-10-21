# Project instructions

Use Australian English and metric measurements.

## Current programme

Before planning or changing the application, read the relevant milestones/status in [the consolidated branch plan](docs/2026-10-21-companion-media-agent-master-plan.md). ES3C28P ESP32-S3 is the sole supported application target; the CYD port is abandoned and its records are historical.

Preserve the original stable firmware and write-locked registration. Develop on the feature branch with isolated desktop data/listeners. Use existing S3 firmware for host-side tests where possible. A firmware trial needs explicit user approval, a verified recovery backup/procedure and the reviewed role change in [board safety](docs/board-upload-safety.md). Guard rejections stop that write; investigate rather than editing identity/fingerprints to make it pass.

Before registration, flashing, upload-tool changes or recovery, read the board-safety runbook. Use only guarded, explicitly targeted upload routes. Keep identities, credentials and flash backups private in `.local/`. Keep main as the reference until the user approves a release.

For Hermes tasks, endpoint migration or home/work connectivity, read [the permanent-route runbook](docs/hermes-tailscale-home-work.md) and the [Hermes collaboration skill](.agents/skills/hermes-collaboration/SKILL.md). The required target is the same Linux Hermes over persistent private Tailscale at both locations; Groq stays primary. Distinguish the development skill from the unfinished in-app adapter and planned transport from verified deployment.

Report local builds/tests, deployment checks and physical application/classroom acceptance separately. Documentation or a healthy HTTP endpoint does not close the corresponding acceptance gates.
