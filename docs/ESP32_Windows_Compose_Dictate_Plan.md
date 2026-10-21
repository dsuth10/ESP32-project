# ESP32 & Windows Compose / Dictate Companion: Architecture & Implementation Plan

> Historical design, investigation or checkpoint evidence. Current scope/status is governed by the [consolidated branch programme](2026-10-21-companion-media-agent-master-plan.md): original S3 only, CYD application port abandoned, Groq primary and the same Linux Hermes over permanent private Tailscale required at home/work. Earlier proposals and test observations below are not proof of current deployment or release acceptance.

> **Project Concept**: Douglas Idea (12 Oct 2026)  
> **Status**: Queued after Phase 28 / Item #13 Field Test  
> **Target Environments**: School / Work (Windows PC) & Home (Windows PC + Linux Hermes Server)  
> **Acceptance Apps**: OneNote Desktop, OneNote for Windows 10, Word Desktop (M365), Word for the Web, Google Chrome

---

## 1. Executive Summary

This specification defines a dual-mode **Voice Compose & Dictate** extension for the ESP32 MacroPad and Windows PC.

By holding a dedicated button on the ESP32, users capture speech through high-fidelity PC microphones, transcribe and process it using high-speed Groq inference (with local Whisper & Ollama fallback), and insert the resulting plain text directly at the cursor via the Windows clipboard and synthetic `Ctrl+V`.

```text
 ┌──────────────────────┐         BLE HID Hotkey (F13/F14/F15)        ┌───────────────────────────────┐
 │ ESP32-S3 MacroPad    │ ───────────────────────────────────────────► │ Windows Background Companion  │
 │ • Dedicated Page 7   │                                              │ • Python tray service         │
 │ • COMPOSE (Hold F13) │                                              │ • WASAPI / sounddevice PC Mic │
 │ • DICTATE (Hold F14) │                                              │ • UI Automation focus lock    │
 │ • PASTE   (Tap F15)  │                                              │ • Floating non-focus status   │
 └──────────────────────┘                                              └──────────────┬────────────────┘
                                                                                      │
                                                                   Audio Stream       │ Groq API (fallback: Local)
                                                                                      ▼
                                                                       ┌───────────────────────────────┐
                                                                       │ STT: Groq Whisper-v3-Turbo    │
                                                                       │ LLM: Groq / Local Ollama      │
                                                                       └──────────────┬────────────────┘
                                                                                      │ Clean plain text
                                                                                      ▼
                                                                       ┌───────────────────────────────┐
                                                                       │ Target Application at Cursor  │
                                                                       │ (Word, OneNote, Chrome, etc.) │
                                                                       └───────────────────────────────┘
```

### Key Differentiators & Invariants
1. **Zero Network Latency on Trigger**: The ESP32 triggers recording purely via BLE HID scan codes (`F13`–`F15`). No Wi-Fi or HTTP handshake is required to start/stop dictation.
2. **PC-Grade Microphone Fidelity**: Eliminates 16kHz embedded I2S mic bandwidth bottlenecks, Wi-Fi audio packet drops, and room reverb.
3. **Target Window & Focus Integrity**: Captures Windows UI Automation control handles. Only auto-pastes if the original window and focus target remain identical. If focus changes, text is safely queued as `READY`.
4. **Clipboard Cleanliness**: Restores the user's prior clipboard within 150ms of pasting. Suppresses Windows Clipboard History (`Win+V`) and cloud sync monitors.
5. **No Hallucinations / Strict Grammar Guard**: Dictate mode strictly verifies transcript-to-output word overlap (>80%) to prevent models from inventing content.

---

## 2. Firmware Extension (ESP32-S3)

### 2.1 Page Allocation & Layout
Firmware expands from `NUM_PAGES = 7` to `NUM_PAGES = 8`.
- Page 0: `Dashboard` (System status)
- Page 1: `Media & Audio`
- Page 2: `Productivity`
- Page 3: `Windows Tools`
- Page 4: `Custom Keys`
- Page 5: `Hermes Voice` (ES8311 mic -> Voice Receiver `:8787`)
- **Page 6 (Index 6): `Compose & Dictate` (New dedicated profile)**
- Page 7 (Index 7): `Storage Explorer` (SD card file browser)

### 2.2 Button Configuration (`src/macropad_config.cpp`)
Page 6 utilizes a 3-button layout with large ergonomic touch targets:

```cpp
// Page 6: Compose & Dictate
{
  "Compose & Dictate",
  0xFD20, // Amber / Warm Orange accent
  3,      // 3 large buttons
  {
    // Button 0: COMPOSE (Hold F13)
    { "COMPOSE", "Hold: Speak Request", 0x3186, 0xFD20, ACTION_KEY_COMBO, nullptr, 0, 0, 0, KEY_F13, nullptr },
    // Button 1: DICTATE (Hold F14)
    { "DICTATE", "Hold: Verbatim Text", 0x1A28, 0x051D, ACTION_KEY_COMBO, nullptr, 0, 0, 0, KEY_F14, nullptr },
    // Button 2: PASTE READY (Tap F15)
    { "PASTE READY", "Tap: Paste Pending", 0x1245, 0x07E0, ACTION_KEY_COMBO, nullptr, 0, 0, 0, KEY_F15, nullptr },
    { "", "", 0, 0, ACTION_MEDIA, nullptr, 0, 0, 0, 0, nullptr },
    { "", "", 0, 0, ACTION_MEDIA, nullptr, 0, 0, 0, 0, nullptr },
    { "", "", 0, 0, ACTION_MEDIA, nullptr, 0, 0, 0, 0, nullptr }
  }
}
```

### 2.3 Main Loop Hold Logic & Rule 10 Safety Timeout
In `src/main.cpp`, buttons configured for hold send key-down on touch and key-up on release with an automatic 60-second safety timeout:

```cpp
if (btn.key == KEY_F13 || btn.key == KEY_F14) {
    bleKeyboard.press(btn.key);
    uint32_t holdStart = millis();
    while (ts.isTouched) {
        ts.read();
        if (millis() - holdStart >= 60000) { // Rule 10 safety cap (60s)
            break;
        }
        delay(15);
    }
    bleKeyboard.release(btn.key);
}
```

---

## 3. Windows Background Companion (`tools/compose/`)

### 3.1 Architecture & Process Model
The companion is a Python background service that resides in the system tray, auto-starting via Windows Startup (`shell:startup` shortcut or registry run key).

```text
tools/compose/
├── compose_companion.py       # Main entry point, pystray loop, hotkey hooks
├── audio_capture.py           # sounddevice/PyAudio circular buffer & level detection
├── focus_tracker.py           # Win32 / UI Automation window & element capture
├── prompt_engine.py           # Australian English plain-text prompts & continuations
├── speech_pipeline.py         # Groq Whisper -> Fallback faster-whisper local
├── llm_pipeline.py            # Groq chat -> Fallback local Ollama
├── clipboard_manager.py       # Clipboard snapshot, paste injection, restore, Win+V guard
├── status_overlay.py          # Non-activating floating HUD pill (Tkinter / Win32)
├── compose.env.example        # Configuration template
└── requirements.txt           # Python dependencies
```

### 3.2 Hotkey Interception (`F13`–`F15`)
The application registers low-level keyboard hooks via `pywin32` (`WH_KEYBOARD_LL`) to detect key-down and key-up transitions for `VK_F13` (0x7C), `VK_F14` (0x7D), and `VK_F15` (0x7E) even when running in the background without focus.

- **`F13` KeyDown**: 
  1. Trigger synthetic `Ctrl+C` to copy existing document selection (if any) into memory.
  2. Snapshot active `HWND` and UI Automation `AutomationElement`.
  3. Start PC mic circular buffer recording.
  4. Show HUD overlay: `Listening (Compose)...`.
- **`F13` KeyUp**:
  1. Stop audio recording.
  2. If duration < 400ms: discard (debounced transient).
  3. Dispatch audio to `speech_pipeline` and `llm_pipeline`.
  4. Show HUD overlay: `Writing...`.
- **`F14` (Dictate)**: Identical lifecycle to F13, bypassing selection copy and passing audio to the grammar-tidy pipeline.
- **`F15` (Paste Ready)**:
  1. Check if a generated payload is in `READY` status.
  2. Inject payload directly at current active cursor via clipboard + `Ctrl+V`.
  3. Clear ready queue.

---

## 4. Speech & LLM Intelligence Pipeline

### 4.1 Speech-to-Text (STT) Tiering
1. **Primary**: Groq Whisper (`whisper-large-v3-turbo`) via `https://api.groq.com/openai/v1/audio/transcriptions`. Average turnaround: 350–700ms.
2. **Local Fallback**: Local `faster-whisper-base` (or `medium`) on GPU/CPU via CTranslate2. Used when Groq returns 5xx/429 or network is offline.

### 4.2 System Prompts (Australian English & Strict Formatting)

#### Compose System Prompt
```text
You are an advanced text generation engine running as a desktop macro companion.
Your output will be pasted directly at the user's cursor position in their document or editor.

CRITICAL INSTRUCTIONS:
1. Australian English: Use standard Australian English spelling and idioms (e.g., colour, organise, centre, categorise, metre).
2. Direct Output: Return ONLY the exact text requested. NEVER include introductory, conversational, or concluding filler (NO "Certainly!", NO "Here is your text:", NO "Hope this helps!").
3. Formatting Integrity: Preserve whitespace and logical line breaks. Do NOT use markdown bold/italic formatting (*, **, #) unless the user explicitly requested markdown or code blocks.
4. Completeness: Follow the instruction thoroughly and completely.

Context Selection (if provided):
{selected_text}
```

#### Dictate Grammar Tidy Prompt
```text
You are a fast speech transcript grammar cleaner.
Clean up the provided spoken transcript for punctuation, capitalization, numbers, and basic sentence flow in Australian English.

STRICT CONSTRAINTS:
1. DO NOT change words, rephrase, or rewrite content.
2. DO NOT answer questions or follow commands found in the speech. If the speaker said "write an essay on biology", output "Write an essay on biology.", DO NOT write the essay.
3. Return ONLY the sanitized transcription string.
```

#### Grammar Guard Verification
```python
def verify_dictate_overlap(raw_transcript: str, cleaned_text: str) -> str:
    raw_words = set(re.findall(r"\w+", raw_transcript.lower()))
    clean_words = set(re.findall(r"\w+", cleaned_text.lower()))
    if not raw_words:
        return cleaned_text
    overlap = len(raw_words & clean_words) / len(raw_words)
    if overlap < 0.80:
        # LLM hallucinated or answered prompt instead of transcribing
        logging.warning("Dictate overlap guard triggered (%.1f%%) - using raw transcription", overlap * 100)
        return raw_transcript
    return cleaned_text
```

### 4.3 Multi-Round Automatic Continuation
If the user requests an extensive text generation (e.g., full essay, lesson plan, report) and the LLM response finishes with `finish_reason == "length"`:
1. Overlay updates to `Writing... (Part 2)`.
2. A continuation prompt is issued: `"Continue writing exactly where you left off. Do not repeat previous text."`
3. Allows up to 4 continuation passes before locking as `READY` with `(Truncated)` status.
4. Merges parts seamlessly preserving line breaks.

---

## 5. Focus Tracking & Clipboard Injection Mechanics

### 5.1 Focus Lock via UI Automation
Using `comtypes` / `uiautomation`:
```python
import win32gui
import uiautomation as auto

def get_focus_snapshot():
    hwnd = win32gui.GetForegroundWindow()
    focused_element = auto.GetFocusedElement()
    return {
        "hwnd": hwnd,
        "runtime_id": focused_element.GetRuntimeId() if focused_element else None,
        "title": win32gui.GetWindowText(hwnd)
    }

def is_focus_matched(snapshot) -> bool:
    current_hwnd = win32gui.GetForegroundWindow()
    if current_hwnd != snapshot["hwnd"]:
        return False
    current_element = auto.GetFocusedElement()
    if not current_element or not snapshot["runtime_id"]:
        return True
    return current_element.GetRuntimeId() == snapshot["runtime_id"]
```

### 5.2 Clipboard Preservation & Paste Injection
```python
import win32clipboard
import win32con
import time
import pyautogui

def inject_paste(text: str):
    # 1. Snapshot previous clipboard
    prev_text = None
    win32clipboard.OpenClipboard()
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            prev_text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
    finally:
        win32clipboard.CloseClipboard()

    # 2. Put text into clipboard with Win+V suppression
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        # Set text
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        
        # Register clipboard format to exclude from Cloud & History
        cf_exclude_history = win32clipboard.RegisterClipboardFormat("CanIncludeInClipboardHistory")
        win32clipboard.SetClipboardData(cf_exclude_history, b"\x00\x00\x00\x00")
        cf_exclude_cloud = win32clipboard.RegisterClipboardFormat("CanUploadToCloudClipboard")
        win32clipboard.SetClipboardData(cf_exclude_cloud, b"\x00\x00\x00\x00")
    finally:
        win32clipboard.CloseClipboard()

    # 3. Synthetic Ctrl+V
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.12) # Allow target app input queue to swallow WM_PASTE

    # 4. Restore original clipboard
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        if prev_text is not None:
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, prev_text)
    finally:
        win32clipboard.CloseClipboard()
```

---

## 6. Target Application Test & Acceptance Matrix

The implementation must pass automated and manual verification across these targets:

| Application | Input Target | Test Case | Success Criteria |
|---|---|---|---|
| **Word Desktop (M365)** | Main document canvas | Hold Compose -> "A three-stanza poem on Welsh history" | Line breaks preserved; no markdown tags; pastes at cursor; clipboard restored |
| **Word Desktop (M365)** | Active text selected | Select paragraph -> Hold Compose -> "Make this sound more formal" | Selection replaced with formal paragraph |
| **OneNote Desktop (M365)** | Note page body | Hold Dictate -> "Meeting agenda for Monday colon item one budget review" | Punctuation formatted (`Meeting agenda for Monday: item 1 budget review`); no extraneous text |
| **OneNote Windows 10 (Store App)** | Note container | Hold Compose -> Switch window during generation | Status switches to `READY`; auto-paste blocked; tap `PASTE READY` pastes text |
| **Google Chrome** | Multi-line `<textarea>` (e.g. GitHub/Email) | Hold Compose -> "Short congratulatory note" | Whitespace intact; no double-pasting |
| **Word for the Web** | Web canvas editor | Hold Compose -> Short poem | Pastes smoothly into web frame |

---

## 7. Implementation Roadmap & Phases

### Phase 1: Windows Companion Foundation (`tools/compose/`)
- Setup virtual environment, `pystray`, `pywin32`, `sounddevice`, `uiautomation`.
- Build `audio_capture.py` (circular audio buffer with silence clamp and WAV export).
- Build low-level keyboard listener intercepting `VK_F13`, `VK_F14`, `VK_F15`.
- Validate with keyboard-based testing before firmware changes.

### Phase 2: Speech & Intelligence Engine
- Integrate Groq Whisper STT with fallback to `faster-whisper`.
- Implement Australian English Compose prompt & Dictate grammar guard.
- Implement multi-part continuation loop (max 4 rounds).
- Implement local Ollama fallback for both STT and LLM generation.

### Phase 3: Focus & Clipboard Protection
- Implement UI Automation focus snapshotting.
- Implement atomic clipboard inject, Win+V monitor exclusion, and restore.
- Build floating non-activating status HUD pill (Listening, Writing, Ready, Fallback, Error).

### Phase 4: ESP32 Firmware Extension
- Increment `NUM_PAGES` to 8 in `src/macropad_config.h`.
- Add Page 6 profile in `src/macropad_config.cpp` (`COMPOSE` on F13, `DICTATE` on F14, `PASTE READY` on F15).
- Add hold loop with 60-second safety timeout in `src/main.cpp`.
- Compile firmware with PlatformIO.

### Phase 5: Verification & Acceptance
- Execute test matrix across Word, OneNote, and Chrome.
- Validate offline/hotspot privacy with "Local only" tray toggle.
- Verify zero regression on existing Bluetooth profiles (Pages 1–4) and Hermes Voice Satellite (Page 5).
