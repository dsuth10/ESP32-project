# Image providers: Gemini first

24 October 2026. Implementation plan for `codex/companion-media-agent`, under
the [consolidated programme](2026-10-21-companion-media-agent-master-plan.md),
primarily M4 and the generated-image part of M5. Status: G1–G2 implemented and
verified offline, including frozen preparation metadata; see the
[implementation record](2026-10-24-image-provider-g1-g2-implementation.md).
No Gemini rendering adapter, real credential setup or paid trial is complete.

## Intended result

Choose an image producer, describe an image, generate it quickly, inspect the
preview, refine it, keep a named version and use the existing Paste Ready action
in Word or OneNote. Start with Google Nano Banana 2.1. Retain the OpenAI adapter
and make later producers additions to the same workflow.

Fast generation is a product priority alongside acceptable visual and teaching
quality. The quoted 4–11 seconds is a benchmark hypothesis, not a service promise.
Public leaderboard position is not an acceptance criterion for this application.

## Verified provider choice

Google currently lists **Nano Banana 2.1** as `gemini-nano-banana-2.1` and
recommends it for new projects. **Nano Banana 2** is the distinct
`gemini-3.1-flash-image` model. Keep the technical identifier separate from its
friendly label. See [Google's image guide](https://ai.google.dev/gemini-api/docs/image-generation)
and [2.1 model reference](https://ai.google.dev/gemini-api/docs/models/gemini-nano-banana-2.1).

Start with the Gemini Developer API and a Google AI Studio key, assuming that is
the key the user can obtain. Vertex AI would be a separate authentication and
deployment choice. Verify the account's model access before the paid trial.
Google explains project/key setup in its [API key guide](https://ai.google.dev/gemini-api/docs/api-key).

The current standard 2.1 pricing lists US$0.0336 for a 1K output image, plus
applicable input and text/thinking charges; image generation has no free API
tier. Recheck prices before spending. This is not an AUD invoice estimate.
[Google pricing](https://ai.google.dev/gemini-api/docs/pricing#gemini-nano-banana-2.1)

## Existing foundation and necessary changes

Local import, preview, naming and persistence have user acceptance. Image
insertion, undo/redo and save/reopen passed in Word and OneNote on the home setup.
These tests used synthetic imported images; real generated-image acceptance is
still open. See [home acceptance](2026-10-24-home-acceptance.md).

`media_service.py` currently constructs the OpenAI adapter directly. Settings
provides one image model and one OpenAI key. Prepared jobs do not freeze a
provider/model/options choice. Those are the main changes required; the library,
version lineage and Office insertion paths can be reused.

## Ordered delivery

| Step | Work | Completion evidence |
| --- | --- | --- |
| G1 | Introduce a small common image-provider interface and provider factory. Preserve OpenAI behaviour. Define capabilities for generation, reference-image editing, sizes and aspect ratios. | Offline tests prove routing, unsupported-option refusal and unchanged OpenAI operation. |
| G2 | Add Google settings and masked Windows-protected key storage. Add a visible provider/model choice and a ready/not-configured state. | Save/restart and configuration tests pass; keys never enter jobs, exports, sync or logs. |
| G3 | Implement the Gemini generation and single-reference refinement adapter against the current official API. | Recorded synthetic response fixtures cover successful images, refusals, malformed output and uncertain failures without paid calls. |
| G4 | Connect preparations, preview, job recovery, timing and spending allocations to the selected provider. | An offline complete workflow preserves versions, provider identity and exactly one dispatch. UI remains responsive. |
| G5 | Configure the user's key privately and verify model access; prepare the real budget service and a bounded pilot. | Setup does not generate an image. Account, model and allocation readiness are shown separately. |
| G6 | Run an explicitly authorised small home trial, then test generated-image insertion. | Actual images, timings, provider receipts and user quality/Office results recorded separately from automated tests. |
| G7 | Extend to other producers and complete home/work delivery. | Each adapter meets the same contract; private Linux deployment and two-host sync retain their existing acceptance gates. |

G1–G4 can proceed without a key or provider spend. G5–G6 depend on account access
and a separate paid-trial decision. No firmware change is needed.

## Provider contract and durable jobs

- Keep provider selection explicit. The text assistant remains Groq-primary;
  selecting Google images changes the image renderer only.
- Normalise requests into prompt, operation, optional selected parent version,
  provider, exact model and supported output options. Normalise results into
  validated image bytes/MIME, provenance, provider request identifier, usage and
  measured duration. Keep provider-specific parsing inside its adapter.
- Freeze provider/model/options/allocation with each prepared job. Changing
  Settings must not redirect an already prepared or dispatched attempt. Show
  the frozen choice beside Generate; a changed choice requires re-preparation.
- Keep existing OpenAI settings valid. Existing installations retain their
  configured provider; selecting Gemini is explicit. For undispatched legacy
  jobs without a snapshot, require re-preparation before a paid call.
- Preserve every saved image and canonical choice. Refinement produces a child
  version; it does not overwrite the parent. Allow explicit cross-provider
  refinement only when the selected destination supports image input, explaining
  that the selected image will be sent there.
- A timeout must never trigger a second request or an automatic switch to a
  different producer. Existing `needs_recovery` handling and held allocations
  remain in force. Local job identity is not proof of provider-side idempotency.

## Gemini adapter and first settings

Use the existing `requests` transport with the current documented Interactions
REST API, avoiding an additional SDK dependency for the initial adapter. Confirm
the payload and response schema against fixtures before implementation is closed.
Disable automatic POST retries, use explicit timeouts, refuse redirects and keep
credentials in the request header rather than the URL.

Decode only the final image output, validate its MIME, dimensions and bounded
bytes using the existing image checks, and retain actual returned provenance.
Interim thinking images and text-only/refusal responses must not become saved
final pictures. A success response without a usable image needs a clear outcome
and reconciliation; do not automatically repeat it.

Proposed defaults: Nano Banana 2.1, 1K output, one image per attempt and square
aspect ratio, with supported portrait/landscape choices. Put resolution and
thinking controls under advanced options. Compare `minimal` thinking with the
model's default `medium` before choosing the home preset; speed must not quietly
degrade teaching diagrams. The [model reference](https://ai.google.dev/gemini-api/docs/models/gemini-nano-banana-2.1)
documents these thinking levels and resolutions.

The [Interactions guide](https://ai.google.dev/gemini-api/docs/interactions-overview)
describes server-side storage as the default. Explicitly use `store=false` for
this initial workflow and send the selected parent image with each refinement,
without chaining cloud conversation state. This setting does not establish that
all provider operational retention is disabled. Web/search grounding stays off
for the first slice; it is a separate feature/cost decision.

## Teacher controls and feedback

Provide **Image producer** and **Model** choices, a masked **Google image API key**
field and an explicit **Check connection** action. Connection checking must not
call an image-generation endpoint. Show separate states for credentials/model
access, generation enabled and budget available; a listed model is not proof of
successful paid rendering.

Generate shows the chosen producer/model and conservative AUD allocation. While
running, show elapsed seconds and useful stages such as requesting image,
receiving image and preparing preview. Keep the app responsive. If the user
stops waiting, explain whether the request may still finish and be charged;
closing a local wait cannot promise remote cancellation or a refund.

The returned preview shows provider/model, duration and size. Keep naming,
refining and Paste Ready as separate actions. Continue using the tested Word
adapter and approved explicit OneNote Ctrl+V behaviour.

## Spending and data boundaries

Retain the existing budget reservation before dispatch and freeze allocations
for uncertain attempts. Use provider/model/size-specific conservative allocations;
distinguish them from returned usage and reconciled invoice costs. Keep the A$30
monthly design allowance unless the user changes it.

The shared Linux service is not deployed. For a separately approved single-PC
home pilot, the existing real authenticated server can run on loopback with
isolated data and its actual budget ledger; never replace it with a fake approval
or bypass the reservation check. Record that this pilot ledger does not coordinate
spend from another computer. Full release still requires the same deployed
private service and two-host acceptance in M1/M3. See the
[server guide](media-sync-server.md) and [deployment kit](companion-deployment.md).

Store the key through existing user-bound DPAPI protection; do not ask the user
to paste it into chat. Transmit only the deliberate image brief and selected
reference image. History, Office window titles, caret data and unrelated images
stay out of the provider request. Keep provider-specific conversation state
local and out of sync; audit the existing metadata allowlist before adding
provenance fields. Preserve the existing local-only prohibition on cloud calls.

## Test and pilot matrix

Offline tests cover provider selection, settings migration/secret masking,
frozen jobs, image validation, refusal/text-only output, quota/authentication
errors, timeout after dispatch, lost accounting acknowledgement, restart
recovery, no automatic fallback/retry, parent preservation and local-only mode.
Check the native app at 920 × 740 and 720 × 640. Re-run relevant writing,
library, packaging and Office insertion regressions after integration.

Proposed first paid pilot, subject to approval: at most **12 attempts** under a
separately agreed conservative total AUD allocation. Prepare eight generation
briefs (photorealistic Australian subjects, labelled water-cycle diagrams and
classroom illustrations), then four targeted edits. Allocate the cap and
per-attempt amounts after checking current pricing/account settings; reduce the
attempt count if needed. Stop at the first unresolved dispatch/accounting issue.

Measure provider round-trip and button-to-preview durations separately. Record
every success, refusal and failure with size, aspect ratio and thinking level.
Report the small pilot's median and full range; do not claim a reliable tail
latency percentile from so few samples. Assess realism, prompt adherence, correct
labels/arrows, edit preservation and teacher usability. Specifically report
whether 4–11 seconds was achieved rather than presenting it as assured.

Finally, use a kept generated image and a refined child in disposable Word and
OneNote material: one image per Paste Ready press, correct proportions, undo,
redo, save/reopen, and companion restart persistence. Native Google rendering,
physical insertion and later cross-location sync are separate acceptance results.

## Delivery and first action

Implement and test on the current companion branch with isolated feature data.
Preserve `main`, installed firmware, existing credentials and unrelated files.
Deliver a tested local commit and hash-verified private source preview before a
live pilot. A new provider failure must leave normal writing and cached images
usable. Disabling Gemini returns to the previous workflow without deleting its
saved images. No paid call, service deployment or remote push is authorised by
this planning document alone.

The first implementation slice is G1–G2: provider routing, compatible settings,
protected Google key entry and frozen job metadata, all verified offline.
