# Teaching Board agent and reusable resource library: implementation plan

25 October 2026. Current implementation contract for the authorised feature on
`codex/companion-media-agent`. The [programme](2026-10-21-companion-media-agent-master-plan.md)
owns release/deployment gates. This plan reconciles the [agreed Board design](2026-10-25-teaching-board-design.md),
[library research](research/2026-10-25-teaching-board-library-memory-research.md)
and [operating policies](2026-10-25-board-agent-default-policies.md). The latter
settle automatic Board acquisition; earlier explicit-only image rules still
govern the separate Images/Office workflow. No repeat policy interview is needed.

## Deliverable and boundaries

Deliver a narrow, runnable desktop loop: edit one local teaching profile → type
a Board request → find exact reusable resources → compose one complete editable
page → validate privately → atomically apply with one Undo → save resources and
lesson → reopen offline. Targeted follow-ups operate on stable object identities.
Keep the current pupil page during work, errors, cancellation and missing required
resources. Freeze keeps its complete snapshot unchanged until Resume.

New Google content has one teacher thumbnail/complete-page preview and a first-use
action. Ordinary requested edits and clear approved-library selections apply
directly. Destructive changes require confirmation of the exact proposal digest.
Never count automatic saving as approval or canonical promotion.

The existing provisional Qt candidate remains the integration host. This does
not select the final renderer or establish physical pen/touch/display acceptance.
Compose, Dictate, Office insertion and original S3 firmware keep their own owners.

## Dependency graph and worker ownership

| Work | Owner/module | Dependencies | Reviewable completion |
| --- | --- | --- | --- |
| A: local catalogue | Luna; `board_resources.py` | Existing image identities/store | SQLite typed immutable versions, relationships, exact/alias/FTS search, derived-index rebuild, review exclusions and idempotent ingestion |
| B: composition lifecycle | Stronger integration worker; `board_agent.py` | BoardModel/BoardSession, existing Hermes service | Profile, bounded request, async progress/cancel, strict JSON commands, stale-result refusal, complete resource/layout checks, atomic apply/Undo/Freeze and first-use preview |
| C: resource policy | Luna; `board_resource_policy.py` | Existing MediaService/budget/provider snapshots | Local-only routing; durable one-attempt/50-cent guard; narrow Commons rights metadata; deterministic truthful charts |
| D: application integration | Coordinator; candidate/provider/integration modules | A–C interfaces | Profile/request/progress/resource selection/preview UI, explicit protected runtime configuration, automatic catalogue ingestion, exact local resource resolution |
| E: portable export/import | Bounded worker after A–C | Existing store/media and D | Hash manifest, editable pages/history dependencies, safe archive import, PDF visual verification; no profile/secrets/jobs exported |
| F: regression and evidence | Coordinator + independent worker review | D/E | Focused failure tests, candidate native checks, documented runnable instructions and measured local evidence |

Workers own separate files until their slice is returned. The coordinator reviews
and integrates the contracts; passing standalone helpers is insufficient for D.
No worker may call a live provider, flash, deploy, push or alter a protected
configuration as an incidental implementation step.

## Contracts

### Resource identity and catalogue

Preserve `asset_id`, `version_id`, SHA-256 and existing lineage/canonical pointers.
A catalogue version records type, title/description/aliases/tags, bounded typed
metadata, provenance, exact dependency versions, content hash and availability.
Image versions reference existing managed blobs. Dataset/chart/page content is
validated structured data; video/document metadata does not imply playback or
extraction. Keep teacher review/corrections separate from immutable bytes.

FTS5 is a local rebuildable projection with parameterised queries. Search the
whole catalogue before bounding the shortlist. Exact IDs/aliases/title matches
take precedence; duplicates and ambiguity require honest results. Only suitable
approved content can be auto-selected. Generated drafts/rejections are excluded
from ordinary reuse. Metadata relevance does not prove visual correctness.

Open an existing image source read-only. Backfill in bounded batches with a
durable cursor; no live-store migration or sync extension hidden in the picker.
No cloud captioning, embeddings, bulk uploads or profile sync. Later enrichment
needs separate consent/allowance and cannot block local lexical search.

### Request and publication

Capture request ID, lesson/page IDs, revision, session token, selected object IDs,
exact resource shortlist, profile revision and effective-context digest. Profile
precedence is current instruction → lesson context → saved defaults. Keep free
text local except effective guidance for that explicitly requested composition.
No private notes, History, credentials, paths or full catalogue in agent context.

Models return only supported typed commands. Application code validates the
envelope, scope, IDs, resource hashes/decoding, required wording/resources and
page geometry before applying a single command batch. Never execute model code,
SQL, shell, remote URLs or arbitrary chart expressions. No partial publication.
The renderer checks text fit; overflowing content needs repair or a focused
teacher action before publication. Progress starts immediately and reports actual
stages and elapsed time. Fifteen seconds is a measured target, never a timeout
that publishes an incomplete page. Cancel invalidates local application and asks
the existing remote run to stop; an outstanding remote/paid action remains
uncertain and retains its identity.

### Acquisition and spending

Search locally first. With no suitable saved match, intent routes values to local
charts, factual photos to one bounded Commons search, and original illustrations
to Google. Explicit source instructions and local-only override normal routing.
Do not cascade through every provider after failure. Missing essential images
hold publication; optional decoration may be omitted only if the brief permits it.

Reuse the shared A$30 calendar-month Australia/Brisbane ledger. One automatic
Google attempt per Board request, exact configured positive estimate ≤ A$0.50,
1K default. Existing MediaService owns reservation-before-dispatch and uncertain
holds; do not reserve twice. Persist request/job binding before any call. Restart,
cancel, changed brief and failed outcome cannot create a replacement automatic
identity. Paid refinement/additional candidate needs a focused explicit action.
Allocations are estimates, not invoices or a guaranteed provider cap.

Commons automatic imports require consistent supported machine-readable rights:
CC0 1.0, CC BY 4.0 with full credit, or explicitly supported public-domain evidence.
Unknown/conflicting restrictions stop automation. Retain file/source/licence URLs,
creator/title, credit/notices, acquisition time, hash and changes. Put required
credit in a readable pupil-facing area and portable/PDF export. Keep existing
origin/download/decode limits. Never manufacture manual rights acknowledgement.
Reference: [MediaWiki imageinfo](https://www.mediawiki.org/wiki/API:Imageinfo) and
[CC BY 4.0 attribution terms](https://creativecommons.org/licenses/by/4.0/).

Factual chart values come from supplied/selected validated data with units,
source/date/coverage and exact version. Preserve missing values. Store dataset,
validated chart specification and rendered PNG as related immutable resources.
Illustrative data needs explicit permission and visible pupil-facing labelling.
No generated raster graph substitutes for measured data.

## Execution and acceptance gates

1. A–C offline implementations and contract tests, then coordinator review.
2. D complete local loop using real local stores and synthetic agent fixtures;
   prove required-media failure/cancel/stale/Freeze and exactly one Undo.
3. E portable lesson and PDF, inspecting both content and rendered layout.
4. F independent review, regressions, native teacher/pupil captures and exact
   runnable instructions. Record tests separately; do not add overlapping counts.
5. Permanent-route acceptance: same existing Linux Hermes over private HTTPS at
   home/off-LAN/work, authenticated useful task, denial, restart/reconciliation.
   This is a deployment gate; offline code/HTTP liveness cannot close it. Follow
   [the permanent-route runbook](hermes-tailscale-home-work.md).
6. Teacher acceptance: real three-page Year 5 water cycle, targeted typed and
   dedicated PC-mic edit, Undo, Freeze, pen/touch/eraser, save/reopen, portable/PDF,
   single/dual display and display removal. Existing hardware firmware suffices.

## Subsequent increments

After this first complete local slice: teacher-judged retrieval set (about 100
queries), 1,000/10,000/100,000-record stress measurements, modality-specific
embedding comparison, opted-in enrichment, explicit catalogue sync/conflicts,
then validated video/audio/document extraction/playback. These need measured
results, per-format limits and deployment/physical acceptance; generic catalogue
rows do not mark them complete. Existing image tag/decode client/server mismatch
must be reconciled before expanding the sync protocol.

## Implementation evidence — local candidate complete

A–F are integrated locally. Luna implemented catalogue/policy/export slices;
a stronger worker implemented and reviewed the composition lifecycle/native UI
contracts. The coordinator wired the real editor, existing protected runtime,
library, acquisition and export routes. Independent cross-review found and fixed
the concurrent Google claim race, source-footer licence confusion, missing UI
chart export roots, incoming dependency traversal leaking unrelated pages,
native codec/text-fit gaps and exact chart identity/readability issues.

The final **single integrated selection passed 445 tests, with one optional
pdfplumber skip, in 23.38 seconds**. This count includes the new code and existing
Board/editor/store/media-service/provider-routing regressions. It is not added
to the earlier overlapping worker counts. The disposable Windows junction
checks ran outside the filesystem sandbox; no safety check was disabled.

```powershell
$boardTestPaths = @(rg --files tools/compose/tests | Where-Object { $_ -match 'test_board_.*\.py$' })
& .local/teaching-board-renderer-env/Scripts/python.exe -m pytest @boardTestPaths tools/compose/tests/test_media_service.py tools/compose/tests/test_image_provider_routing.py -q -rs --tb=short --basetemp .local/teaching-board-candidate/pytest-agent-final
```

The skipped launcher-environment extraction check was supplemented by bundled
pdfplumber extraction and Poppler renders of all three synthetic water-cycle
pages. The coordinator and export worker inspected rendered layout, wrapping,
image proportions and credits. Persistent evidence is under
`.local/teaching-board-candidate/agent-build-evidence/`, including the portable
package, PDF, three page PNGs and `water-cycle-export-evidence.json`. A native
two-window smoke separately passed seven Freeze/ink/navigation/Undo/save/reopen
checks; its JSON and captures are under
`.local/teaching-board-candidate/smoke-agent-build-final/evidence/`.
Two displays were enumerated; physical input/projector acceptance was not tested.

The isolated launcher environment has Board/HTTP/PDF/audio/STT dependencies from
`requirements-board.txt`. Installing them recorded no audio and downloaded no
model weights. Local-only microphone handling rejects absent local models before
transcription, preserving typed input. Optional assistant/catalogue failure keeps
manual editing and durable lesson saving usable.

The [candidate guide](2026-10-25-teaching-board-agent-candidate.md) gives exact
entry points, configuration boundaries, profile/resource/page reuse, chart-data
format and recovery controls. All code/source changes remain local on the
feature branch at that first build checkpoint. No live model/provider/Hermes task,
credential mutation, deployed transport/sync, firmware write, stable merge or push
occurred in that build. The later [school readiness work](2026-10-25-school-readiness-plan.md)
records its own real read-only Linux task, portable setup checks and feature
delivery separately; it still does not establish private HTTPS/hotspot acceptance.

**Open acceptance:** steps 5–6 above; actual model composition/provider output
quality and timings, real microphone/pen/touch/display behaviour, teacher lesson
quality, permanent private route and two-installation sync. L3–L5 remain deliberate
later increments, including semantic indexes, cloud-consented enrichment, broader
format presentation and catalogue sync. Catalogue type support does not close
those capabilities. This local result closes the first narrow agent/library build,
not the programme or classroom release gates.
