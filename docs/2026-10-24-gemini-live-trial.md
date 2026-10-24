# Gemini home trial: generation and refinement working

24 October 2026. Follow-up to the [first rejected request](2026-10-24-gemini-first-attempt-checkpoint.md)
and [provider plan](2026-10-24-gemini-image-provider-plan.md). The user explicitly
authorised the paid trial, then authorised controlled diagnosis, fixes and new
attempts without stopping for approval after each error. The maximum remained
twelve attempts, including failures, at a 20 AUD cent design allocation each.

## Failure and correction

The original request returned HTTP 400 and its error body was discarded by the
old adapter. That original detail remains unavailable. After the diagnostic
correction, a separate deliberate request returned HTTP 400 with:

> Image delivery mode is not supported.

The request explicitly supplied `response_format.delivery=inline`. Google's
published OpenAPI enum lists that value, but the actual endpoint rejected it.
The current [image-generation examples](https://ai.google.dev/gemini-api/docs/image-generation)
omit the delivery field. Removing **only that field** produced the first real
saved image. Ten consecutive requests using the corrected adapter succeeded.
JPEG MIME, model, size, aspect ratio and thinking configuration were preserved.
The parser still requires validated inline bytes; URI-only results are rejected
without fetching a URL. No automatic retry or producer fallback was added.

A service-level regression first reproduced the live rejection for generation;
after the correction it verifies generation followed by single-parent refinement.
The transport fixture deliberately rejects any explicit delivery field. Other
existing tests retain the refusal, timeout, multiple-image and URI-only guards.

## Actual twelve-attempt result

All outputs were 1024 × 1024 JPEG images using `gemini-nano-banana-2.1`, square
aspect ratio, stateless requests and no search grounding. Six original images
and four single-reference edits were saved. Two comparison cases were dropped
to make room for diagnosis within the original attempt limit.

| Attempt | Thinking | HTTP | Provider round trip |
| --- | --- | --- | --- |
| Original kookaburra request | medium | 400 | 1.319 s |
| Diagnostic kookaburra request | medium | 400 | 0.879 s |
| Corrected kookaburra generation | medium | 200 | 15.460 s |
| Kookaburra background edit | medium | 200 | 15.435 s |
| Labelled water cycle | medium | 200 | 28.937 s |
| Water-cycle arrow edit | medium | 200 | 15.104 s |
| Fraction illustration | medium | 200 | 14.216 s |
| Kangaroo generation, native Generate button | medium | 200 | 15.336 s |
| Kangaroo branch addition | medium | 200 | 13.414 s |
| Kookaburra comparison | minimal | 200 | 10.825 s |
| Fraction comparison | minimal | 200 | 9.557 s |
| Fraction colour edit | medium | 200 | 13.278 s |

Successful provider requests: **median 14.660 s; range 9.557–28.937 s**. The native
Generate action painted its preview in **15.481 s**, separately from its 15.336 s
provider time. The other nine successes used a private bounded harness calling
the same actual MediaService, provider and authenticated ledger; they do not
have native button-to-preview timings. Two minimal-thinking samples reached the
proposed 4–11 second range. This does not establish a reliable latency target,
tail percentile or a general quality-equivalent speed advantage. Medium remains
the home preset pending teacher review.

## Visual inspection and accounting

Agent inspection found plausible Australian wildlife photographs, four correctly
spelt water-cycle labels, and a circle with four equal quarters and one red
quarter. The targeted edits changed the sky, added a branch, made arrows blue,
and changed the fraction quarter to blue while retaining the requested subject
and layout. These are candidate-quality observations, not teacher or classroom
acceptance. Edits are regenerated images and are not pixel-identical outside
their requested change. All four parent versions remain independently saved.

The real home ledger reports **A$27.60 available** from its A$30 monthly design
allowance. Ten successful allocations retain A$2.00; the two failed attempts
still hold A$0.40. Total unavailable allocation is **A$2.40**, not A$2.80: the
held amount is included in `spent_or_uncertain`, not added to it. Allocations
are not Google's invoice. No provider invoice or final AUD cost is established,
and the failed holds were neither released nor presented as confirmed charges.

## Durable evidence and recovery

Exact job identities, safe provider receipts, numeric token usage, request
settings, source fingerprints, timings, ledger snapshots and authorisation
records remain private in `.local`. Append-only JSONL events accompany a readable
audit and materialised trial state. Original proposal/checkpoint snapshots are
preserved. Keys remain in Windows user-bound protected settings and are excluded
from logs and source previews. Raw provider bodies and thought content are not
logged.

After the trial, a verified media backup was restored into a new private folder.
All twelve generation/refinement jobs matched the originals, all ten saved
versions passed SHA-256 checks, and each refinement retained its parent. Protected
settings and a consistent SQLite ledger snapshot were preserved separately.

## Verification and remaining acceptance

- Focused provider/diagnostic tests: **52 passed**.
- Companion/provider/service/packaging regression: **326 passed, one skipped**
  because Windows symlink creation was unavailable.
- Actual native Generate, asynchronous progress and painted preview passed.
- The local home app loads the corrected adapter with generation enabled and
  the same isolated library and protected key. A private one-click launcher
  reuses the configured ledger identity; it makes no provider request on launch.

The first cold-launch check exposed a separate launcher error: SyncClient wraps
connection failures in SyncError, while the new private launcher caught the raw
requests exception. The user saw the resulting error dialog. A focused test
reproduced the failure. The corrected launcher recognises the wrapped connection
cause, starts a missing ledger, and still refuses authentication errors rather
than creating another server. Three private launcher tests passed, covering
absent ledger, existing authenticated ledger and authentication refusal. A real
fresh launch then started exactly one ledger and one companion, with the same
library and clean runtime error logs. This is process restart evidence, not a
Windows reboot test. Launcher failures now also have safe durable event records.

The general Word/OneNote path has earlier [home acceptance](2026-10-24-home-acceptance.md).
This trial does not establish physical handheld insertion, undo/redo and
save/reopen **of these newly generated versions**. Teacher content review,
provider invoice reconciliation, Windows reboot, Linux deployment, two-host
sync and classroom acceptance remain separate gates. Installed firmware,
registration, stable `main`, public publishing and remote Git delivery are
unchanged by this trial.
