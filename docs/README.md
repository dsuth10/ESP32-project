# Project documentation index

21 October 2026. Start with the current programme; dated research/checkpoint documents preserve evidence and are not the active release plan.

## Current plans and operating guides

| Document | Use it for |
| --- | --- |
| [Consolidated branch programme](2026-10-21-companion-media-agent-master-plan.md) | Fixed decisions, implemented versus unaccepted work, M0–M9 roadmap, dependencies and completion dashboard. |
| [Permanent Hermes/Tailscale connection](hermes-tailscale-home-work.md) | Required same-agent home/work route, safe migration, protected setup, persistence and off-LAN acceptance. Configuration remains pending. |
| [Home/work architecture](home-work-architecture.md) | Current S3/Windows/Groq/Hermes/library ownership and target topology. |
| [Image candidate testing](feature-media-testing.md) | Isolated launch, image workflow, Office/microphone/sync acceptance and recovery. |
| [Media server contract](media-sync-server.md) | Actual implemented media/budget API, privacy limits and undeployed Linux service boundary. |
| [Board upload safety](board-upload-safety.md) | Guarded identities/manifests, stable write lock and explicit S3 trial/recovery gate. |
| [Build guide](build-guide.md) and [portrait guide](PORTRAIT_UI.md) | Existing S3 builds, setup and guarded release constraints; no automatic permission to flash. |
| [Hardware reference](hardware-reference.md) | Original ES3C28P pinout, configured memory and enclosure/manufacturer references. |
| [Agent instructions](../AGENTS.md) and [engineering rules](../GEMINI.md) | Current scope and regression constraints for contributors/agents. |
| [Hermes skill](../.agents/skills/hermes-collaboration/SKILL.md) | Bounded development-agent API workflow, not the unimplemented product adapter. |

## Implementation and historical evidence

- [Image implementation checkpoint](2026-10-21-media-feature-implementation.md): recorded 164 integrated tests, 9 Hermes tests, synthetic Word/native UI evidence and remaining gates; subsequent safety work is distinguished.
- [First assistant/History increment](2026-10-21-companion-assistant-first-increment.md) and [embedded design](2026-10-21-embedded-companion-assistant-design.md): original incremental evidence/design, superseded as a roadmap.
- [Product discovery](2026-10-21-open-product-discovery.md): adoption/licensing recommendations and earlier scope; licence selection remains unresolved.
- [Second-board inspection](2026-10-21-second-board-inspection.md): historical CYD detection/display/touch/guard evidence. CYD application port abandoned; preserve backup/source history.
- [Compose/Dictate plan](ESP32_Windows_Compose_Dictate_Plan.md), [implementation report](ESP32_Windows_Compose_Dictate_Implementation_Report.md), [repair notes](Compose_Dictate_Repair_2026-10-17.md), [OneNote automation proposal](ESP32_Classroom_Companion_OneNote_Automation_Plan.md), [dashboard proposal](Dashboard-plan.md) and [power/touch report](soft-power-touch-wake-report.md): prior contracts/observations or future ideas, not evidence that every current milestone is implemented.
- [Research directory](research/): dated provider, sync, insertion, orchestration, adoption and licensing investigations. Recheck changing API/pricing/rights before implementation or spend. Consultation records may contain private operational context and require public-release sanitisation.

Manufacturer PDFs, schematics, CAD/dimensions, pinout spreadsheets and existing `system-architecture` HTML/JSON/images remain reference assets or historical rendered snapshots. Current network topology is the home/work guide above. They were not reissued as newly verified hardware specifications or relicensed by this documentation update.

## Completion language

“Documentation complete” means plans/guides/links are consolidated. “Implemented” means source exists. “Verified locally” is bounded to its recorded harness. “Deployed”, “works from work”, “classroom accepted” and “publicly released” each require their own evidence. Read the master dashboard before claiming completion.
