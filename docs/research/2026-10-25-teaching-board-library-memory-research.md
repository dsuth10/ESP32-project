# Teaching Board: reusable lesson-resource library and agent memory

Later implementation checkpoint: the
[agent build plan](../2026-10-25-teaching-board-agent-build-plan.md) reconciles this
research and the delegated defaults into an integrated local first slice. This
report retains its original research-only evidence. Semantic indexing/enrichment,
catalogue sync and broader-format presentation remain later increments.

25 October 2026. Research and proposed design, based on current repository source and primary documentation retrieved today. **This is not an implemented catalogue, a paid-provider trial, deployed sync, or classroom acceptance.** No live library, credentials, services or firmware were changed. The current development programme remains [the consolidated plan](../2026-10-21-companion-media-agent-master-plan.md).

## Recommendation

Evolve the existing application-owned SQLite media store into a **typed reusable lesson-resource library**, preserving immutable versions, hash-addressed content and existing image identities. The scope includes images, videos, datasets, graphs/charts, structured data and other lesson resources. Add a structured, agent-maintained catalogue and SQLite FTS5 search first. Design rebuildable modality-specific semantic indexes alongside it, and select their embedding model/backend through a small measured comparison. Store the one explicit teaching profile separately, and assemble a small, version-bound working context for each Board request.

Do not introduce Mem0, Letta or a graph database as the owner of the resource library. They address broader agent/context needs, while the immediate missing capability is reliable resource description, discovery, exact retrieval and reuse. Explicit dataset → chart → preview and video → transcript relationships fit relational tables initially; having these relationships does not itself require a graph database. This is an architectural judgement from the code and product requirements below, not a benchmark claim that one technology is universally best.

The next implementation should prove one complete loop: **request a page → search the local catalogue → resolve the intended image or chart → build and check the layout → apply atomically → save reusable media → revise by command → undo → reopen offline**. Build the catalogue foundation within that slice, rather than postponing the page workflow for a general memory platform.

## Confirmed intent and remaining decisions

The user confirmed in the current conversation:

- Start with one polished editable Board page; the agent may write and arrange the content while preserving explicitly supplied wording.
- Handle ordinary layout conflicts automatically. Use consistent projector-friendly styles and preserve readability.
- Select a clear library match automatically and use a small thumbnail chooser for genuine ambiguity.
- Automatic web retrieval and Google image generation are wanted when a suitable saved image is unavailable. “Code generation” means charts as well as Google-generated pictures.
- Start with **one saved teaching profile**, including year-level/default instructions and a free-text instruction area. Lesson context and the current instruction can override defaults; show effective teaching context privately to the teacher.
- A 15-second result is a target to measure. Continue with clear progress and cancellation when work takes longer. Keep the existing pupil page until the complete replacement is ready.
- Support targeted follow-up edits immediately.
- **Automatically save reusable results into the library**, building a larger searchable collection over time.
- The library's scope extends beyond images: videos, datasets, graphs/charts, data and other materials used in lessons/presentations belong in the design. Catalogue capacity is distinct from which formats the current Board can present.

Subsequent user delegation asked the coordinator to settle Google spending/attempt limits, source routing, chart-data rules, web reuse and cloud-indexing permissions. The [delegated operating-default note](../2026-10-25-board-agent-default-policies.md) now supplies concrete design defaults for those five items; they are not verbatim user answers or live configuration. Earlier documents' explicit-search rules describe the earlier scope; reconcile the newly requested automatic fallback with these defaults before implementation. The research comparisons below remain proposals rather than installed capabilities.

## Four separate kinds of state

| State | Proposed owner | What it contains | Retrieval/use |
| --- | --- | --- | --- |
| Durable resources | Evolved existing library store and hash-addressed blobs | Exact file/structured-resource content, immutable version, lineage, provenance, canonical choice and dependencies | Resolve and verify exact versions before use; lesson package retains required independent content |
| Searchable catalogue | Versioned application tables plus rebuildable indexes | Titles, descriptions, aliases, tags, educational facets, visual observations and quality state | Query the entire library locally; give the agent only a ranked shortlist |
| Teaching profile | One bounded local settings record, explicitly editable by teacher | Year level, language, default pedagogy/style and free-text instructions | Include the effective snapshot in the prepared Board request |
| Board working context | Existing document/session plus bounded request/result records | Current page, selected objects, exact image choices, current instruction and relevant follow-up context | Stable IDs/revisions; reject stale results and preserve Undo/Freeze |

Conversation History, provider prompts, credentials and the Linux agent's own memories remain separate. The programme already requires a separate media service and excludes History/prompts/secrets from media sync; a retrieval index does not change those boundaries. [Programme decisions and architecture](../2026-10-21-companion-media-agent-master-plan.md)

## What exists in the code

| Area | Current source evidence | Consequence |
| --- | --- | --- |
| Storage | Schema v2 has `asset` title/tags/canonical/revisions and immutable `asset_version` metadata, parent, hash, dimensions, source and origin. Hash and asset/date indexes exist. [media_store.py, schema](../../tools/compose/media_store.py#L97) | Preserve these identities, lineage and canonical semantics; add catalogue annotations rather than rewriting image history |
| Search | `list_assets()` loads assets and performs normalised whole-query substring matching over title/tags, returning recent matches up to 500. [media_store.py, search](../../tools/compose/media_store.py#L399) | No ranked token search, synonyms, educational facets or visual search; this is the first search gap |
| Board chooser | Streams candidate rows and matches before its 500-result limit. [board_images.py](../../tools/compose/board_images.py#L79) | The recent search-limit fix is preserved, but does not provide semantic ranking |
| Deduplication | SHA-256 shares physical blobs. A normal new import still creates another asset/version; `operation_id` handles repeated operations. [media_store.py, import](../../tools/compose/media_store.py#L281) | A content hash is not yet catalogue deduplication; retain separate acquisition provenance |
| Agent recommendation | The existing catalogue snapshot contains at most 12 entries with bounded title/tags, IDs and dimensions; no pixels. It validates the exact recommendation and local bytes. [hermes_catalogue.py](../../tools/compose/hermes_catalogue.py#L7) | Reuse its exact-version checks; search before constructing the shortlist. Metadata-only matching cannot establish what an image actually depicts |
| Sync | Current events/source metadata are allowlisted. Source fields are URL, creator, licence, attribution, provider and model. [media_store.py](../../tools/compose/media_store.py#L364), [server validation](../../server/media_library_server.py#L62) | Captions, embeddings and profiles need explicit contracts; do not hide them in source fields |
| Tag bounds | Client accepts up to 100 tags; current server accepts 40 tags of at most 80 characters. Same source files as above. | Reconcile this concrete mismatch before automatic tagging grows; use bounded normalised tags and structured facets |
| Google | Source defaults name `gemini-nano-banana-2.1`; the adapter supports reference images and resolution allocations. Existing service has reservation/receipt/uncertainty handling and explicit generation, but no automatic tagging. [image_provider_config.py](../../tools/compose/image_provider_config.py#L9), [media_service.py](../../tools/compose/media_service.py#L27) | Reuse the adapter and its durable job semantics; do not infer live settings/account access from source defaults |
| Profile/context | Unknown settings keys are not retained, and Board/context schemas are strict. [companion_settings.py](../../tools/compose/companion_settings.py#L14), [board_model.py](../../tools/compose/board_model.py#L139), [board_hermes.py](../../tools/compose/board_hermes.py#L24) | A saved profile requires a deliberate versioned extension and a captured effective request snapshot |
| Current format gates | Local import accepts only PNG/JPEG/WebP, up to 20 MiB and 25 megapixels, with decode validation. Server accepts only those image types/20 MiB and its decoder limits images to 16 megapixels. [local validation](../../tools/compose/media_store.py#L216), [server types](../../server/media_library_server.py#L29), [server decode](../../server/media_library_server.py#L405) | Existing local/server image-limit mismatch needs reconciliation. Removing image checks would not implement safe video/dataset import |
| Board rendering | Object kinds are text, image, shape, arrow and ink; unsupported kinds reject. [board_model.py](../../tools/compose/board_model.py#L23) | A generic library row alone does not add video playback, data parsing or editable chart behaviour; each needs an accepted importer/renderer path |

Local feasibility check today: the default Python 3.13.7 runtime uses SQLite 3.50.4. An **in-memory only** FTS5 table was created, populated and searched successfully. That proves this interpreter has FTS5; it does not prove packaged application support, catalogue migration or performance. No additional packages were installed.

## Typed resources, relationships and reusable packages

Introduce a common resource/version envelope with an extensible `resource_type`, content MIME, byte count/hash, origin, schema version and availability state. Keep type-specific metadata in validated records rather than adding every possible property to one unbounded JSON field. Existing image asset/version IDs must survive migration. A resource may have several representations: a dataset's source file, a chart specification, a chart PNG preview and a lesson dependency manifest are related resources, not interchangeable files.

| Resource type | Minimum proposed type-specific information | Searchable representation | Usage boundary |
| --- | --- | --- | --- |
| Image | Dimensions, format, alt description, labels, visual type | Title/tags/caption/OCR plus optional visual vector | Existing image insertion after validation; exact version remains pinned |
| Video/audio | Container/codecs, duration, dimensions/tracks/language, local-cache state, source rights; optional poster, transcript/caption tracks and time ranges | Resource summary and timestamped transcript chunks; optional sampled visual/audio vectors | Catalogue/search can precede playback. Codec, seek/playback, audio output, offline package and audience controls need separate acceptance |
| Tabular dataset | Column schema, types, units, missing-value convention, row count, coverage/date/geography, source/licence, factual/illustrative status | Dataset/column names and descriptions, bounded validated sample/summary; actual data remains queryable separately | Do not embed the whole table into the composition prompt. Numeric values come from validated source/subset operations, not approximate vector retrieval |
| Graph/chart | Dataset version IDs, structured chart/diagram specification, labels/units, transformation parameters, renderer/version, preview | Title, question answered, concepts, axes/series/variables, visual form | Preserve editable specification and source data; a raster preview supports the existing image renderer while richer chart editing is developed |
| Text/document | Format/language, extracted text, page/section boundaries and extraction status | Bounded text chunks tied to resource version and location | Extracted text is derived; it is not permission to import a whole document into the Board or execute macros |
| Other attachment/structured resource | Declared and validated schema/type, content hash, source, capability state | Common metadata plus an accepted type-specific extractor if present | Extensible schema does not mean unrestricted execution or automatic rendering of unknown formats |

Use a small relationship table with exact version endpoints, relation type and derivation metadata: `derived_from`, `rendered_from`, `thumbnail_of`, `transcript_of`, `segment_of`, `uses`, `part_of` and `supersedes`. Examples: rainfall CSV version → validated subset/transformation → chart specification version → rendered PNG version; video version → transcript version → timed transcript chunk. A reused video segment should reference the original version plus start/end times; whether to materialise a new clip depends on offline/playback/rights requirements.

This follows established provenance concepts—source entities, processing activities, outputs and responsible agents—without requiring an RDF database. W3C PROV defines interoperable provenance models, and RO-Crate's current provenance guidance records software versions, inputs and outputs. Use them as vocabulary/interchange references rather than imposing a full research-repository stack. [W3C PROV overview](https://www.w3.org/TR/prov-overview/), [RO-Crate 1.3 provenance](https://www.researchobject.org/ro-crate/specification/1.3/provenance.html)

For tabular data, the current Data Package Table Schema describes JSON field types/formats, constraints, missing values and keys. Reuse a compatible bounded schema vocabulary instead of inventing ambiguous column metadata; record metric units explicitly in application metadata. [Table Schema](https://datapackage.org/standard/table-schema/)

For charts, prefer an application-validated declarative specification to arbitrary generated program execution. Vega-Lite is a candidate reference: it uses JSON descriptions and has documented compilation/export routes, including PNG/SVG/PDF. Choosing it still needs a renderer/package/licence and security review; this research did not install or select a chart runtime. A constrained Board-native chart compiler is another candidate for the initial bar/line/scatter charts. [Vega-Lite overview](https://vega.github.io/vega-lite/docs/), [compilation/export](https://vega.github.io/vega-lite/usage/compile.html)

The library should expose separate states for metadata known, original cached, preview ready, full content available offline and supported in the current Board. Keep a source URL alongside cached content identity; URL availability is not offline availability. Do not promise a video is embeddable or distributable merely because it can be searched. Large videos/datasets need type-specific byte/time/row/column/CPU limits and streaming/resumable transfer, rather than lifting the current image limit globally. Parser/transcoder work belongs in bounded workers with cancellation; generated chart/data expressions are validated against supported operations. Archive/package import must check paths, dependencies and expansion limits before extraction.

A portable lesson needs a manifest listing exact resource/dependency versions, hashes, relative paths, essential provenance and required capabilities. Include the data/specification needed to edit a chart as well as its display preview; include permitted offline video content/captions when supported. Missing or externally linked dependencies must be explicit. RO-Crate is a useful established packaging/interchange reference for mixed files and provenance; adopting its entire JSON-LD model is optional and should follow interoperability needs. [Current RO-Crate specification](https://www.researchobject.org/ro-crate/specification/1.3/index.html)

## Technology assessment

### SQLite FTS5: implement first

FTS5 provides ranked full-text search, weighted BM25 columns, phrase/prefix queries and configurable tokenisation. External-content indexes require explicit maintenance to stay consistent with their owning tables. SQLite itself is public domain. [FTS5 documentation](https://www.sqlite.org/fts5.html), [SQLite copyright](https://www.sqlite.org/copyright.html)

Proposed use: index the effective title, aliases, description, observed labels and approved tags. Weight exact title/aliases more strongly than broad machine descriptions; apply year level, subject, media type and usability filters as structured constraints. Treat user input as search terms through a bounded query builder, not arbitrary SQL or unchecked FTS syntax. Start with Unicode tokenisation and a small explicit synonym/alias table; evaluate stemming and substring support against educational queries before selecting them. Keep Australian spellings and useful alternate forms such as `water cycle`/`hydrological cycle` without silently changing the displayed teacher label.

Use an application-owned catalogue table and transactionally maintained FTS projection. Include a catalogue revision and provide a deterministic full rebuild. The text index remains derived: deleting or rebuilding it cannot lose images, annotations or provenance. No extension download or additional running service is required for the interpreter tested above.

### Hybrid retrieval: design now, add after a measured comparison

Text embeddings help retrieve paraphrases; visual embeddings help retrieve the depicted content independently of a filename. Neither removes the need for exact identifiers, structured filters or provenance. A useful proposed pipeline is lexical retrieval plus image/text semantic retrieval, rank fusion, then optional reranking of a small shortlist. Qdrant documents reciprocal rank fusion of multiple rankings; Sentence Transformers documents retrieve-then-rerank. Those establish available approaches, not an accuracy result for this library. [Qdrant hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/), [Sentence Transformers reranking](https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html)

Compare these embedding paths:

| Path | Documented capability | Fit and limits for this application |
| --- | --- | --- |
| Local CLIP image/text baseline | Sentence Transformers supports shared text/image vectors, image similarity and near-duplicate examples; its image wrapper page labels image-text support experimental. OpenAI CLIP provides CPU/GPU usage and is MIT-licensed. [Image-search docs](https://sbert.net/examples/sentence_transformer/applications/image-search/README.html), [CLIP source](https://github.com/openai/CLIP) | Best first **offline baseline to evaluate**. Requires model/runtime packaging and cold/warm latency measurement; image similarity is not proof of correct scientific labels or exact chart data. Pin and review the actual weight artefact's licence before bundling; repository licence alone is not a complete dependency audit |
| Google Gemini Embedding 2 | Current Gemini docs describe text, image, video, audio and document inputs in a shared embedding space, with modality-specific limits. Model generations use incompatible spaces and migration needs re-embedding. [Gemini embedding docs](https://ai.google.dev/gemini-api/docs/embeddings) | Strong cloud candidate to compare because the project already uses Google, but this is a **new adapter/data-processing use**, not a feature of the current image-generation call. Needs permitted content upload, cost/account validation and cached vectors. Long media needs segmentation and version/time references; one vector for a whole lesson/video will lose useful location detail. Preserve offline lexical search; offline semantic query support would need a compatible local encoder, not just downloaded cloud document vectors |

Google's listed standard embedding prices today are US$0.20 per million text input tokens and US$0.00012 per image; batch image price is US$0.00006. Thus 10,000 one-pass image embeddings would be US$1.20 standard or US$0.60 batch **for that listed image component alone**; descriptions, query calls, retries, taxes and exchange rates are additional. These are derived estimates, not measured account charges or an A$ conversion. Google's paid-service terms distinguish how uploaded content is used from unpaid services. Do not silently use an unpaid tier or bulk-upload an existing private library. [Current pricing](https://ai.google.dev/gemini-api/docs/pricing#gemini-embedding-2), [Gemini API terms](https://ai.google.dev/gemini-api/terms)

Evaluate the vector index separately from the embedding model:

| Index candidate | Primary evidence | Decision |
| --- | --- | --- |
| `sqlite-vec` | Embedded SQL vector tables; Windows support claimed by its source; pre-v1 breaking-change warning; MIT/Apache-2 licensing. [Docs](https://alexgarcia.xyz/sqlite-vec/), [source](https://github.com/asg017/sqlite-vec) | First embedded prototype candidate if vectors are justified. Pin the package/extension and rebuildable schema; test DLL loading, packaging, filtering and query throughput on the actual Windows candidate. Not installed or verified here |
| SQLite Vec1 | Current official page describes ANN, portable C, Windows compilation and version 0.8; roadmap still lists testing/optimisation and partition-key work. [Vec1 docs](https://sqlite.org/vec1.html) | Include in a bounded comparison if scale requires ANN. Newer official work is worth tracking, but is not established as a drop-in packaged replacement here |
| Qdrant | Vector/payload service, hybrid queries and Apache-2 licence. Python client has persistent local mode, documented primarily for development/prototyping, and a server path. [Source](https://github.com/qdrant/qdrant), [client](https://github.com/qdrant/qdrant-client) | A later option if measured concurrency/scale needs a separate index service. Adds another index lifecycle and, in server mode, operational dependency. It should remain a projection of the existing media store, not own media/canonical truth. No size threshold is assumed without measurements |

### General agent-memory systems: do not adopt for this slice

| Option | What its current primary source actually offers | Assessment |
| --- | --- | --- |
| Mem0 | User/session/agent memory, preference extraction/retrieval and self-hosted/managed options; Apache-2 source. [Mem0 repository](https://github.com/mem0ai/mem0) | Potential later choice for approved conversational preference learning. One explicit teaching profile needs no extraction engine, and summarised memories cannot replace exact media/version/provenance records |
| Letta | Current SDK persists agent memory in a memory repository, with agent updates/dreaming. Its main repository points to the newer Letta Code runtime and labels V1 historical. [Current memory docs](https://docs.letta.com/agent-sdk/memory), [repository](https://github.com/letta-ai/letta) | Useful concepts for bounded working memory, but adopting another agent runtime is unnecessary for the current Hermes/Board integration. Avoid designing against legacy-only memory-block examples |
| Graphiti / Zep | Graphiti builds temporal context graphs and needs an operated graph backend; Zep supplies a managed enterprise context layer. Graphiti is Apache-2. [Graphiti source](https://github.com/getzep/graphiti) | Defer until actual queries require temporal relationships across lessons/concepts. A graph can complement a catalogue later; it does not supply exact image storage or automatically solve visual matching. Current code's Graphify developer graph is a separate concern |

No vendor's published memory benchmark is used as evidence of retrieval quality or live-teaching latency in this application.

## Proposed catalogue and agent organisation

These are proposed fields and contracts, not changes already applied.

| Group | Suggested fields and ownership |
| --- | --- |
| Identity | Existing asset/version UUIDs and SHA-256; resource type and validated type-schema version; acquisition event ID; current annotation revision; tombstone/hidden state |
| Human labels | Teacher title, description, aliases, tags, collections and corrections; preserve separately from machine suggestions |
| Educational facets | Subject, topic/concepts, optional curriculum references, year-level range, difficulty/detail, learning use such as explanation/question/assessment |
| Visual facts | Photo/illustration/diagram/chart, named subjects/actions, aspect ratio, labels present, OCR text where reliable, language, background/transparent state, alt description |
| Provenance and suitability | Existing source/creator/licence/attribution/provider/model; acquired/generated/local/chart origin; reuse status; visual/correctness review status; observed limitations |
| Machine annotations | Suggested values, confidence/evidence basis, annotator model/version, prompt-template version, image hash, created time; explicitly distinguish visually observed from inferred/prompt-requested content |
| Retrieval projection | Effective searchable text/hash, index version, optional embedding model/version/dimension/normalisation, embedding status and source revision; chunk ID and page/time/table-location reference where applicable |
| Chart-specific origin | Original supplied/sourced dataset reference, units, labels, source date, factual versus illustrative status, structured chart specification and renderer version; rendered preview is linked to this origin |

Prefer faceted collections over one rigid folder tree. The same water-cycle image may belong to Science, Year 5, evaporation and a particular lesson. Use stable concept IDs with editable labels/aliases; avoid a model continually inventing near-identical tags. Begin with a small vocabulary derived from current teaching use and retain a bounded free-tag field. Curriculum codes suggested by the agent remain suggestions until validated against the intended curriculum/source; the image's subject alone cannot prove alignment.

On successful acquisition, commit bytes and minimal deterministic metadata immediately; then enqueue optional description/tag/OCR/embedding enrichment. The agent may add machine annotations and proposed aliases in bounded background work. It may not overwrite locked teacher labels, move canonical image pointers, merge versions, or mark scientific correctness/reuse as verified merely because a model produced a confident description. Teacher correction overrides the effective search projection and survives re-enrichment. A correction to a caption changes annotation/index revisions, not the immutable image bytes.

Use generation briefs as candidate discovery text, with an `intended` evidence label. They are not observations that the resulting image contains every requested element. A chart produced locally can supply deterministic labels/units from its structured specification; a generated raster chart should not be treated as a reliable substitute for the source dataset.

Do not retain every failed or rejected candidate as a normal reusable search result. Preserve necessary job/attempt receipts privately; reusable library entries should have valid decoded content, minimum metadata and a distinct draft/review state. Automatic saving does not equal teacher quality approval or canonical promotion. This preserves the existing explicit canonical-version decision while satisfying the user's automatic library-growth request.

## Retrieval contract and confidence

1. Parse the teacher's query into exact references plus bounded semantic intent/facets. The search service, not the remote agent, owns SQL and library traversal.
2. Exact pinned IDs and exact teacher aliases take priority. Apply exclusions such as deleted, unavailable, unsuitable licence or incompatible visual type before ranking.
3. Search the full catalogue with lexical retrieval, then optional compatible semantic retrieval; fuse rankings. Search relevant versioned chunks for transcripts/documents, return their locations and group hits by resource. Include matching reasons and evidence basis, not just a score. Data queries such as a particular rainfall value use the dataset's structured values and units, not a semantic guess.
4. Give the composition agent a small shortlist of exact version IDs, dimensions, relevant description/facets and provenance summary. Resolve bytes locally and verify the selected hash before import. Do not send the entire library, prompts or History.
5. Auto-select only when calibrated evidence supports a clear match. Use query-specific acceptance and top-result separation measured against teacher judgements; do not call cosine similarity a probability or choose a universal threshold such as 0.8.
6. Show thumbnails when several versions/assets genuinely fit. Use a bounded visual check of top candidates when required by the query; metadata-only evidence cannot establish exact visual content. A model inspecting pixels is also fallible, particularly for labels, counts and scientific correctness.
7. Report no adequate match honestly, then use the agreed fallback route. The required web/Google allowance and factual-chart policy still need decisions. No “no match” result should trigger repeated paid retries under a new identity.

Follow-up phrases such as “that image” refer to the selected Board object's version ID. “Our usual water-cycle diagram” can use an explicit teacher alias/preference, stored with scope and revision. Do not silently infer permanent preferences from one incidental choice; offer an explicit correction action such as “Use this as my usual image for water cycle”.

## Deduplication, recovery, migration and sync

- **Exact bytes:** use SHA-256 to avoid repeated blob storage. For automatic imports, recognise an existing exact version and attach a new acquisition record where needed. Preserve independent provenance/rights facts rather than discarding them in a blind merge.
- **Same image, different bytes:** perceptual/embedding similarity may propose a duplicate group, but compression, crop, labels and diagram corrections matter. Group for review; do not auto-delete, merge immutable lineage or change existing lessons.
- **Enrichment jobs:** persist input hash, annotation revision, model/template/version, job identity and status (`pending`, `running`, `complete`, `failed`, `uncertain`, `stale`). Coalesce repeated work and enforce a distinct enrichment allowance/concurrency limit. Reconcile uncertain paid calls; ordinary retryable local indexing is different from uncertain paid dispatch.
- **Backfill:** start with a bounded, resumable queue; prioritise used/recent assets, then older assets. A failed caption/embedding leaves lexical and manual search available. Do not delay the lesson's valid saved bytes while indexing fails.
- **Model changes:** keep old and new embedding spaces separate, build the replacement projection, evaluate it, then switch. Never compare vectors from incompatible encoders. Record source hash and caption revision so stale projections can be identified.
- **Schema migration:** introduce explicit catalogue/annotation versioning and a tested upgrade/rollback/export path. Rebuild FTS after migration and check missing/orphan rows. Do not silently mutate an active read-only source library from the Board picker.
- **Sync:** extend the current version/canonical protocol deliberately for catalogue annotation revisions and conflicts. Keep human and machine fields separate and preserve competing teacher edits. Resolve the current client/server tag-bound mismatch first. Send allowlisted descriptive metadata, not full prompts/teacher profile/History. Derived indexes should normally rebuild locally; vector synchronisation, if later chosen, must include the exact encoder and input revision.
- **Broader format sync:** add resource types/dependency manifests and capability negotiation explicitly. Old image clients must not attempt to decode video/data as images. Large transfers need independently tested resume/checksum/storage behaviour. Dependencies become available atomically for an offline-capable package, or its missing capabilities are reported; a synced title alone is not a usable synced resource.
- **Portable lessons:** continue pinning the actual bytes and essential provenance. A shared catalogue reindex, rename or canonical switch cannot change a saved lesson. Profile free text, private source paths and background job logs are not automatically included.
- **Removal:** tombstone search entries promptly, remove derived rows, and respect references from existing lessons/versions. Retention and physical blob deletion need the existing media-retention design; a search-index delete is not proof of erasure from backups or lessons.

These are proposed application rules. They are not automatically supplied by choosing FTS5, a vector database or a memory framework.

## Teaching profile and request context

Use one versioned local profile with structured defaults and bounded free text, a visible edit/reset UI and an explicit revision. Suggested precedence is current instruction → lesson context → teacher defaults. Snapshot the effective values into each prepared Board request and include their digest, preserving the existing request/revision/session checks. Show the teacher which defaults were used.

The profile is teacher-authored guidance, not authority for executing code, changing network settings or bypassing tool checks. Retrieved image captions, OCR and web metadata are content, not instructions. Do not silently learn sensitive pupil information, copy unrelated History or edit the persistent profile from an ordinary composition request. Global teaching profile sync/portable export remains a separate choice.

For follow-up edits, retain the current page snapshot, relevant recent instruction/result and selected object IDs. Use a bounded context budget and explicit lesson-wide scope only when needed. A long-lived conversational memory product can be reconsidered if later requirements exceed this, but it is not required for the first page.

## Proposed delivery sequence and evaluation

| Slice | Reviewable result | Evidence required |
| --- | --- | --- |
| L1 | One saved profile; typed resource/version/dependency and annotation contracts preserving image compatibility; auto-save metadata and exact-duplicate handling; FTS5 ranked/faceted search | Migration/rebuild/recovery tests, preserved manual labels and provenance, strict sync-bound tests, actual Windows packaged-runtime FTS check |
| L2 | Typed Board request uses local search/shortlist and exact immutable versions; deterministic charts/layout; atomic complete publication, follow-up and Undo | One real polished page, a targeted revision, cancel/stale/failure cases, unchanged pupil view while working, saved offline reopen |
| L3 | Bounded enrichment queue and offline-versus-Google embedding experiment behind the same search contract | Retrieval relevance improvement, cold/warm timings, package/memory footprint, privacy/cost review; no regression in exact matching |
| L4 | Explicit catalogue sync and growing-library stress/recovery | Two real Windows installations after deployment, concurrent teacher edits, offline backlog, deletion/index rebuild and restore |
| L5 | Additional validated format slices: datasets/editable charts, video/audio and document extraction as separately scoped capabilities | Per-type import, preview/search, cancellation/resource limits, provenance, offline dependencies, sync and presentation acceptance. The current agreement still places Board audio/video presentation later |

L1/L2 should remain small enough to prove the user workflow. The intended Hermes private HTTPS route can be completed in parallel; neither a text/vector index nor healthy fixtures establish real agent deployment acceptance.

Use a teacher-judged evaluation set of roughly 100 queries initially, covering exact names, aliases/Australian spellings, paraphrases, visual relations, labelled/unlabelled diagrams, wrong-year distractors, exact versions, duplicates and genuine no-match cases. Include questions such as “the water-cycle picture with no labels”, “a kangaroo facing left”, “our approved evaporation diagram” and “the rainfall chart in millimetres”. Extend the set with “the video section explaining condensation”, “the dataset used for that graph”, source-date/unit queries and mixed-type distractors. Mark acceptable resources/versions/locations and why. Version the judgements and retain a held-out set.

Proposed test sizes are **1,000, 10,000 and 100,000 catalogue/version records**; these are stress targets, not forecasts of the user's collection or claimed benchmarks. Retrieval-quality tests require diverse real/approved fixtures. Synthetic metadata can measure scale and correctness of indexing, not semantic relevance. Measure:

- exact-ID/title/alias recall, recall@5, first-choice precision, ranking quality and no-match/ambiguity accuracy;
- rate of confident wrong auto-selection, especially incorrect scientific labels/counts and near-identical versions;
- teacher corrections, time to a usable image and repeated-image reuse;
- p50/p95 local query latency, cold/warm model startup, indexing/backfill throughput, RAM/disk/package footprint;
- total time split into library search, agent/model queue, composition, validation/render, web retrieval and Google generation;
- enrichment/provider charges from receipts/invoices, failed/uncertain jobs, offline behaviour and duplicate dispatches.

Suggested initial engineering goals to agree, **not results**: exact-reference retrieval always returns the intended available version; a high-confidence auto-select policy favours precision over coverage; warm local search remains a small part of the 15-second composition target. Do not set an unconditional similarity or latency acceptance number before the corpus/hardware measurements. UI progress should begin promptly, with honest stage/status and cancellation. Optional background enrichment should not block a page's complete publication when adequate metadata/media is already available.

## Next interview frontier

**Resolved by subsequent delegation:** the five questions below are retained as the research decision trail. Use [the delegated defaults](../2026-10-25-board-agent-default-policies.md) as the current design direction; do not ask this whole interview again. Specific exception actions and the existing first-use generated-image preview remain as recorded there.

1. **Google autonomy:** reuse the existing A$30 monthly pilot design allowance, or define a new allowance? Agree per-request generation/refinement limits and what happens when it is exhausted. Reservations remain estimates, not a guaranteed billing cap.
2. **Fallback route:** after no library match, prefer source-dependent routing—real-world photos from permitted web sources, charts from structured data, illustrations from Google—or a fixed order? Avoid running all routes merely to fill time.
3. **Chart truth:** when values are absent, ask/source factual data, or permit clearly marked illustrative data? Never silently present invented values as measurements.
4. **Enrichment privacy/cost:** permit Google description/embedding processing for newly created assets only, selected existing assets, or the whole library? Keep local-only/FTS functionality independently usable.
5. **Reusable web material:** agree acceptable source/licence/attribution policy for automatic import; current Commons acknowledgement is a manual boundary to replace deliberately, not bypass in code.

Shared understanding and implementation scope should be confirmed after these choices. This report creates no new paid-call, deployment or firmware authority.

## Evidence limits

Primary-source browsing, source inspection and one in-memory FTS5 feasibility probe only. No installed vector/embedding/memory packages, model downloads, library indexing, image upload, provider call, live Hermes run, deployment, sync, classroom trial or product source change occurred. Exact vendor versions/prices and account availability must be rechecked before implementation or purchase. The only repository write in this research is this report.
