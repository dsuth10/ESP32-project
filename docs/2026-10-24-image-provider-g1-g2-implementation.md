# Image producers: first offline implementation slice

24 October 2026. Local implementation on `codex/companion-media-agent`, under
[the provider plan](2026-10-24-gemini-image-provider-plan.md), G1–G2 and the
prepared-job groundwork for G4. Gemini rendering is not implemented in this
slice. Account setup, model-access checking and paid evaluation remain open.

## Changes

- Added an image-provider protocol, factory and capability registry for generation,
  reference images, sizes and aspect ratios. OpenAI retains its existing model
  setting, square 1024 × 1024 output, high quality, endpoints and single dispatch.
  Unsupported producers/options fail before reservation or HTTP dispatch.
- Existing installations default to OpenAI. Settings offers an explicit Google
  choice, separate exact model identifiers and a masked Google image API key.
  Google defaults to `gemini-nano-banana-2.1`. Its declared capabilities describe
  the planned adapter; the UI clearly shows rendering as pending and disables
  its Generate button. It does not silently route to OpenAI.
- The Google key uses the existing user-bound Windows DPAPI transaction. It is
  excluded from plaintext environment-file loading and process overrides. Saving
  or switching producers retains the existing OpenAI key/model and all images.
- Settings reports credential configuration, unchecked model access, adapter
  availability, generation policy and unverified budget availability separately.
  No connection check or provider request runs during setup. An explicit metadata
  connection-check action remains for the next integration/setup work.
- Preparations persist schema, provider, exact model, validated options and AUD
  allocation in local job fields. They remain visible beside Generate. Selection,
  model or allocation changes require re-preparation; legacy preparations without
  a snapshot are refused before reservation. Missing reference images also fail
  before reservation instead of becoming unreferenced generation. No database
  schema change is needed.
- Existing timeout, held-allocation, restart and lost-accounting-acknowledgement
  handling remains in use. No automatic fallback or retry was added. Refinement
  into another supported producer requires confirmation that the selected image
  will be sent there; parent versions and canonical choices remain intact.
- The sync source allowlist remains unchanged (`url`, `creator`, `licence`,
  `attribution`, `provider`, `model`). Snapshots, requests, jobs and credentials
  do not enter sync. The existing private library backup still contains local
  prompts/jobs, as its UI states; credentials remain in separate protected storage.
- Wrapped Settings labels and arranged image actions across two rows so controls
  remain accessible at the minimum supported width.

The model identifier and distinction from Nano Banana 2 were checked against
[Google's model reference](https://ai.google.dev/gemini-api/docs/models/gemini-nano-banana-2.1).
The future metadata check can use the documented
[Models GET endpoint](https://ai.google.dev/api/models#method:-models.get);
this slice makes no such request.

## Local verification

All image inputs, keys and provider responses used for verification were synthetic.
No real provider/account calls, Office documents or registered boards were used.

- First integrated companion/provider/settings/package run: **251 passed,
  2 skipped**. This preceded the final additional layout/Office/portable checks.
- Final non-GUI selection (companion tests, provider and Office adapter fixtures,
  source/package lifecycle and portable service): **270 passed, 1 skipped, 1
  failed**. The failure was Windows access denied while renaming a disposable
  backup folder; its isolated end-to-end rerun passed (**1 passed**). The skip
  was unavailable Windows symlink creation for an archive rejection test.
- Separate native layouts and History library: **9 passed, 1 skipped**. The
  existing Hermes 920 × 740 case skipped because Tcl could not load a resource;
  that case passed alone (**1 passed, 1 deselected**). The four new image/settings
  checks all passed at 920 × 740 and 720 × 640.
- A combined native/threaded-server run terminated during Windows Tk garbage
  collection. The final groups above were deliberately run in separate processes.
  This remains a limitation of the combined Windows test run, not a clean all-in-one
  suite result.
- Real Windows DPAPI save/reload passed using synthetic Google and OpenAI keys
  in isolated `.local` data. Neither key appeared as plaintext in the resulting
  settings or protected file. Native panel screenshots were visually reviewed;
  a clipped-label issue was corrected before the final checks.
- After adding the two documentation files to the preview allowlist, packaging
  checks passed again (**17 passed, 3 skipped** under the filesystem sandbox;
  symlink/junction creation was unavailable there).
- The final routing/service/provider selection passed **45 tests**, including
  the added missing-parent guard and unchanged OpenAI HTTP payload check.

The final non-GUI command was:

```powershell
python -m pytest tools/compose/tests tests/test_media_providers.py tests/test_media_targets.py tests/test_preview_package.py tests/test_companion_package.py server/tests/test_media_server_portable.py --ignore=tools/compose/tests/test_image_provider_layout.py --ignore=tools/compose/tests/test_hermes_layout.py --ignore=tools/compose/tests/test_library_panel.py -q -rs --basetemp=.local/pytest-google-g1g2-20261024-d --tb=short
```

Its single failure was rerun with `tools/compose/tests/test_media_end_to_end.py`
and a fresh isolated base directory. Native checks used the three excluded files
in a separate process, then the skipped Hermes case with `-k 920` in a fresh one.

## Delivery and remaining gates

The source-preview builder includes this record and the provider plan. It verifies
every packaged source hash. The archive, integrity manifest, synthetic data and
screenshots stay private in `.local/`; no installer or running application is
updated by building it.

Next: G3 Gemini Interactions adapter and synthetic schema fixtures, then the rest
of G4 preview/recovery/timing integration. G5 actual account/model access and
ledger readiness, G6 separately authorised paid quality/Office trial and G7
cross-location delivery remain open. Current Google settings do not establish
account access or paid rendering success. No firmware change, service deployment,
remote push or physical/classroom acceptance is part of this slice.
