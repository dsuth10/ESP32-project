# Windows Compose and Dictate repair — 17 October 2026

The immediate reason Page 6 produced no response was that no Windows companion was running. USB COM5 supplies the programming/serial connection; Page 6 control events travel over Bluetooth to the Windows companion. The Linux Page 5 receiver is a separate path.

## Repairs

- The launched GUI now handles both key-down and key-up. The firmware holds its keys throughout both tap-latched and hold-to-talk recordings, so key release must finish recording. Waiting for another key-down left the GUI recording indefinitely.
- Both companion entry points use one polling edge decoder. Extended F13–F15 and the redundant Ctrl+Alt+Shift+F9–F11 chord produce one event per action. Standard function-key release remains tracked if a modifier changes. The tray service no longer adds a competing keyboard hook.
- The GUI no longer calls the nonexistent `FocusTracker.restore_focus()`. It checks the original target; changed focus retains generated text in READY. Focus the document and use the hardware PASTE READY button to insert it. GUI test-button recordings also retain their output rather than inserting into the companion itself.
- Selection capture uses UI Automation rather than injecting Ctrl+C while the hardware is holding Ctrl+Alt+Shift. UI Automation is initialised on the calling thread, and a failed comparison against a recorded control retains the result in READY.
- The GUI now uses the text returned by the dictation guard. Previously, a rejected candidate was still selected because the returned original transcript was treated as a truthy Boolean. Grammar cleanup failure now preserves the original transcript.
- Paste uses checked native Windows input rather than PyAutoGUI, avoiding the screen-corner failsafe. Failed injection retains the pending GUI payload. Successful input submission is not itself proof that every possible target application consumed the paste.
- Microphone start failure is reported without falsely entering recording state. The GUI finishes recording after 60 seconds and rejects overlapping generation jobs. Background threads send GUI work through a queue drained by the Tk main thread.
- Automatic local Whisper device selection now retries on CPU if GPU initialisation or lazy inference fails. This machine has a visible CUDA device but failed inference because `cublas64_12.dll` could not load. The prior implementation also depended on undeclared PyTorch for device detection; it now uses CTranslate2.
- The launcher keeps startup errors visible, GUI instances are guarded against duplicate launches, required NumPy/SciPy dependencies are declared, and local logs are ignored by Git.

## Verification

- Windows reported COM5 and a Bluetooth device named ESP32 MacroPad with status OK. No firmware reflash or Bluetooth re-pair was needed for this repair.
- A brief Logitech C270 microphone recording produced a valid audio buffer.
- The companion has no configured Groq key. Local Whisper base is cached, and local Ollama has `llama3.2:latest` installed.
- A synthetic speech fixture transcribed exactly as “The blue bicycle is beside the garden gate.” using local Whisper after CPU fallback. A separate local Ollama request generated a sentence successfully.
- All 17 regression checks passed: `python -m pytest tools/compose/tests -q`. Python compilation also passed. Checks cover hardware edges, redundant HID keys, modifier changes, microphone failure, overlapping jobs, focus changes, paste failures, grammar guard handling, and lazy CUDA failure.
- The repaired GUI was launched in the interactive Windows session and reported a responding desktop window with no startup error.
- The user physically tested Page 6 DICTATE and confirmed: “It records and inserts text”. This confirms the hardware-to-document dictation path in the tested target. Physical COMPOSE testing and other target applications have not been confirmed.

The existing implementation report is historical context. Its blanket functional claims, claim that the grammar guard guarantees no hallucinations, and description of native paste did not match the inspected source. Background-launch visibility depends on the actual Windows session; the repaired app launched successfully from this session.

## Everyday use

Run `tools/compose/start_compose.bat` when the companion is closed. Leave the companion running, focus an editable document, and select Page 6 on the ESP32. Tap COMPOSE or DICTATE to latch recording, then tap again to finish; holding a button records until release. If the target changes while processing, focus the intended document and tap PASTE READY. Closing the companion stops its microphone and hardware listener. Automatic startup at Windows sign-in has not been configured.

Firmware and the Page 5/Linux receiver were left as found. Existing unrelated working-tree changes were preserved. The repository-wide whitespace check still reports pre-existing trailing whitespace in `src/main.cpp`.
