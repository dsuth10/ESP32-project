# Board image options and ordinary image requests

29 October 2026, `codex/companion-media-agent`. The user requested Google and
OpenAI with every existing supported output choice available to Board requests,
then reported that “Can you put an image of a horse up on the board?” failed
with “No supported reusable photo was found”.

## Behaviour

The Board now honours the saved image producer and output snapshot rather than
requiring Google/1K and overriding the resolution. Supported choices remain the
existing adapters' choices:

| Producer | Output choices |
| --- | --- |
| Google Gemini | 1K, 2K or 4K; 1:1, 3:4 or 4:3; minimal, medium or high thinking |
| OpenAI | 1024 × 1024; 1:1; high quality; saved model identifier |

Choose the producer/options in Voice Settings, save, then reload the selected
settings in Board settings. Each producer requires its own protected API key.
Readiness describes the selected producer, resolution, aspect ratio and
thinking/quality without contacting a provider or exposing credentials.
Explicitly naming a different producer explains the required settings change
before creating a job; no silent provider switch occurs.

The exact horse request previously entered the photo route, exhausted an empty
Commons result set and stopped before any image-generator call. A deterministic
parser now recognises ordinary single-image requests, extracts the subject and
uses illustration intent. It shares recognition with simple image placement,
avoiding a second model-generated command for an empty Board page. Complex
briefs retain the model planner, whose instructions now distinguish ordinary
pictures from explicitly requested photographs or factual visual evidence.

Saved images remain first choice. With no saved match, an ordinary image request
uses the selected generator once. Explicit photo/evidence requests retain one
reusable-photo search and never silently become synthetic evidence. Explicit
source requests and validated chart data retain their existing routes.

Generation enabled/local-only checks, immutable provider/output snapshots,
durable exclusive claims, account binding, uncertain-outcome recovery, no
automatic replay and first-use teacher preview remain. Uncapped mode retains
direct provider billing with no application spending cap. Capped mode uses the
existing image-service range of 1–3000 AUD cents for the selected producer and
resolution, with authenticated shared-ledger reservation before dispatch.
The previous Board-only A$0.50 restriction is removed.

## Validation

The exact horse repro failed with the reported reusable-photo error, then passed
after the routing repair. Fixtures assert one image-generator call, no Commons
search, saved-image reuse and retained photo/evidence restrictions.

The saved-settings UI workflow covers both spending modes for Google 1K/2K/4K
and OpenAI. It verifies transmitted output options, first-use preview before
publication, Undo/Redo, save/reopen and no replay. The combined focused runtime,
saved-settings and simple-image suites passed **52 tests**. The initial complete
provider/readiness/claim/settings workflow checkpoint passed **140 tests** before
the horse follow-up. Native Voice settings/media layout checks passed **18 tests,
1 skipped**.

The final broad Board/provider/media/unified-desktop run passed **750 tests,
6 skipped, 2 deselected**. The two deselected checks require junction creation
and loopback connections denied by this sandbox. The first broad invocation used
a temporary lesson root outside the required candidate directory, causing seven
additional fixture failures; using a candidate-contained temporary root resolved
all seven. The final eight saved-profile cases also passed with the real
production simple-image composer, not a replacement composition fixture.

These are local fixture/native checks. No paid image request, live provider-access
claim, deployment, physical/classroom acceptance or firmware write is included.
Existing private settings and credentials are unchanged. Restart an already-open
application to load the source changes; existing failed requests are not replayed.

## Follow-up: explicit generation and occupied page

The user's next report showed “Composition or required-resource validation
failed”. Read-only inspection of the running teacher window confirmed the exact
instruction “I need you to generate an image of a horse and put it up on the
board” and the error after 0.9 s. The shared library contained no generation job,
and no new Board recovery request had reached composition. The precise original
exception was hidden by the generic handler; a provider outage is not established.

The fixture replay of that exact wording reproduced the same message at the
resource-planning stage. The original simple-request grammar recognised placement
verbs but not generation plus placement, so it still called the model classifier.
The current lesson also contained existing ink and an image, which excluded the
empty-page-only deterministic compositor even after successful acquisition.

The shared parser now handles generate/create/draw/make plus optional placement
wording. Explicit generation bypasses saved-image reuse and requests one fresh
image from the configured producer. The deterministic compositor selects that
required new image rather than confusing it with existing page-image context.
On occupied pages, it proposes a complete image page; existing content remains
unchanged until the teacher accepts the whole-page replacement and first-use
preview. Undo restores the original page and its image/ink objects. Complex
briefs and ordinary edits of occupied pages keep their existing composition path.

Unexpected errors now identify resource planning, image acquisition, page
composition or page validation, without including raw provider exception text,
URLs or credentials.

The exact generation repro passed after failing before the change. The focused
controller/runtime/claims/settings/simple-image checkpoint passed **223 tests**.
The strengthened saved-profile workflow passed **24 cases**: both spending modes,
Google 1K/2K/4K and OpenAI, plain placement, explicit generation and explicit
generation over an occupied page. The production parser, compositor, validator,
preview and Undo/Redo/save/reopen paths run without a text-model fixture producing
commands. Fresh-generation versus saved reuse, private-error redaction and five
generation phrasings also have focused regressions. No live paid image call was
submitted during these checks.

Final broad regression: **776 passed, 6 skipped, 2 deselected**. The same two
junction/loopback permission-dependent checks remain excluded. A separate live
Google model-metadata GET with the existing protected key succeeded; no image
was requested, so paid rendering and image quality remain unverified.

The running application completed its normal Save and close handshake and was
reopened through the feature launcher with the same lesson and saved feature
profile. Native inspection confirmed the original dog image and ink remained,
the Board was Ready with configured services, and the exact horse instruction
was restored in the request field. It was left unsent for the user's live retest;
no existing task was replayed and no paid request was submitted.
