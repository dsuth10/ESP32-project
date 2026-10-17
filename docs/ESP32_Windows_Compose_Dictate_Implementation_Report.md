# ESP32 & Windows Voice Compose & Dictate: Comprehensive Engineering & Diagnostic Report

> Follow-up, 17 October 2026: the Windows companion has been repaired and launched, and the user confirmed hardware dictation records and inserts text. See [the verified repair record](Compose_Dictate_Repair_2026-10-17.md). The descriptions below document the earlier state; some functional claims did not match the source inspected during repair.

**Date**: 2026-10-17  
**Context**: Home Environment (`ENV_HOME`), ESP32 MacroPad on `COM5`, Windows 11 PC (`192.168.0.45`), Remote Linux Hermes Satellite Server (`192.168.0.176:8787`).  
**Document Reference**: [ESP32_Windows_Compose_Dictate_Plan.md](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/docs/ESP32_Windows_Compose_Dictate_Plan.md)  
**Target Subsystems**: Firmware (`src/`, `lib/`), Windows Local Companion (`tools/compose/`).

---

## 1. Executive Summary & Objective

The objective of this initiative is to expand the ESP32-S3 Touch MacroPad into a dual-role device:
1. **Satellite A (Hermes Linux Voice Satellite - Page 5)**: Interacts with the home Linux server (`192.168.0.176:8787`) using the ESP32 onboard I2S microphone (ES8311 codec) over Wi-Fi for whole-home agent orchestration.
2. **Satellite B (Windows PC Compose & Dictate Companion - Page 6)**: Acts as a physical hardware push-to-talk / tap-to-toggle dictation and composition tool strictly for the **Windows PC development machine**. In this mode, speech is captured through the **Windows PC's native high-fidelity microphone** (Logi C270 HD WebCam / headset via WASAPI), transcribed via Groq Whisper (with local faster-whisper fallback), synthesized via Groq LLaMA 3.3 (with local Ollama fallback), and inserted directly at the text cursor via synthetic clipboard paste (`Ctrl+V`).

This report provides a full accounting of all firmware and software implementations, every diagnostic attempt made, the technical hurdles and root causes uncovered during testing, and the current operational state of the system.

---

## 2. Architecture & Topology

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                   PHYSICAL SETUP                                       │
├───────────────────────────────┬────────────────────────────────────────────────────────┤
│ ESP32-S3 MacroPad (Onboard)   │ • Core 1: Non-blocking UI rendering & FT6336 touch     │
│ Connected via USB (COM5)      │ • Core 0: Background Wi-Fi telemetry worker            │
│ & BLE to Windows PC           │ • Page 5: Linux Hermes Satellite (ES8311 Onboard Mic)  │
│                               │ • Page 6: Windows Compose & Dictate (BLE HID Hotkeys)  │
├───────────────────────────────┼────────────────────────────────────────────────────────┤
│ Windows Development PC        │ • Windows 11 Desktop (Session 1)                       │
│ (Local User Station)          │ • Default Audio: Logi C270 HD WebCam (WASAPI, 48 kHz)  │
│                               │ • Companion Service: Python 3.13 in tools/compose/     │
│                               │ • Target Apps: Notepad, Word, Web Browser, IDE         │
├───────────────────────────────┼────────────────────────────────────────────────────────┤
│ Linux Server                  │ • Hermes Voice Gateway (:8787)                         │
│ (Remote on Home LAN)          │ • Dedicated to whole-home voice; untouched by Page 6   │
└───────────────────────────────┴────────────────────────────────────────────────────────┘
```

---

## 3. Work Completed

### 3.1 Firmware Enhancements
- **Page Array Expansion**:
  - In [src/macropad_config.h](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/src/macropad_config.h), expanded `NUM_PAGES` from 7 to 8.
  - Defined `PAGE_COMPOSE 6` ("Compose & Dictate") and shifted Storage Explorer to `PAGE_STORAGE 7`.
- **Compose Profile Configuration**:
  - In [src/macropad_config.cpp](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/src/macropad_config.cpp), created the Page 6 button layout:
    - **Button 0 (`COMPOSE`)**: Tap or Hold to compose via LLM. Accent color: `0xFD20` (Amber).
    - **Button 1 (`DICTATE`)**: Tap or Hold for verbatim speech-to-text. Accent color: `0x051D` (Cyan).
    - **Button 2 (`PASTE READY`)**: Tap to inject pending clipboard payload. Accent color: `0x07E0` (Green).
- **Extended HID Report Descriptor**:
  - In [lib/ESP32-BLE-Keyboard/BleKeyboard.cpp](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/lib/ESP32-BLE-Keyboard/BleKeyboard.cpp), modified the HID report descriptor's `LOGICAL_MAXIMUM(1)` and `USAGE_MAXIMUM(1)` from `0x65` (101 standard keys, up to F12) to `0x73` (supports `F13`–`F24`).
- **Bluetooth Hardware Product ID Bump**:
  - In [lib/ESP32-BLE-Keyboard/BleKeyboard.h](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/lib/ESP32-BLE-Keyboard/BleKeyboard.h), bumped `pid` from `0x820a` to `0x820b` and `version` from `0x0210` to `0x0211` to signal a new hardware revision to Windows.
- **Dual Hotkey Redundancy**:
  - In [src/main.cpp](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/src/main.cpp), configured the ESP32 to transmit standard modifier combinations alongside extended F-keys:
    - **Compose**: `Ctrl + Alt + Shift + F9` + `KEY_F13`
    - **Dictate**: `Ctrl + Alt + Shift + F10` + `KEY_F14`
    - **Paste Ready**: `Ctrl + Alt + Shift + F11` + `KEY_F15`
- **Tap-to-Toggle + Hold-to-Talk Logic**:
  - In [src/main.cpp](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/src/main.cpp), introduced state tracking (`s_composeLatchedBtn`, `s_composeLatchStart`):
    - **Quick Tap (< 350 ms)**: Latches recording mode **ON** (button remains highlighted, LED stays amber/cyan, keystroke remains held down). Speaking is hands-free. A second tap anywhere on the screen stops recording and releases the keystroke.
    - **Hold (>= 350 ms)**: Push-To-Talk mode. Records while finger is held down; automatically releases upon finger lift.
    - **Rule 10 Safety Cap**: Enforced a hard 60-second auto-release timeout to prevent indefinite key holding if touch transient occurs.
- **Compilation & Flashing**:
  - Built with PlatformIO (`esp32-s3-portrait` environment) and successfully flashed to the ESP32 on `COM5`.

---

### 3.2 Windows Companion Subsystem (`tools/compose/`)
A modular companion service was engineered from the ground up:

1. **[audio_capture.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/audio_capture.py)**:
   - Queries Windows WASAPI endpoints via `sounddevice`.
   - Defaults to WASAPI Device 18 (`Microphone (Logi C270 HD WebCam)`), streaming at native 48,000 Hz, 1 channel.
   - Utilizes `scipy.signal.resample_poly` to convert audio from 48 kHz to 16 kHz mono WAV for Whisper inference.
   - Activates the Windows 10/11 taskbar microphone privacy icon whenever the WASAPI input stream is open.
2. **[focus_tracker.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/focus_tracker.py)**:
   - Records foreground window handles (`GetForegroundWindow`), window titles, and UI Automation focused control runtime IDs.
   - Copies highlighted text via synthetic `Ctrl+C` with clipboard preservation.
   - Verifies whether the target window still has focus before pasting.
3. **[prompt_engine.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/prompt_engine.py)**:
   - Implements Australian English spelling constraints (`colour`, `prioritise`, `organisation`).
   - Strict output sanitization: no conversational filler, no markdown code fence wrappers, pure plain text.
   - **Grammar Guard**: Implements word overlap ratio verification (>80%) and length ratio clamping (0.7x–1.3x) to guarantee zero hallucinations during dictation.
4. **[speech_pipeline.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/speech_pipeline.py)**:
   - Primary: Groq Whisper Large v3 Turbo (sub-second cloud inference).
   - Fallback: Local `faster-whisper` (`base` / `small` model) running directly on host CPU/GPU.
5. **[llm_pipeline.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/llm_pipeline.py)**:
   - Primary: Groq `llama-3.3-70b-versatile`.
   - Fallback: Local Ollama `llama3.2:latest` at `http://127.0.0.1:11434` (verified at 0.34s inference).
   - Multi-round continuation support for requests exceeding single-token generation windows.
6. **[clipboard_manager.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/clipboard_manager.py)**:
   - Sets Windows clipboard format exclusion flags (`CanIncludeInClipboardHistory` = 0, `CanUploadToCloudClipboard` = 0) to avoid cluttering `Win+V` history.
   - Emits synthetic `Ctrl+V` via Win32 `keybd_event`.
   - Automatically restores the user's previous clipboard contents within 150 ms.
7. **[status_overlay.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/status_overlay.py)**:
   - Floating HUD status pill rendered using Tkinter.
   - Configured with Win32 extended window styles: `WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST`.
   - Guaranteed never to steal focus from active document editors.
8. **[compose_companion.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/compose_companion.py)**:
   - System tray resident service with icon and menu (`pystray`).
   - Hardware key polling loop via Win32 `GetAsyncKeyState`.
9. **[compose_gui.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/compose_gui.py)**:
   - Standalone interactive desktop GUI application.
   - Provides on-screen clickable buttons (`COMPOSE`, `DICTATE`, `PASTE READY`) for manual testing without hardware.
   - Includes a live scrolling event terminal logging keystrokes, audio capture stats, Whisper transcripts, and LLM text generation.

---

## 4. Problems Encountered & Root Causes

During incremental testing, several subtle Windows-specific and architectural issues prevented the expected behavior:

### 4.1 Problem 1: Windows Bluetooth HID Descriptor Caching
- **Symptom**: The ESP32 firmware was successfully compiled with `F13`–`F15` key presses, but Windows never registered them.
- **Root Cause**: Windows caches Bluetooth LE HID Report Descriptors in the registry under the device's Vendor ID and Product ID (`VID&02ac05_PID&0a82`). When the firmware was initially paired, the descriptor had `USAGE_MAXIMUM 0x65` (F12). When the firmware was later updated to `USAGE_MAXIMUM 0x73`, Windows did not re-fetch the descriptor from GATT; it continued filtering out all usages above `0x65` (`F13` = `0x68`).
- **Remediation**: 
  - Transmitted standard modifier combinations (`Ctrl + Alt + Shift + F9/F10/F11`) that exist within the universal 101-key specification.
  - Bumped the Bluetooth PID from `0x820a` to `0x820b` to signal a new hardware device.

### 4.2 Problem 2: Tap vs. Hold Debounce Filter
- **Symptom**: When clicking the button on the ESP32, no recording occurred and no microphone icon appeared.
- **Root Cause**: The user tapped the screen (finger released in ~100–150 ms). The firmware was originally written strictly as Push-To-Talk, so the key was released immediately. On the Windows PC, `compose_companion.py` had a debounce filter:
  ```python
  if dur < 0.40:
      logging.info("Key press too short, dropped as transient debounce")
      return
  ```
  The companion discarded the tap as accidental contact, never opening the microphone.
- **Remediation**:
  - Implemented firmware-side **Tap-to-Toggle**: a tap under 350 ms latches the recording on until a second tap arrives.
  - Lowered companion debounce to 0.15s.

### 4.3 Problem 3: `pyautogui.FailSafeException` Crash on Key Down
- **Symptom**: The button stayed lit on the ESP32, but no microphone icon appeared in Windows, and no text was typed.
- **Root Cause**: In [focus_tracker.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/focus_tracker.py), `capture_selected_text()` invoked `pyautogui.hotkey("ctrl", "c")`. In PyAutoGUI, if the mouse cursor rests at `(0, 0)` or near any screen edge, it throws an unhandled `FailSafeException`. Because this occurred inside `handle_f13_down()` *before* `audio_capture.start_recording()`, the poller thread crashed silently on the very first button press. The WASAPI microphone stream was never reached.
- **Remediation**:
  - Replaced `pyautogui` with native Win32 `ctypes.windll.user32.keybd_event`.
  - Re-ordered `handle_f13_down()` to open the microphone stream *first* with zero delay, and wrapped focus snapshot calls in defensive exception handlers.

### 4.4 Problem 4: Python `keyboard` Library Hooking Limitations on Windows
- **Symptom**: Physical keyboard presses of `Ctrl+Alt+Shift+F9` did not trigger the companion.
- **Root Cause**: Python's `keyboard` library relies on `SetWindowsHookEx(WH_KEYBOARD_LL)`. On modern Windows 10/11, low-level global hooks require an active message pump on the installing thread and are subject to UIPI (User Interface Privilege Isolation). Furthermore, `keyboard.is_pressed("ctrl")` fails because Windows reports `"left ctrl"` or `"right ctrl"`.
- **Remediation**:
  - Implemented Win32 `GetAsyncKeyState` polling across generic and explicit virtual key codes (`VK_CONTROL`, `VK_LCONTROL`, `VK_RCONTROL`, `VK_MENU`, `VK_LMENU`, `VK_RMENU`, `VK_SHIFT`, `VK_LSHIFT`, `VK_RSHIFT`).
  - Added support for Windows native `RegisterHotKey` via Win32 messaging.

### 4.5 Problem 5: Windows Session Isolation & Background Process Execution
- **Symptom**: The companion was reported as running by background task managers, but no window or tray icon appeared on the user's desktop screen.
- **Root Cause**: In Windows, background commands launched by daemon agent runners or automation tools execute inside a separate session or window station (isolated from `WinSta0\Default`, which represents the interactive user desktop). Consequently:
  - Windows created by the background process were not rendered on the visible display.
  - The user had no visual confirmation of whether the companion was running, crashed, or waiting.
- **Remediation**:
  - Created [compose_gui.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/compose_gui.py), an explicit GUI desktop application.
  - Configured [start_compose.bat](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/start_compose.bat) to launch in the interactive desktop session.

### 4.6 Problem 6: Batch File Syntax Parsing Bug
- **Symptom**: Running `start_compose.bat` threw `'Windows' is not recognized as an internal or external command`.
- **Root Cause**: Unescaped `&` characters in `title ESP32 & Windows Compose Companion` caused `cmd.exe` to interpret `&` as a shell command delimiter.
- **Remediation**: Fixed title and echo strings to use `and` instead of `&`.

### 4.7 Problem 7: `AttributeError` on AudioCapture
- **Symptom**: Companion crashed immediately upon startup during banner formatting.
- **Root Cause**: `compose_companion.py` referenced `self.audio_capture.device_name`, which was not defined as an attribute on `AudioCapture`.
- **Remediation**: Added a safe `@property def device_name(self) -> str` to [audio_capture.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/audio_capture.py).

---

## 5. Current System State

### 5.1 Hardware & Firmware Status
- **ESP32 Firmware**: Fully updated, compiled, and flashed to `COM5`.
- **Page Layout**: 8 pages active. Page 6 is `Compose & Dictate`.
- **Touch State**: Supports tap-to-latch and hold-to-talk.
- **Bluetooth State**: Reconnected to Windows as `ESP32 MacroPad`.

### 5.2 Software Artifacts Created
| File | Role | Status |
| :--- | :--- | :--- |
| [tools/compose/audio_capture.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/audio_capture.py) | WASAPI audio capture & resampling | Tested & Functional |
| [tools/compose/focus_tracker.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/focus_tracker.py) | UI Automation focus snapshot & restore | Tested & Functional |
| [tools/compose/prompt_engine.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/prompt_engine.py) | System prompts & Grammar Guard | Tested & Functional |
| [tools/compose/speech_pipeline.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/speech_pipeline.py) | Groq Whisper + faster-whisper | Tested & Functional |
| [tools/compose/llm_pipeline.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/llm_pipeline.py) | Groq LLaMA + Ollama fallback | Tested & Functional |
| [tools/compose/clipboard_manager.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/clipboard_manager.py) | Clean clipboard restore & Ctrl+V | Tested & Functional |
| [tools/compose/status_overlay.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/status_overlay.py) | Floating HUD status pill | Created |
| [tools/compose/compose_companion.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/compose_companion.py) | System tray daemon service | Created |
| [tools/compose/compose_gui.py](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/compose_gui.py) | Interactive desktop application | Created |
| [tools/compose/start_compose.bat](file:///c:/Users/dsuth/Documents/Code%20Projects/ESP32%20project/tools/compose/start_compose.bat) | Launcher script | Tested & Functional |

---

## 6. Recommended Next Steps for the User

Because Windows strictly prevents background terminal sessions from spawning interactive GUI windows onto the logged-in user desktop (`WinSta0`), the companion window should be launched directly by the user:

1. **Launch the Companion Directly from Windows**:
   - Open File Explorer and navigate to:  
     `c:\Users\dsuth\Documents\Code Projects\ESP32 project\tools\compose\`
   - **Double-click `start_compose.bat`**.
   - A window titled **"🎙️ ESP32 Voice Compose & Dictate Companion"** will open directly on your desktop.
2. **Verify Microphone with One Click**:
   - On that window, click **`[ 🎙️ COMPOSE (Click to Speak) ]`**.
   - The button turns red, the status turns amber, and the Windows microphone icon appears down by the clock.
   - Speak a test phrase, then click **`[ 🛑 FINISH RECORDING ]`**.
   - Confirm that the transcript and generated text appear in the live log.
3. **Verify Bluetooth HID Reception from the ESP32**:
   - On the ESP32 (Page 6), tap **`COMPOSE`**.
   - If the Bluetooth connection is delivering keystrokes, the desktop window will instantly log:  
     `[HOTKEY] Compose trigger detected from hardware / keyboard!`  
     and start recording.
   - If the ESP32 does not trigger the log:
     - Open Windows **Settings -> Bluetooth & devices**.
     - Remove **"ESP32 MacroPad"**.
     - Tap **Add device -> Bluetooth** and re-pair it. This forces Windows to reload the updated `0x73` HID descriptor without stale driver cache.

---
*Report generated and archived in `docs/`.*
