# Gemini rendering and workflow: offline implementation

24 October 2026. G3–G4 candidate on `codex/companion-media-agent`, following
[G1–G2](2026-10-24-image-provider-g1-g2-implementation.md) and the
[provider plan](2026-10-24-gemini-image-provider-plan.md). Real account access,
paid generation, teaching quality and physical generated-image insertion are
not verified by this work.

## Provider and request boundary

`tools/compose/gemini_images.py` implements generation and one selected reference
image through the documented Interactions REST endpoint. It uses a header key,
explicit timeouts, disabled POST retries, refused redirects and bounded response
reading. Requests explicitly disable storage, background execution and streaming.
No previous interaction ID, conversation, History, target-document metadata,
grounding tool or unrelated image is supplied. A reference is validated locally
and included with each refinement; no cloud conversation is resumed.

The parser requires completion and one final image in the last model-output step.
It ignores thought summaries, refuses multiple final images and never downloads
an output URI. Base64, actual MIME, complete image decoding, 20 MiB and
25 megapixel limits are checked with the existing library validator. The actual
returned model is retained rather than inferred from the requested model.

These choices were checked against Google's current
[image guide](https://ai.google.dev/gemini-api/docs/image-generation),
[Interactions overview](https://ai.google.dev/gemini-api/docs/interactions-overview)
and [OpenAPI schema](https://ai.google.dev/static/api/interactions.openapi.json).
The fixture module records constructed schema examples, including an intentionally
small blue PNG. It is not a recording from a real Google account. `store=false`
does not establish that all provider operational retention is disabled.

## Workflow and spending

- Gemini is an explicit factory route. OpenAI keeps its existing model/key,
  endpoints and request payload, with the shared stage/receipt contract added.
  It also uses the common complete-image validation. No failure switches producer.
- Google supports the bounded square, portrait and landscape choices already
  declared by G1. Resolution (1K/2K/4K) and thinking level (minimal/medium/high)
  are under Advanced Google image options. Medium remains the default; no speed
  or teaching-quality comparison has been made.
- Each resolution of the single supported exact Google model has a separately
  entered conservative AUD allocation. Empty means unconfigured. Google never
  borrows the legacy OpenAI allocation or another resolution's allocation. No
  cost preset, exchange rate or invoice amount was invented. The shared server's
  A$30 monthly design allowance remains unchanged.
- Prepared provider/model/options/allocation and preparation settings survive
  restart. A change to output settings or allocation requires re-preparation.
  Existing default OpenAI preparations remain compatible; old Google preparations
  using only the generic allocation need a new explicit Google allocation and
  re-preparation.
- An atomic SQLite claim protects each job across companion instances, in addition
  to the per-service lock. A rejected competing claim cannot overwrite the active
  attempt. This is local dispatch protection, not provider-side idempotency.
- Reservation and uncertain marking still precede dispatch. Timeout, malformed,
  refusal/text-only, incomplete and HTTP error results retain a safe local receipt
  and the held allocation for reconciliation. A lost accounting acknowledgement
  leaves the saved image available. No uncertain attempt is automatically repeated.
  Review offers an explicit accounting-only reconciliation action for a saved
  image with a lost acknowledgement; the same allocation is committed idempotently
  without another reservation or image request.
- Local receipts retain safe provider/model identifiers, HTTP status, request and
  interaction IDs where returned, numeric usage counters, output dimensions/MIME
  and measured duration. Raw response text and thought state are not retained.
  Invoice costs remain separate from allocation and token counters.
- Provider round trip, service workflow and button-to-painted-preview durations
  are measured separately. Tk runs background work through the existing UI queue;
  elapsed seconds and stages remain visible while waiting. The notice explains
  that closing the app does not cancel the remote request or release its allocation.
- The preview shows producer/model, dimensions and available local timings.
  Receipt lookup uses the existing operation identity. Receipts, usage, timings,
  jobs and prompts stay local; sync still sends only the established version/source
  allowlist. A second desktop receives images and provider/model provenance without
  receiving local attempt records. Existing private backups still include local
  jobs/prompts, but do not include protected credentials.

## Configuration check

Settings has an explicit **Check Google connection (no image)** action. Its only
provider call is an authenticated, bounded model-metadata GET. Startup and saving
settings do not invoke it. Local-only mode blocks it before transport. Changing
settings during checking invalidates the displayed result; saving waits for the
check to finish. A successful metadata response explicitly leaves paid rendering
and budget availability unverified. No real connection check was performed here.

## Local verification

All provider transports and keys used here are synthetic; the loopback budget/sync fixtures
exercise the actual authenticated application server and ledger code in temporary
data. They do not deploy a service or approve a pilot allocation.

- Final non-GUI regression selection: **320 passed, 1 skipped**. It includes the
  companion writing/History/settings suites, both image producers, Office adapter
  fixtures, two-desktop loopback library/budget tests, portable server and package
  lifecycle checks. The skip is unavailable Windows symlink creation in an archive
  rejection test.
- The **six image/settings native cases passed**, each in a fresh process, covering
  both supported sizes, key masking, save/action reachability and asynchronous
  rendering/timing. A preceding grouped native run had a Tcl-resource skip; the
  fresh-process checks remove that ambiguity for these six cases.
- Native History library regression: **4 passed** in a separate process.
- Focused accounting/provider/service/loopback verification: **58 passed** before
  the final regression selection. The Google loopback case deliberately commits
  the real reservation and loses its acknowledgement, then proves explicit
  reconciliation retains one 100-cent synthetic allocation and one image dispatch.
- Python compilation and scoped Git whitespace checks passed.

Final regression command:

```powershell
python -m pytest tools/compose/tests tests/test_media_providers.py tests/test_media_targets.py tests/test_preview_package.py tests/test_companion_package.py server/tests/test_media_server_portable.py --ignore=tools/compose/tests/test_image_provider_layout.py --ignore=tools/compose/tests/test_hermes_layout.py --ignore=tools/compose/tests/test_library_panel.py -q -rs --basetemp=.local/pytest-gemini-release-candidate --tb=short
```

Native cases used `tools/compose/tests/test_image_provider_layout.py` with one
size/case selected per process; History used `test_library_panel.py` separately.
Counts describe distinct selections/checkpoints and should not be added into a
claim of a single all-in-one run.

The native full-app smoke ran at **920 × 740** and **720 × 640**, with isolated
`.local` data, synthetic provider and microphone, hardware inputs disabled and a
guard refusing every real HTTP request. A synthetic result was saved and shown
with producer/model/timing details. Screenshots were visually reviewed. The first
full-app check exposed a squeezed preview at minimum height; compact controls and
hiding completed preparation details fixed it. Native checks also caught a
closed-image error introduced during editing; it was fixed before delivery.

The automated responsiveness check holds a synthetic provider POST open, confirms
that a Tk heartbeat and elapsed/stage display continue, then checks the final
preview, stored timings and absence of automatic insertion. Separate native
processes avoid the previously observed mixed Tk/threaded-server cleanup issue.

## Delivery and remaining gates

The allowlisted private source preview includes this record, current provider plan,
adapter and synthetic tests. Building it verifies every packaged source hash.
Local evidence/screenshots remain in `.local/gemini-g3g4/`; they are not bundled.
The generated Graphify outputs present before this work are left outside the
implementation commit, as are unrelated enclosure files.

Next is G5: privately enter the user's key, explicitly check model access, prepare
the actual authenticated budget service and agree a bounded home pilot. Then G6
needs separate paid-trial authority, real images/receipts, latency and teaching
quality review, and physical Word/OneNote insertion. Synthetic timings establish
no 4–11 second service claim. M1/M3 deployment, two-host cross-location acceptance,
firmware, classroom and public-release gates remain open. Nothing in this slice
pushes remotely, deploys a service, changes installed firmware or updates an
installed companion release.
