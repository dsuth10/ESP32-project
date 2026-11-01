# Monitor shortcut / OneNote focus: project integration options

> Read-only investigation, 1 November 2026. Current programme status remains governed by the [consolidated branch plan](../2026-10-21-companion-media-agent-master-plan.md). This note does not approve firmware writes, unlock registration or close physical/classroom gates.

## Recommendation

Implement **open/focus OneNote onto a teacher-named monitor as a Windows companion desktop action first**, with durable monitor identity and an audited receipt. Wire it to a companion UI control and an optional keyboard chord that the existing `HotkeyState` / BLE HID path can later carry. Do **not** start with firmware `ACTION_HOST_COMMAND`, Wi-Fi host commands, OneNote page navigation or a new device page.

That order matches how Create & Paste already works: the handheld only emits HID keys; Windows owns semantics, focus guards and Office behaviour. BLE cannot choose a monitor. The historical [OneNote automation plan](../ESP32_Classroom_Companion_OneNote_Automation_Plan.md) correctly proposed host-side window/monitor management, but that protocol is still design-only. A desktop-first slice can ship without a flash; a dedicated Create & Paste button remains a separately approved firmware trial.

## What exists today

### Device → Windows shortcut path

| Layer | Role | Primary paths |
| --- | --- | --- |
| Firmware profiles | Compile-time pages/buttons | `src/macropad_config.h`, `src/macropad_config.cpp` |
| Macro execution | BLE HID only | `src/main.cpp` → `executeMacro()` |
| USB serial | Display feedback + page switch command; not an action bus | `tools/compose/device_feedback.py`; firmware `page N` handling in `src/main.cpp` |
| Windows hotkey poller | Edge detection for five modes | `tools/compose/hotkey_state.py` |
| Companion routing | Record / paste / open library | `tools/compose/compose_gui.py` → `_handle_hardware_event` |
| Tray companion (legacy path) | F13–F15 style handlers | `tools/compose/compose_companion.py` |

Firmware action types (`macropad_config.h`): `ACTION_MEDIA`, `ACTION_KEY_COMBO`, `ACTION_STRING`, `ACTION_VOICE`. There is **no** implemented `ACTION_HOST_COMMAND`.

Create & Paste is zero-based page index 6 (`PAGE_COMPOSE`), shown as device page 7/8. Buttons (`macropad_config.cpp`):

| Button | HID | Windows mode (`HotkeyState`) | Companion behaviour |
| --- | --- | --- | --- |
| COMPOSE | `KEY_F13` | `compose` (`0x7C` / chord `0x78` = F9) | Start/stop writing recording |
| DICTATE | `KEY_F14` | `dictate` (`0x7D` / `0x79`) | Start/stop dictation |
| IMAGES | `KEY_F16` | `media` (`0x7F` / `0x77`) | Image-request recording |
| LIBRARY | `KEY_F17` | `library` (`0x80` / `0x76`) | One-shot: select Image library tab / show workspace |
| PASTE READY | `KEY_F15` | `paste` (`0x7E` / `0x7A`) on **release** | Inject queued text/image |
| (empty sixth slot) | — | — | Unused in profile `numButtons = 5` |

Fallback chords are Ctrl+Alt+Shift with F9 / F10 / F11 / F8 / F7 respectively (`compose_gui.py` help text; [device trial](../2026-10-24-create-paste-device-trial.md)). Hardware inputs default off in feature profiles via `ESP32_ENABLE_HOTKEYS` (`compose.env.example`, `settings_panel.py`).

Other pages remain ordinary HID macros (media keys, productivity chords, Windows tools, Custom Keys, Hermes hold-to-talk). Custom Keys can send arbitrary chords, but as [build-guide](../build-guide.md) and [README](../../README.md) state, Bluetooth does not identify a OneNote page or move a window between monitors.

### Focus, Office and monitors already in the app

- **Document focus restore:** `tools/compose/focus_tracker.py` — snapshot HWND/title/pid; `restore_focus` with `AttachThreadInput` / `SetForegroundWindow`; refuses companion/teacher/pupil internal PIDs. Used so Compose/Dictate UI can return to the last external document; automatic paste never restores a window the teacher left.
- **OneNote image insertion (not open/place):** `tools/compose/media_targets.py` — foreground must be `ONENOTE.EXE`; canvas class `OneNote::DocumentCanvas`; explicit Paste Ready may allow Ctrl+V when selection UIA is unavailable; background OneNote insertion remains restricted. Receipts report paste requested, not saved embedding.
- **Pupil display monitor choice (Teaching Board only):** `tools/compose/board_candidate.py` — `QGuiApplication.screens()`, combo “Display N”, `setScreen` + move to `geometry().topLeft()`. Useful pattern for enumeration/move, not a OneNote provider and not durable across unplug/DPI changes without further work ([renderer research](2026-10-25-teaching-board-renderer-options.md)).
- **Status HUD:** `tools/compose/status_overlay.py` positions on the **primary** display only and deliberately avoids stealing focus.
- **USB feedback:** identity-bound, display-only states; handshake expects `page7-v1`; after link writes `page 7\n`. Does not dispatch host automation (`device_feedback.py`).

### Programme and prior design constraints

- M7 ([master plan](../2026-10-21-companion-media-agent-master-plan.md)): Create & Paste + USB feedback exist; **general runtime profile editing remains design**.
- Earlier research already noted firmware-constant shortcuts and no runtime profile protocol ([Hermes orchestration investigation](2026-10-21-hermes-orchestration-investigation.md)).
- Historical plan sections 2–7 (`docs/ESP32_Classroom_Companion_OneNote_Automation_Plan.md`) propose `ACTION_HOST_COMMAND`, Wi-Fi semantic commands, named monitors and OneNote navigation. **None of that host-command path is present in current application/firmware sources reviewed for this note.**

## Practical integration options

| Option | Mechanism | Pros | Cons / constraints |
| --- | --- | --- | --- |
| **A. Desktop action + UI (recommended first)** | New host helper: resolve named monitor → find/launch desktop OneNote → move/maximise → `SetForegroundWindow` with existing focus discipline | No flash; testable with stubs; aligns with “Windows owns semantics” | No handheld button until a HID route is added |
| **B. Desktop action + new HotkeyState mode** | e.g. F18 / Ctrl+Alt+Shift+F6 chord only until firmware matches | Keeps BLE transport model; reuses poller | Needs companion config; physical button still needs firmware trial |
| **C. Firmware sixth Create & Paste button → F18** | Fill empty slot with `ACTION_KEY_COMBO` `KEY_F18`; extend `HotkeyState` | Matches Library one-shot UX | **Scoped S3 trial + recovery**; layout/gesture tests; does not itself place windows |
| **D. Remap Custom Keys / Windows Tools** | e.g. Win+… or media Calculator-style | Small firmware edit pattern already documented | Still cannot target a monitor; fragile Start-menu launch |
| **E. Full `ACTION_HOST_COMMAND` + Wi-Fi** | Historical plan | Deterministic multi-step scenes | Large protocol/security/M7 surface; blocked until design is productised |

**Recommended path:** A → optional B → C only after explicit device approval. Keep OneNote **open/focus/monitor** separate from **Paste Ready insertion** permissions so a focus action cannot silently grant clipboard paste.

### Desktop action design sketch (not implemented)

1. Persist teacher-named monitor roles (e.g. `classroom_display`) with a stable key (prefer EDID/device instance path + bounds hash; fall back to bounds+DPI with an explicit “confirm remap” when the set changes). Avoid relying only on volatile “Display 2” indices.
2. On invoke: enumerate monitors; resolve role; locate `ONENOTE.EXE` top-level window(s) or launch the desktop app via a configured, allowlisted path/URI; move with Win32 placement (`SetWindowPos` / monitor work area); restore/maximise; foreground with the same attach/restore care as `FocusTracker`.
3. Emit a local receipt: monitor role, hwnd, whether launched or reused, success/failure. Refuse ambiguous multi-window cases with a clear teacher message rather than guessing.
4. Do **not** navigate notebooks/pages in the first slice; do **not** use Office COM for placement if HWND + process identity suffice.
5. Settings live with existing companion config/DPAPI patterns (`companion_settings.py`); feature hardware inputs remain opt-in.

## Tests (proposed once implemented)

Local engineering only; do not claim classroom acceptance from stubs.

- Unit: monitor role resolution; remap when displays change; refuse missing role.
- Unit: OneNote find vs launch; refuse non-desktop / wrong process; multi-instance ambiguity.
- Unit: placement moves into target work area; maximise optional; no crash if hwnd dies mid-flight.
- Focus regression: action must not mark companion as an insert target; Paste Ready / `media_targets` keyboard permission still requires explicit paste gesture and canvas checks (`tests/test_media_targets.py`, `tools/compose/tests/test_media_gui_integration.py` patterns).
- Hotkey: new mode edges coalesce extended/fallback keys like existing modes (`tools/compose/tests/test_compose.py`, `test_device_feedback.py`).
- Firmware (only with trial authority): gesture non-repeat for one-shot button; BLE disconnect; layout compile assertions as in the page 7 trial record.

## Gaps

- No host semantic command channel from the ESP32.
- No durable monitor identity store for Office windows.
- No open/focus/place OneNote API in `media_targets.py` or companion UI.
- Runtime button/profile schema and authenticated device config still design-only (M7).
- Teaching Board pupil `Display N` selector is not shared infrastructure and is index-based.
- Wireless return feedback and broader physical Create & Paste acceptance remain open ([device trial](../2026-10-24-create-paste-device-trial.md)).

## Device approval boundaries

| Change | Boundary |
| --- | --- |
| Desktop-only open/focus/monitor helper + settings + tests | Application work on the companion branch; no flash; preserve unrelated edits |
| New HID key / Create & Paste sixth button / page layout | Explicit user approval, verified 16 MiB recovery, scoped `tools/board_trial.py` route per [board upload safety](../board-upload-safety.md); stable registry stays write-locked |
| Editing identities/fingerprints to pass a guard | Forbidden; investigate refusals |
| USB feedback carrying executable host commands | Out of current contract (display-only; BLE remains action transport) |
| Assistant “fix device / add shortcut” via model shell | Already refused; use typed, reviewed app changes ([README](../../README.md), master-plan rule 8) |
| Claiming M5/M7/classroom done from this research | Not permitted; separate physical/Office acceptance |

The board currently runs the approved page 7 application trial; further firmware writes need their own scoped authorisation. Prefer proving the Windows placement path on disposable OneNote windows before requesting another flash.
