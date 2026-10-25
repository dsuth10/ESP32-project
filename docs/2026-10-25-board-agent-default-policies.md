# Board agent: delegated operating defaults

Later implementation record: the [agent build plan](2026-10-25-teaching-board-agent-build-plan.md)
and [candidate guide](2026-10-25-teaching-board-agent-candidate.md) record the
integrated local enforcement and tests. The implementation-status statements in
this original decision note describe its documentation-only checkpoint; they are
not the latest source status. Live-provider/deployment/physical gates remain open.

25 October 2026. **User-delegated design defaults**, selected after the user asked the coordinator to settle Google spending, source routing, chart data, cloud indexing and automatic web reuse. These choices are concrete implementation direction, not claims that the user supplied each limit verbatim. They do not change live settings, send requests, upload content, spend money or approve deployment.

This note resolves the five open policy items in [the library/memory research](research/2026-10-25-teaching-board-library-memory-research.md). The confirmed workflow remains one polished Board page, one saved teaching profile, clear progress/cancellation, continued work beyond the 15-second target, the current pupil page retained until the complete replacement is ready, targeted edits with Undo, and automatic saving of reusable results. The [consolidated programme](2026-10-21-companion-media-agent-master-plan.md) still owns broader release and deployment gates.

## 1. Google spending

- Retain **A$30 per calendar month in Australia/Brisbane** as the shared image-generation allocation envelope, including existing image workflows; do not give Board a second independent A$30 allowance.
- An ordinary Board request may automatically dispatch **one new Google picture attempt**, with a conservative configured estimate of **at most A$0.50 for the whole request**. Default to the supported 1K output; a higher-resolution request needs its own valid estimate within that limit or an explicit teacher override. The configured estimate must be positive and appropriate to the exact provider/model/options, not copied from an old trial.
- No automatic paid refinement, second candidate, quality-improvement loop or replacement identity after an uncertain call. A follow-up requiring another paid picture is shown as a paid action with its estimate; explicit confirmation authorises that additional attempt within the remaining monthly allowance.
- Reserve through the existing shared ledger before dispatch. Missing estimate, unavailable ledger, exhausted allowance or an estimate over the request limit means **no chargeable dispatch**. Show one concise teacher action to choose an existing image, change the brief or review the paid exception.
- Keep uncertain reservations held and reconcile the same job. Changing a brief, reopening a lesson or cancelling the UI does not prove the provider stopped or justify another automatic paid attempt.

These are **application allocation limits, not a guaranteed Google invoice cap or protection against spending outside this application**. The current ledger commits conservative estimated allocations rather than measured provider charges. Source: [reservation and dispatch](../tools/compose/media_service.py#L70), [ledger accounting](../server/media_library_server.py#L322), [exact output allocation](../tools/compose/image_provider_config.py#L78). The A$0.50 request guard and Board-attempt policy are new work; they are not already enforced by these files.

## 2. Source routing

Search the saved library first and pin a suitable exact version. A clear match is selected automatically; genuine ambiguity uses a small thumbnail chooser. An explicit teacher source instruction overrides ordinary routing, while retaining that source's limits.

When no suitable saved resource exists, choose by intent:

| Requested result | Default route |
| --- | --- |
| Graph/chart based on values | Validated structured data → deterministic local chart rendering |
| Photo or factual depiction of a real subject/place/object | One bounded Wikimedia Commons search for a reusable, relevant image |
| Original illustration, scene or requested visual treatment | One Google picture attempt within the policy above |

Do not try every provider sequentially by default. A failed factual-photo search does not silently become a synthetic image presented as photographic evidence. If the requested image is required and no permitted route succeeds, hold the current pupil page and show the teacher a concise choice. Do not silently omit it, substitute a different teaching meaning or publish an incomplete replacement. A nonessential decorative item may be omitted only when the brief/profile permits it and the completed teacher result states that omission.

Local-only mode suppresses external lookup, Google generation and cloud indexing. Current Commons and Google adapters can be reused, but their automatic Board routing is not implemented: [media workflow](../tools/compose/media_service.py#L142).

## 3. Chart data and reproducibility

Factual charts use teacher-supplied data, an explicitly selected saved dataset, or an appropriately licensed primary published dataset relevant to the request. Preserve the exact dataset version, publisher/source, retrieval/publication date, units, coverage and deterministic transformations. Missing values stay missing unless an explicit documented transformation is requested. The agent may choose the chart form and styling, but must not invent measurements, silently change units or infer precise values through semantic search.

If required factual data cannot be found, ask one focused question or offer a clearly labelled illustrative chart. Illustrative values are permitted when the request or saved profile **explicitly permits example/illustrative data**; label them in the pupil-facing chart, not only in private metadata. Otherwise, do not invent them.

Store reusable dataset, chart specification and rendered preview as related immutable versions. Calculations and supported chart transformations run locally through validated operations. A Google-generated picture of a graph is not the factual chart/data source. The [research proposal](research/2026-10-25-teaching-board-library-memory-research.md#typed-resources-relationships-and-reusable-packages) records the typed-resource design; none of those new parsers/renderers has been implemented or benchmarked in this note.

## 4. Cloud indexing and teaching-profile privacy

Default to **local metadata, deterministic extraction and SQLite FTS5**. No cloud captioning, embedding or bulk upload of existing/private resources is enabled. Permission to generate a Google picture does not automatically authorise uploading that picture again for indexing, nor uploading neighbouring resources or the teacher profile.

Offer an explicit future opt-in per selected collection and processing operation, recording resource types, permitted text/images/video frames, provider/model, byte/frame limits, cost allowance and consent revision. Only material within that scope may enter its enrichment queue. Cloud-enrichment allocation defaults to **A$0 until separately enabled**; it does not silently consume the image-generation allowance. Revocation stops new jobs and marks pending work accordingly; already-submitted work needs reconciliation.

Already available title, provenance, dimensions, chart specification and generation brief may populate local catalogue fields. Treat the brief as intended content, not proof of what the image depicts. Preserve teacher corrections separately. Keep teacher-profile instructions local and send only the effective teaching defaults needed for an explicitly requested composition, following the existing bounded-context design. Google embedding is a separate processing capability with modality limits and model-version compatibility rules: [official embedding documentation](https://ai.google.dev/gemini-api/docs/embeddings). No cloud indexing was tested or enabled here.

## 5. Automatic web reuse

Initially automate **supported raster-image retrieval from Wikimedia Commons only**, using existing origin/download allowlists and decode limits. Admit automatic reuse only when machine-readable file metadata and the source page provide a supported, consistent rights basis:

- CC0 1.0;
- CC BY, initially **CC BY 4.0** with complete attribution information;
- an explicit public-domain designation/mark with supporting source information and no conflicting jurisdiction/restriction indication. An ambiguous `Public domain` string alone does not pass.

Do not automatically import unclear, conflicting, noncommercial, no-derivatives or share-alike-only material in this first slice. This is a deliberately narrow automation policy, not a statement that other licensed material cannot be used. Teacher-reviewed routes can be added later with their exact obligations.

Retain the source/file URL, creator, title, licence URL/version, acquisition time, bytes/hash and required attribution notices; record crops/other changes. Put required credit into a readable pupil-visible credits area and preserve it in saved/exported resources. Unknown terms, missing required credit or conflicting metadata stop automatic reuse. Visible availability on Commons is not itself the reuse decision. The current adapter retains a short licence name and requires manual acknowledgement; add a real metadata/rights-policy validator rather than passing `rights_acknowledged=True` unconditionally. [Current retriever](../tools/compose/media_providers.py#L102), [MediaWiki file metadata API](https://www.mediawiki.org/wiki/API:Imageinfo)

CC BY 4.0 permits copying/adaptation subject to attribution, a licence link and change notices; CC0 dedicates rights to the extent possible. Public Domain Mark identifies known copyright status rather than granting a new licence. These tools do not themselves settle every privacy/personality/trademark right. The automation filter is an application policy, not legal clearance for every file or a blanket educational-use exemption. [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), [CC0](https://creativecommons.org/publicdomain/zero/1.0/), [Public Domain Mark](https://creativecommons.org/publicdomain/mark/1.0/), [Commons reuse guidance](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia)

Video, datasets and other resource types remain within the library design, but require their own supported acquisition/validation/presentation paths before automatic imports are enabled.

## Publication and the existing generated-image preview condition

Ordinary explicitly requested Board text/layout changes and clear approved-library selections retain direct atomic application with Undo. No blanket new approval is added to those actions. Freeze still holds the pupil view unchanged.

The programme separately requires generated-image preview. **Default for a newly Google-generated asset: prepare the complete result privately, show its thumbnail in the teacher preview, and use one “Use image and present” action for its first pupil-facing use.** Automatic generation and automatic library saving do not imply automatic human quality approval or canonical promotion. After acceptance, reuse the pinned saved version normally. Rejected images remain excluded from ordinary auto-selection until reviewed.

This preserves a real existing condition: fully hands-free first presentation of a newly generated image would change the programme's preview/quality policy. It is not assumed from the request for automatic fallback. The initial slice retains the preview condition while allowing automatic acquisition, layout and storage. Missing/failed required resources keep the current pupil page displayed; cancellation never publishes a partial page.

## Implementation status and next step

No further user choice is mandatory to implement against these delegated defaults. A specific exception may still require the single focused teacher action described above. Next, reconcile these policies into the Board composition contract and implement the narrow typed page workflow, with per-request spending guards, rights metadata, local catalogue/search, truthful progress and exact-version/Undo/reopen tests. Finish the intended Hermes route in parallel before live-runtime acceptance.

This note and its research-status link are documentation changes only. No source/schema migration, provider call, upload, live setting change, deployment, new performance test or classroom acceptance occurred.
