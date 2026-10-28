# Diagnosis: Board images and uneditable settings in the unified desktop

28 October 2026. Examined `codex/companion-media-agent` at `04b1c49`.
Diagnosis only: application code, the user's settings and lesson were not changed.
Disposable local fixtures were used; no provider call, deployment or firmware write
was performed. Existing unrelated Graphify changes were preserved.

## Finding

The reported experience combines **a confirmed keyboard-focus regression in the
new desktop host**, **an unresolved configuration boundary between its two
workspaces**, and **a misleading error message**. Entering a Google key would not,
on its own, resolve the Board request.

The merge provides one teacher window, but retains a Qt Board process and a
separate Tk Voice process. Their provider configuration and resource stores remain
separate. This separation was deliberate in the integration plan; its consequences
are not adequately exposed in the interface.

## 1. Settings text fields lose keyboard focus when hosted

**Confirmed with the running application and a differential reproduction.**

The user reported that checkboxes respond, while the URL, token, provider-key and
allocation entries cannot receive text. The entries are ordinary editable
`ttk.Entry` widgets (`tools/compose/settings_panel.py:62` and `:84`). There is no
read-only setting on these fields.

In the running teacher window, clicking the empty private media-server URL entry
and sending the individual keys `d`, `o`, `g` left it blank. Accessibility continued
to report focus on the Qt `CompanionHost`, rather than an active Tk text entry.
Nothing was saved. A fresh standalone instance of the same `SettingsPanel`
accepted those same keys and displayed `dog`.

A disposable child process using the production `CompanionHost` embedding path
then narrowed the cause:

| Controlled variation | Result |
| --- | --- |
| Existing hosted application | Entry does not acquire usable keyboard focus. |
| Same SettingsPanel outside the Qt host | Entry accepts the same keystrokes. |
| Production host with only Qt `StrongFocus` added to the container | Entry still rejects the same keystrokes. |
| Production host with a child-side click handler calling the clicked Tk widget's `focus_force()` | Entry accepts and displays `dog`. |

The production host creates the foreign-window container at
`tools/compose/companion_host.py:247`. It has no explicit control-focus handover;
its refresh path remaps the Tk window. The probe measured the container's initial
focus policy as `NoFocus` (0), but changing this alone was insufficient.

This establishes a focus/activation failure at the Qt–Tk hosting boundary.
The successful click handler is diagnostic evidence and a repair direction,
**not a validated production fix**. A general forced-focus handler could affect
dropdowns, modal windows or external-document workflows and needs narrower design
and regression coverage. Qt itself documents platform-dependent activation and
focus limitations for [foreign window containers](https://doc.qt.io/qt-6/qwidget.html#createWindowContainer).

The minimal reproduction requires neither credential encryption nor an active
save, shutdown handshake, microphone or provider. Those mechanisms therefore do
not explain this reproduced text-entry failure.

## 2. Voice Settings do not configure the default Board

**Confirmed in source, the running launch command and offline execution.**

The running unified app was launched with `--companion-python` and without
`--board-settings-root`. The default launcher supplies no Board profile.

`create_board()` loads protected settings only when a Board settings root is
explicitly supplied (`tools/compose/unified_desktop.py:177`). Otherwise
`AgentPanel` defaults to `{'LOCAL_ONLY': True}`
(`tools/compose/board_agent_ui.py:53`). Its image preparer is local-only and its
external resource service is absent. Consequently:

1. The Voice Settings local-only checkbox can be clear while the Board is local-only.
2. Saving a Google key or enabling generation in Voice Settings does not change
   the default Board, including after an ordinary default relaunch.
3. Supplying an explicit saved Board profile loads it at launch, but later changes
   do not reconfigure the running Board.

A synthetic saved profile containing `LOCAL_ONLY=0` and `IMAGE_PROVIDER=gemini`
produced a non-local Board when explicitly selected. Editing that profile file
after construction left the running Board's configuration unchanged.

This is consistent with the written preservation contract, which deliberately
avoids silently enabling cloud work. It is nevertheless a product integration gap:
one window presents a Settings tab without clearly showing that it applies only
to Voice. The teacher cannot select/reload the Board profile through the shared UI.

The normal Windows feature profile exists, but at inspection it contained neither
`settings.json` nor `credentials.dpapi`. That does not establish that credentials
were lost: other profiles or environment configuration are distinct. No secret
values were printed or copied. The sandbox's redirected `LOCALAPPDATA` was ruled
out by inspecting the actual user-profile path explicitly.

## 3. The chart-data wording is misleading

**Confirmed without relying on a model's classification.**

An offline reproduction supplied a deterministic plan for a **dog illustration**,
then exercised the real default Board resource preparer. It returned:

> Supply chart data with units/source/date, or choose an available image.
> local-only mode blocks external acquisition

The pupil view was unchanged. The diagnostic command intentionally fails its
expectation that the dog image can be acquired, providing a repeatable red signal:

```powershell
& .local/teaching-board-renderer-env/Scripts/python.exe .local/diagnose_board_images_20261028.py
```

`tools/compose/board_runtime.py:202` prefixes **every** `teacher_choice` resource
decision with the chart-data instruction. That includes an image blocked by
local-only mode. This message does not demonstrate that the request was mistaken
for a chart, and supplying chart data cannot resolve this image block.

The local-only acquisition guard and unchanged pupil page behaved as intended.
The error should name the unavailable image route, show the effective Board
configuration and point to the relevant configuration control.

## 4. Image generation has further prerequisites

The current Board automatic illustration route is narrower than the Voice image
library. It requires the configured Google Gemini adapter, the supported exact
model, 1K output and an allocation of **1–50 AUD cents** per attempt. The shared
authenticated budget service must be configured and available. Local-only mode
must be off and paid generation enabled. A Google key alone does not satisfy these
conditions. The separate model used to classify and compose the Board request
also needs to be available.

The guards were reproduced through the real Board/MediaService path using local
fixtures and no provider:

| Fixture | Actual result |
| --- | --- |
| OpenAI producer selected | Unsupported size/aspect-ratio error: Board requests Google-style `1K` options. |
| Google selected, generation disabled | Image generation is disabled in current settings. |
| Google allocation absent | Positive estimate of no more than A$0.50 required. |
| Google allocation 100 cents | Same Board A$0.50 limit, despite the broader Settings form accepting this amount. |
| Google enabled with a 24-cent allocation, no budget client | Configure the shared budget server first. |

The OpenAI-size error is another reporting mismatch: the Board should explicitly
explain its Google requirement before preparing a job. The allocation form should
also expose the Board's stricter limit. These guards should be preserved while
the UI makes the prerequisites understandable.

Google credentials/model access, actual rendering, billing and live budget-service
readiness were **not tested**. No provider rejection has been established as the
cause of the reported local-only response.

## Verification and coverage gap

Fresh regression results, reported as separate suites:

| Suite | Result | Limit |
| --- | --- | --- |
| Board runtime, unified desktop and native host | 51 passed | A Windows COM exception diagnostic (`0x8001010d`) appeared during the native-host case; pytest continued and exited 0. This is not a clean native-stability claim. |
| Companion embedding/lifecycle | 18 passed | Synthetic state and focus-boundary checks. |
| Settings transitions and protected settings | 14 passed | Does not establish successful persistence of the user's current credentials. |

The first combined collection attempt failed because the Qt environment lacks
`win32gui` for companion-only imports. Splitting the suites across their existing
interpreters resolved collection; no dependency was installed.

The existing native-host test verifies ownership, visibility, resizing, tab return
and close handshakes. Its synthetic child contains a label and no editable entry.
The full application smoke likewise does not type into hosted controls. The
existing tests can therefore pass while the reported regression remains present.

## Recommended repair sequence

1. Repair child-control focus transfer. Add an actual hosted-entry test covering
   click/type, masked fields, paste, Tab/Shift+Tab, dropdowns, workspace return and
   switching away/back from another application. Verify Office destination guards
   still exclude both teacher and pupil windows.
2. Add explicit Board provider settings selection and reload to the shared UI.
   Show the active profile, effective local-only state and restart/reload status.
   Apply changes deliberately when Board work is idle; preserve pupil content and
   do not silently enable cloud work.
3. Replace the generic chart prefix with route-specific messages. Add one Board
   readiness view covering producer, key presence, allocation, budget service and
   composition provider, without exposing credentials.
4. Verify save/reopen and the intended Board request using fixtures, then validate
   real provider access and a separately authorised paid image request. Accept the
   preview before publishing generated content to pupils.

For temporary settings access, the existing standalone
`start_companion_feature.bat` avoids the native host. Close the shared application
before opening the same profile there. This only addresses settings entry; the
Board still needs explicit profile selection and its generation prerequisites.

The diagnostic scripts are clearly named under `.local/diagnose_*_20261028.py`.
Disposable windows were closed. No application fix, release, deployment or
physical/classroom acceptance is claimed by this report.
