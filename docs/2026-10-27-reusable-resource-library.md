# Reusable resource library: local search and curation

27 October 2026. Authorised follow-up on `codex/companion-media-agent`, under
the [programme](2026-10-21-companion-media-agent-master-plan.md) and
[Board agent build plan](2026-10-25-teaching-board-agent-build-plan.md).

## Delivery plan and ownership

Three sub-agents work in parallel, with coordinator-owned integration:

| Slice | Owner | Reviewable outcome |
| --- | --- | --- |
| Catalogue and search | Catalogue worker | Durable teacher corrections, pinned remembered names, filtered lexical search and matching reasons; persistence and safety tests |
| Teacher library controls | UI worker | Topic/year/type/approval filters, editable details, remember/forget controls, thumbnails and explanations; native fixture checks |
| Search quality | Evaluation worker | Fixed synthetic classroom requests, declared relevant versions and negatives, repeatable quality/timing report |
| Integration and review | Coordinator | Source replay, exact-version reuse, portable round trips, regression suite, usage/evidence documentation and independent worker review |

Dependencies: agree catalogue APIs first; workers implement against those APIs;
then integrate native controls, source ingestion and portable lessons; finally run
the combined regression selection and inspect the native layout. No live provider,
handheld or paid operation is needed for this slice.

## Behaviour and data contract

- Edit a selected version's title, description, tags, topics and year levels.
  Corrections live in a separate local SQLite table. Original resource IDs,
  immutable source metadata, hashes, media bytes and review state remain intact.
  Reopening, source replay and index rebuilding retain corrections.
- Remember a phrase such as **our usual water-cycle diagram** for one chosen
  exact version. Saving the same name again moves that binding explicitly.
  Forget removes the name while retaining the resource. A remembered draft,
  rejected version or missing image never becomes approved through naming.
- Search corrected metadata and original aliases. Exact identities, remembered
  names, titles and aliases precede lexical matches. Common request filler is
  ignored; lexical candidates rank by matched query terms and weighted local
  FTS relevance. This is deterministic lexical retrieval, with no embeddings.
- Filter by topic, Prep/Years 1–12, resource type and approval state before the
  result limit. Topic matching is case-insensitive exact membership; multiple
  values in a facet are alternatives, with different facets combined.
  Use the explicit year filter: year wording in free text is not a facet.
- Results show matching reasons, review/availability, remembered names and
  verified local image thumbnails. Metadata matching does not establish visual
  correctness. Non-image catalogue entries do not establish media playback.
- Ordinary reuse hides rejected/excluded/unavailable resources. Explicit review
  filters allow library management; such selections cannot be submitted for reuse.
  Automatic image selection still requires one exact approved choice and verified
  local bytes. Broader lexical suggestions require teacher selection.
- Portable lessons carry corrections separately from immutable source fields for
  included dependencies. Incoming corrections initialise newly imported versions;
  existing local corrections/review decisions win on repeated catalogue import.
  Remembered names stay in the local library and do not silently rebind another
  installation. Catalogue sync is outside this slice.
- Supplied chart data defines a deterministic rendering operation; broad image
  suggestions do not block that chart or substitute other numerical values.

## Try the candidate

Launch using the [candidate guide](2026-10-25-teaching-board-agent-candidate.md).
In the teacher side panel, use **Search** with optional filters, select a result,
then **Edit details…**, **Remember name…** or **Forget name…**.
Search remains local, including when protected remote settings are configured.

Use a disposable lesson to check: correct a diagram title/tags, assign a phrase,
reopen the candidate, search that phrase, inspect reasons/thumbnail, approve only
after reviewing the resource, and reuse it. Save and reopen the lesson and check
that its pinned image did not change when names or metadata changed. Repeat with
an older approved version and a newer draft to verify the intended choice.

## Verification and remaining gates

The final integrated local selection passed **536 tests, with one optional
pdfplumber extraction skip, in 38.67 s**. This selection includes catalogue,
curation, native teacher UI, Board model/session/runtime/recovery/export,
media-service and provider-routing regressions. Counts from worker runs overlap
and are not added. Existing disposable Windows junction-safety checks passed
outside the sandbox; the sandbox-only attempt could not create the junctions.
No path guard was disabled. `git diff --check` passed for the changed source/docs.

```powershell
$boardTestPaths = @(rg --files tools/compose/tests | Where-Object { $_ -match 'test_board_.*\.py$' })
& .local/teaching-board-renderer-env/Scripts/python.exe -m pytest @boardTestPaths tools/compose/tests/test_media_service.py tools/compose/tests/test_image_provider_routing.py -q -rs --tb=short --basetemp .local/teaching-board-candidate/pytest-library-final-verified
```

An independent catalogue worker reviewed integration and caught explicit-empty
facet export and private-correction export-validation cases; both were fixed
with round-trip/failure tests. A separate quality worker checked the measurement
denominators and automatic-selection boundaries, and found uppercase UUID search
compatibility; that was corrected and covered. Type-filtered exact lookup also
preserves image selection when a non-image has the same ordinary alias, while
an explicit remembered name never falls back to a different version or type.

The synthetic native teacher-window capture was visually inspected:
`.local/teaching-board-candidate/library-search-evidence/teacher-library-search.png`.
It shows readable filters, matching reasons, thumbnail, remembered name and edit
actions in the scrolling side panel. The capture registered the installed Segoe
UI font because the offscreen process initially had no enumerated fonts. This is
native fixture evidence, not physical pen/touch/display or teacher acceptance.

The
[search-quality report](2026-10-27-resource-library-search-quality.md) owns
request-level metrics, negatives and known lexical gaps. These fixtures are not
teacher relevance judgements, real-library scale measurements or classroom
acceptance. Gather teacher judgements before expanding beyond lexical search.

Deployment, two-installation sync, physical application/classroom acceptance and
the wider programme gates remain open. This work does not publish a release.
