# Teaching Board agent and reusable library candidate

25 October 2026. Local implementation under the
[agent build plan](2026-10-25-teaching-board-agent-build-plan.md). This extends
the provisional Qt candidate; it is not a stable release, live-service acceptance
or classroom sign-off.

## Open the candidate

```powershell
& tools/compose/run_teaching_board_candidate.ps1
```

This opens the isolated `review` lesson, creating it if necessary. Existing
lessons are preserved. A fresh synthetic demonstration uses a separate folder:

```powershell
& tools/compose/run_teaching_board_candidate.ps1 -DataRoot .local/teaching-board-candidate/demo-agent -Demo
```

The default is local-only. Manual editing, saved resources, portable lessons and
PDF work without a remote agent. Requested local composition needs an available
configured loopback Ollama model; no model is downloaded by opening the Board.
Typing remains available if speech dependencies, a microphone or a local model
are unavailable.

For a fresh Windows computer, run
`tools/compose/setup_teaching_board_candidate.ps1` first, or let the Board
launcher invoke it when its isolated environment is missing. It selects a local
Python 3.12/3.13 and installs the declared dependencies into this checkout's own
`.local/teaching-board-renderer-env`; it never copies the home environment.
See the [school arrival guide](2026-10-26-school-arrival-guide.md) and
[Linux Hermes handoff](2026-10-26-linux-hermes-school-handoff.md). Optional
`-LibraryRoot` reads an existing local saved-image library without changing it.
An explicitly supplied `-SettingsRoot` now fails clearly if its saved profile
is missing or cannot be decrypted on this Windows account.

For explicitly requested Groq/Hermes/media work, pass the **existing isolated
companion's protected settings folder** using `-SettingsRoot`. Do not pass a key
on the command line, point at the stable application's data or copy DPAPI files
between computers. The launcher reads configuration; it does not enable a live
setting or start the receiver, device listeners, hotkeys or sync worker.

```powershell
& tools/compose/run_teaching_board_candidate.ps1 -SettingsRoot '<isolated companion settings folder>'
```

Groq remains primary. When Hermes is explicitly enabled in that selected
configuration, Board composition uses the existing bounded Hermes service.
Resource classification uses the primary assistant. Requested image work uses
the existing provider/shared-budget configuration, retaining its separate token,
durable jobs and allocation rules. No credentials enter lesson packages.

The isolated environment now has the Board, HTTP, PDF and audio/STT dependencies.
Recreate it from `tools/compose/requirements-board.txt` if needed; this does not
download a speech/model weight or establish device acceptance. Local-only speech
requires `LOCAL_WHISPER_MODEL` to name an already downloaded model directory
containing `model.bin`, preventing an implicit download.

## Teacher controls

- **Saved Board requests:** reopening a lesson lists its saved task identities
  locally. **Refresh existing task** checks the same Hermes run;
  **Review saved result** opens a complete preview before publication;
  **Cancel saved request** blocks local publication and requests remote stop
  when available. Changed lessons and ambiguous publication remain protected.
  See the [recovery guide](2026-10-26-teaching-board-request-recovery.md) for
  the workflow, limits and offline verification.
- **Teaching profile:** save one local year level, Australian English, default
  instructions and explicit illustrative-data permission. Current request and
  lesson context take precedence. Effective context appears in the private
  complete-page preview. Profiles are not exported or silently learned.
- **Send Board request:** request a page or a targeted change. Select an object
  to refer to it. Use the optional exact-wording field when its literal wording
  must survive the composition. Status shows real stages/time and continues
  beyond the 15-second target. Cancel prevents later local publication.
- **PC microphone:** explicitly start/stop up to 30 seconds of recording. Review
  the transcript, then send it as a Board request. Existing Compose/Dictate and
  handheld actions are unchanged.
- **Reusable resources:** search all types or filter images/pages/datasets/charts.
  **Index saved library** reads an existing `media.sqlite3` source without
  changing it. Backfill is resumable and metadata-only; selected image bytes and
  hashes are checked before use. Only a unique exact approved match is selected
  automatically; other matches use thumbnails. Selected bytes are retained in
  the reusable cache and lesson, preserving their original identities.
- **Saved pages:** completed requested pages are automatically retained as
  immutable editable resources. Select one and choose **Reuse selected saved
  page** to restore it offline through the same complete preview/Undo path.
  Dataset/chart selection restores the exact data/specification for a new chart.
- **Approve selected resource for reuse:** records teacher suitability for that
  exact version. It does not promote a canonical image or approve other drafts.
- **Review complete page:** first-use generated images and destructive page
  replacement require the exact completed preview. Ordinary edits apply directly
  with Undo. Failed/missing resources, stale results, unreadable text and native
  decoding failures leave the pupil page unchanged. Freeze retains its complete
  snapshot until Resume.
- **Review image attempts:** inspect the exact unresolved automatic Google job.
  Only after the teacher reviews its saved result/provider outcome can its local
  barrier be reconciled. This neither retries the job nor releases a held
  allocation or establishes an invoice amount. New briefs/reopening do not
  bypass unresolved attempts.

The side panel scrolls to retain existing object-editing controls on a laptop.
Export editable lesson, Export PDF and Import editable lesson are below the
canvas. Imported lessons open as a separate saved lesson, after full validation;
Resume first when the pupil display is frozen. A portable package includes
editable state/history, exact used image bytes/provenance and outgoing typed
dataset/chart dependencies. It excludes unrelated resources, profile, prompts,
jobs, settings and private paths. PDF includes readable credits. Changing a
catalogue alias or canonical pointer does not change a saved page.

## Supported first chart format

Import a bounded JSON dataset using **Use chart dataset**, or select an existing
dataset/chart in the library. Initial rendering is deterministic bar charts,
up to twelve readable categories; larger data needs an explicit subset/split.
Values are finite numbers or `null`, and units, date, source and coverage are
required. Missing values remain missing. No generated code or approximate
semantic value extraction runs.

The [example dataset](../tools/compose/examples/teaching-board-illustrative-rainfall.json)
is explicitly invented practice data. It requires illustrative-data permission,
and its pupil-facing rendering is labelled. Replace it with sourced values for
a factual lesson. The source data, chart specification and rendered image have
separate immutable identities and relationships.

## Limits and acceptance

External routing is library first, then one appropriate route. Commons reuse
requires supported consistent file metadata and its source licence block, with
visible credit. A new Google illustration uses one positive configured estimate
up to A$0.50 and the same A$30 Brisbane calendar-month ledger as Images. No
automatic paid refinement, alternative provider or uncertain retry is added.
Cloud indexing/enrichment is disabled; vectors and semantic ranking are future
measured work. Video/audio/document records do not imply Board playback/import.

The permanent private HTTPS/Tailscale route, actual Groq/Hermes/provider calls,
real PC-microphone/input/display checks, two-installation sync, teacher quality
review and classroom acceptance retain their separate gates. The final renderer
has not been selected. No firmware write, stable release, merge or push is
included in this implementation.

Exact test and native/export evidence is recorded in the build plan and workboard.
