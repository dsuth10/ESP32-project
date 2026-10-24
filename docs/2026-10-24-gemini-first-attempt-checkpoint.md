# First real Gemini attempt: rejected request and diagnostic correction

24 October 2026. Follow-up to [G3–G4](2026-10-24-image-provider-g3-g4-implementation.md)
and the [provider plan](2026-10-24-gemini-image-provider-plan.md). This is a failed
live acceptance result, not a successful generated-image release. Subsequent
authorised diagnosis resolved the rejection and completed the bounded trial;
see the [live-trial follow-up](2026-10-24-gemini-live-trial.md). The paused and
disabled states below describe this earlier checkpoint.

## Real setup and attempt

The user entered their key privately and confirmed successful Google model
metadata access. The key remains in user-bound Windows-protected storage.
The separately approved home-PC ledger runs the actual authenticated server on
loopback with the A$30 monthly design allowance. Missing/incorrect credentials
were refused. A one-cent reservation/release probe restored the full allowance.
This single-PC service does not establish Linux deployment or two-host acceptance.

The user explicitly approved the proposed paid trial, bounded to at most twelve
attempts. The bookkeeping allocation was reduced to 20 AUD cents per 1K attempt
after clarifying that an allocation is not an expected provider charge. The first
native Generate action used the reviewed kookaburra brief, exact model
`gemini-nano-banana-2.1`, 1K square output and medium thinking.

- Exactly one provider dispatch occurred.
- Google returned **HTTP 400** after **1.319 seconds**; no usable image was returned.
- The job entered `needs_recovery`. No retry, fallback or second dispatch occurred.
- The trial stopped at its agreed unresolved-dispatch gate. Generation was disabled
  again through Settings.
- The actual ledger retains **20 cents held**, with **A$29.80 available**. This is
  not evidence of a Google charge. No usage or invoice result established a cost.
- There is no image-generation latency, quality, refinement or generated-image
  Office acceptance result to report from this failed request.

Private job identity, exact request, receipt and trial state remain in `.local`.
No credential or account/project identity is included in this record.

## Established diagnostic defect

The adapter's non-success branch raised before reading the provider error body.
It retained the HTTP status but discarded the detail needed to explain the 400.
The original error body cannot be recovered from that local receipt. No specific
request field, billing condition or model restriction has been established as the
cause of the live rejection.

Offline regression tests reproduced the missing-diagnostics defect before the fix.
The corrected path reads at most 64 KiB of an error response and retains:

- Known RPC status, numeric error code and bounded reason identifiers.
- Validated request-field names from structured field violations or recognised
  unknown-name messages.
- A summary limited to 500 characters, with the key, full brief, paths, URLs,
  long encoded strings and bearer values redacted before persistence.

It does not retain a raw response body, arbitrary detail descriptions, metadata
maps or thought state. Diagnostics stay in local job receipts and remain outside
the existing sync allowlist. Unreadable/oversized errors still fail safely. The
fix does not retry, release an uncertain allocation or switch models/producers.
It improves observability; it does **not** claim to fix the original HTTP 400.

## Offline request-contract check

The public [Google Interactions OpenAPI schema](https://ai.google.dev/static/api/interactions.openapi.json)
was downloaded without credentials for offline validation. Its generated
`ResponseFormat.oneOf` contains a generic unrestricted object that overlaps the
documented image alternative. Strict generic validation therefore rejects both
known image objects and the generic alternative together; that overlap is not
evidence of the live HTTP cause.

Selecting the documented `ImageResponseFormat` branch validates the actual first
request. Deliberate unsupported size/thinking mutations fail. No request-field
change or second generation call was made from that check. Fixture references to
`delivery` demonstrate diagnostics only; they do not identify the live rejection.

## Verification and delivery

The focused provider/service/diagnostic selection passed **61 tests** after the
red/green checks. The final offline regression selection passed **325 tests**, with
one skip because Windows symlink creation was unavailable. It covers companion,
provider, settings, Office adapter fixtures, loopback service/budget and packaging
checks. No new native layout code was changed in this correction.
Native inspection confirmed generation disabled following the failure. No second
live request was used to verify the diagnostic change.

The new code requires a companion restart before a subsequent diagnostic attempt.
The original held job/receipt must remain intact. Any controlled follow-up uses a
new counted attempt within the authorised maximum; it must not replay the old job.
The trial is paused pending resolution or a specific decision to take a diagnostic
attempt. Provider invoice reconciliation, teacher quality review and physical
Word/OneNote acceptance remain open.
