# Image generation without a spending cap

28 October 2026. The user explicitly requested image generation using their saved
Google API key and no spending cap. This supersedes the pilot spending allowance
for their selected feature profile.

Voice Settings now includes **No spending cap**, saved as
`IMAGE_SPENDING_UNCAPPED`. It defaults off for other profiles. When enabled,
generation uses provider billing directly and needs neither a per-attempt
allocation nor the shared budget server. Private media sync remains independent.
Board illustrations retain their Google/1K output choice and first-use preview.

Prepared jobs freeze the spending mode. Changing modes requires preparing a new
job. Uncapped jobs record direct provider billing rather than a zero-cost claim.
They retain exclusive durable claims, provider receipts, uncertain-outcome
recovery and no automatic replay. Board attempts bind their recovery identity to
the provider/key fingerprint in uncapped mode; existing capped receipts retain
their original shared-service binding. No keys enter receipts or exports.

The existing feature profile now has Google selected, generation enabled,
uncapped spending enabled and local-only mode off. The exact protected credential
file was preserved. The Board remembers the same feature profile for its next
launch. The public settings were backed up privately under `.local/` before the
change. No unresolved default-lesson Board image attempts were present.

Validation:

- Provider, spending, durable jobs, Board acquisition, saved-profile end-to-end
  preview/Undo/Redo/reopen, settings persistence and recovery: **211 passed,
  1 skipped** in the Board interpreter.
- Native settings and media layouts: **8 passed** in the Voice interpreter.
- Settings transition guards: **7 passed** in the Voice interpreter.
- Live Google model-metadata check: passed using the saved protected key. This
  was a metadata GET; no paid image request was made.

An initial combined test invocation used the Board interpreter for native Voice
tests and could not import `win32gui`. Those tests passed in their owning Voice
interpreter. The new uncapped regression initially used the wrong receipt
filename; correcting the fixture to match its request identity resolved it.

During the initial settings change, Computer Use timed out waiting for app
access, so the user window was left open pending a normal close/reopen.

## Follow-up: dog request blocked by local-only Board

The user's subsequent dog-image request hit the exact local-only resource error.
The live Board showed **local-only · no saved provider profile**, while the saved
feature profile had generation and uncapped spending enabled, with local-only
off. Selecting saved Voice Settings changed the live Board to configured
services, but that process still displayed the older disabled-generation/shared
budget prerequisites. Thus the earlier saved configuration had not completed the
handover to the active Board. Its process had started after the public-settings
write; simply assuming a restart had applied those settings was insufficient.

The normal loader and unified `create_board` path were replayed against the real
protected profile in a disposable offscreen lesson. Both loaded generation=1,
uncapped=1 and local-only=0, without provider calls. No general startup-code defect
or precise reason for the old process's differing view was established.

The application was closed through its normal **Save and close** handshake and
reopened with the same feature profile explicitly selected for both workspaces.
Live Board settings then confirmed **Google Gemini, 1K, no application spending
cap**, and the Board returned to **Ready · requested tasks use configured
services**. The lesson remained saved. The profile selection was also persisted.
The exact local-dog-error regression passed; the saved-profile image workflow and
uncapped/recovery tests passed again (**10 passed**). No paid dog request was
submitted or automatically replayed during diagnosis.

Deployment, live image rendering/quality/billing, physical application and
classroom acceptance remain separate; these checks do not close those gates.
