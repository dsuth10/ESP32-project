# Embedded companion assistant: first working increment

> Historical design, investigation or checkpoint evidence. Current scope/status is governed by the [consolidated branch programme](2026-10-21-companion-media-agent-master-plan.md): original S3 only, CYD application port abandoned, Groq primary and the same Linux Hermes over permanent private Tailscale required at home/work. Earlier proposals and test observations below are not proof of current deployment or release acceptance.

21 October 2026

## Available now

The application launched by `start_companion.bat` has three tabs:

- **Compose & Dictate:** the existing recording, transcription, generation, focus protection, hardware shortcuts and Paste Ready controls.
- **Ask your companion:** typed requests with separate Ask and Manage contexts. Ask produces writing. Manage can read a deliberately limited status summary, save named text and optionally search retained History.
- **History & saved text:** persistent text requests/responses, Unicode search, saved filtering, copy, deliberate queueing for Paste Ready, UTF-8 export and individual deletion.

Restart an already-running companion to load the new interface. No new Python dependency is required beyond the current companion environment: storage uses SQLite from the standard library. Existing receiver startup/ownership behaviour is preserved. The separate older tray-service entry point is not integrated with the new desktop History in this increment.

## Assistant behaviour

The assistant reuses the existing Groq configuration and key. `GROQ_ASSISTANT_MODEL`, when set, selects a model separately from Compose. Management requires tool/function calling support. With no Groq key, or `LOCAL_ONLY=1`, the assistant calls the configured Ollama OpenAI-compatible endpoint. There is no automatic cloud fallback for assistant local-only mode. Actual offline management depends on the installed model's tool support.

Ask has no management tools, no access to saved History and no live search. Existing Compose web grounding remains available separately. Manage receives a short application-specific prompt and can call only the supported local operations. It cannot execute shell commands, arbitrary SQL, source changes or firmware installation. A model cannot enable an undeclared operation by naming it.

The status tool returns recording/busy flags, microphone-configuration presence, processing policy, History availability, queued-text presence and whether the receiver port is open. It excludes document text, logs, keys, network addresses and microphone identifiers. It explicitly distinguishes a listening port from verified receiver/backend health and does not claim Bluetooth readiness.

History search requires selecting **Allow History search for this request** in Manage mode. That grant resets after submission. Matching retained text goes to the chosen model as tool results. Ask and Manage keep separate bounded recent conversations; **New conversation** clears their in-memory context without deleting stored History. An explicit Save request may retain chosen text even when automatic request History is switched off.

Tool arguments are validated locally, batches/rounds are bounded, repeated writes within one request are deduplicated, and successful operation receipts remain available if a later provider call fails. Closing the window cancels subsequent assistant tool execution and result persistence. An already-issued network request cannot be recalled, and a completed save is not undone by cancellation.

## Persistence and recovery

The default database is `%LOCALAPPDATA%\ESP32ClassroomCompanion\companion.sqlite3`. `ESP32_COMPANION_DATA_DIR` can override its directory for isolated tests. User writing, SQLite sidecars and local QA directories are excluded from Git. No raw audio or configuration credentials are included in the History schema. The database is local text storage using Windows account permissions, without application-level encryption.

Automatic retention defaults on because persistent request/response history was requested. Set `HISTORY_ENABLED=0` in `compose.env` for a different startup default, or use the visibly labelled session checkbox. Selected source-document context is not separately archived with a request. New sensitive previews in the desktop GUI remain visible in its live text area but are not duplicated into the operational log file. Existing historical logs are not altered.

Completed Compose/Dictate output is saved before delivery is scheduled. If storage is unavailable, the companion reports that condition and preserves the existing writing/queued-paste path. A failed provider request is labelled failed rather than stored as a completed writing result. History is not an action replay system: selecting old text never reruns its management operations.

## Verification

- Existing companion baseline: 46 tests passed before integration.
- Integrated suite: **90 tests passed**, including real Tk History-widget interactions, persistence across store instances, concurrent writes, Unicode/literal searches, schema-version refusal, tool permissions, local-only selection, duplicate-save handling, cancellation and retention before paste scheduling.
- Python compilation and `git diff --check` passed.
- Live Groq checks using synthetic data succeeded for both Ask and a genuine local status-tool call.
- A native Windows preview successfully sent a synthetic Ask request to Groq, displayed the response, showed it in History and queued the chosen response without injecting text into another application.
- Native preview inspected the existing controls and new tabs at the normal size; a separate Tk layout check verified the main controls fit within a 720 × 640 client area.

Native/live QA used isolated local test databases. Receiver lifecycle and hardware hotkeys were disabled in the preview so testing did not take ownership of the existing device session. No firmware was built or flashed. Physical Compose/Dictate behaviour, Bluetooth reconnection and target-application paste acceptance were not newly tested in this increment. The original running companion window was left intact; restart it to use the new code.

## Next bounded increment

Implement versioned device configuration and an acknowledged transport before exposing conversational handheld edits. Start with a shortcut/label change, preserve the existing built-in profile, keep a last-working revision and verify device persistence after reconnect/reboot. New pages and scrolling require additional supported firmware controls. The current assistant explicitly reports that these changes are unavailable.

The architectural recommendations remain in [the embedded assistant design](2026-10-21-embedded-companion-assistant-design.md). Original local changes to the receiver, launchers and Graphify outputs have been preserved. This increment has not been committed, pushed or published.
