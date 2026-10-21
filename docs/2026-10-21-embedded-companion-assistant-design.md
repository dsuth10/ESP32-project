# An assistant built into the desktop companion

> Historical design, investigation or checkpoint evidence. Current scope/status is governed by the [consolidated branch programme](2026-10-21-companion-media-agent-master-plan.md): original S3 only, CYD application port abandoned, Groq primary and the same Linux Hermes over permanent private Tailscale required at home/work. Earlier proposals and test observations below are not proof of current deployment or release acceptance.

Design recommendation — 21 October 2026

This follows the request to make conversational administration part of the desktop application itself. It proposes future architecture; it does not implement history, an agent, a database, runtime device configuration or firmware changes. Existing application and device behaviour is preserved.

## The intended experience

The teacher opens the same companion application and uses an “Ask your companion” area. They can ask for classroom writing, retrieve saved responses, request a shortcut button or ask the companion to diagnose a connection. They do not need an IDE, a separate agent installation or knowledge of the word agent.

Keep Compose, Dictate, Paste Ready, Bluetooth events, microphone handling and the optional voice receiver functioning independently. Add three visible areas alongside the existing controls: Assistant, History and Saved text. Device/settings views can show what changed and provide Undo. Avoid making a teacher navigate technical component names for routine tasks.

An example: “Add a button called Next page that sends Page Down.” The assistant reads the current profile, selects a supported key action, applies a validated profile revision, synchronises the device and reports whether the device acknowledged that revision. If the teacher then tests it in their presentation application, record that acceptance separately. A configuration acknowledgement alone does not prove the target application used the shortcut.

## Current code and the main gap

- `start_companion.bat` delegates to `tools/compose/start_compose.bat`, which launches `compose_gui.py`. The launcher can remain the entry point during development.
- The desktop application is Python/Tkinter and already has speech, generation, queued paste, event feedback and receiver lifecycle code. It currently has a transient pending result; no persistent request/response database was identified in the reviewed companion code.
- `llm_pipeline.py` sends messages to Groq or Ollama and reads generated text. It does not implement a local tool-execution loop.
- Device pages are a fixed `NUM_PAGES` and `const MacroProfile PROFILES[]` in `src/macropad_config.h/.cpp`. Drawing and touch handling have specialised branches. Adding runtime pages requires firmware work, not simply changing a database row.
- BLE currently supplies keyboard actions. It is not an established two-way application configuration protocol. A management transport, device identity, capability handshake and revision acknowledgements still need implementing.

These gaps are tractable, but distinguish the proposed experience from capabilities available today.

## One assistant interface, separate jobs

| Request class | Context | Allowed effects |
| --- | --- | --- |
| Ask / compose / dictate | Writing instructions, selected text when appropriate, selected history, optional current-information search | Produce text; save or queue output using existing focus protections |
| Find / reuse | Explicitly scoped history or saved items | Search, copy, pin or queue a chosen item |
| Change / repair | Application policy, installed versions, supported capabilities, relevant configuration and diagnostics | Validated application/device operations and recoverable configuration revisions |
| Develop a new capability | Relevant source, build environment, engineering constraints and tests | Build an isolated candidate update; verify and deploy through an update worker |

The same Groq account and potentially the same model can serve multiple jobs, using separate conversations, prompts, tool sets and budgets. Test administration and coding performance independently; good writing performance is not evidence of reliable development performance. Keep provider/model selection configurable.

Use visible “Ask” and “Change my companion” modes as a reliable initial boundary; add intent routing for convenience with the active mode displayed. Ordinary writing should not receive device-changing tools. Ask one concise clarification when intent or the target computer/application is genuinely ambiguous. A games-popularity question can use ordinary retrieval/writing context without the engineering manual or management tools. If current popularity is claimed, that answer needs a dated source rather than model recollection.

## Groq supplies reasoning; the local application performs actions

Groq supports local tool calling: the model requests an operation and arguments, the desktop application validates and executes that operation, and returns the result to the model. This requires an orchestration loop in our code. Groq-hosted code execution does not itself access the teacher's Windows computer or ESP32. [Groq local tool calling](https://console.groq.com/docs/tool-use/local-tool-calling).

Example proposed operations include reading capabilities, inspecting profiles, creating a shortcut, creating a page from supported controls, checking the microphone, checking the receiver, applying a revision and restoring the previous revision. These are proposals, not existing commands. Restrict available tools to the current task and validate every call locally. Runtime device limits, valid keys, duplicate labels, target identity, revision conflicts and connectivity should be checked in application code.

Routine reversible changes can follow directly from the user's request: save the prior revision, apply the requested change, verify, show the outcome and offer Undo. Do not add repeated confirmation dialogues to every shortcut request. An action that needs a cable, unavailable school permission or missing hardware must explain the actual dependency instead of claiming success. Firmware installation should occur when idle with a recovery path; never interrupt an active recording/paste session.

## Application knowledge and skills

Package a short versioned application guide with every release. The administration prompt should define the assistant's role, boundaries, verification rules and preference for configuration before source edits. Include a compact current-state summary: app/firmware version, target identity, advertised capabilities and active profile revision.

Load task-specific resources only when needed: shortcut/key mappings; device page schema and limits; audio troubleshooting; receiver/network troubleshooting; history operations; development/build/update procedures. Read live diagnostics rather than relying on chat memory. Cache stable documentation and retrieve relevant sections instead of sending the entire repository and all history on every request.

These skills can be bundled Markdown instructions and schemas; they do not require an external skill service. The executable tools are still necessary. A prompt can describe a button operation, but cannot create a working device-management channel by itself.

Treat retrieved documents, search results, stored generated text and tool output as data. They must not silently become instructions authorising device changes. Avoid sending secrets or unrelated history to the model. Package documentation and tools against matching application versions so older instructions cannot apply unsupported updates.

## Make common changes configuration

Build a small versioned UI/action schema with components such as labelled button, shortcut, text action, navigation button and, later, slider or scroll control. Validate and preview configurations on the desktop, then send supported definitions to a firmware renderer with persistent storage. Retain current built-in pages as the fallback/default profile.

The desktop keeps the authoritative saved configuration; the device keeps a validated applied copy so existing standalone shortcuts do not require an AI call per press. Define atomic revision application, acknowledgements, connection-loss behaviour and restore-last-working semantics. Prototype USB configuration first if it reduces complexity, while treating wireless management as a separately tested transport. Existing USB programming support is not proof that this protocol already exists.

For the proposed scrolling example, first clarify whether the user means scrolling the handheld screen, scrolling a computer document or changing slides. Page Up/Down actions may satisfy a presentation need using keyboard events. Smooth scrolling needs a supported host scroll operation or mouse-wheel HID behaviour; the current keyboard-only action model does not establish that support. Once a scrolling primitive and layout exist, asking for a page containing it can be configuration. Until then, it is a development request.

## Retained requests and reusable text

Use an application-owned local SQLite database under the Windows user application-data directory, outside the repository. Store persistent data through narrow application operations with parameterised queries and transactions. The model should not invent SQL, manage schema migrations or directly rewrite the database file. The application manages database mechanics; the assistant helps users manage its contents.

Proposed records:

- Requests, responses and response revisions, with timestamps, mode, processing provider, success/failure and optional timing/usage information.
- Saved text, titles and tags; allow copying, editing, searching, pinning and explicit queueing for paste.
- Conversation links and explicitly selected context, so a user can continue a previous request without uploading the whole archive.
- Device/profile revisions and change outcomes, kept separate from classroom-writing history.

History should retain the finished response before paste so an insertion failure does not lose it. Streamed partial/failed output should be labelled accordingly. Restoring an old response must not automatically replay an administrative action.

Keep writing history, troubleshooting logs and the administration audit separate. History is deliberately retained content; diagnostic export should still omit it by default. Provide delete, clear-history, export and retention settings, and make it clear when history is enabled. Do not retain raw audio by default. Store credentials separately using OS credential protection. Consider backups, retention expiry, database migration/recovery and removal of personal data from backups as part of persistence design.

The Groq API key stays in the local application's protected settings, not in firmware or public source. Sending a request to Groq remains cloud processing even when actions and the history database are local. Local-only operation must also apply to assistant routing/search; a local text model does not automatically support every administration tool. Explicitly report unsupported capabilities rather than falling back to cloud against the selected policy.

## New code and self-updates

Keep arbitrary feature development as a later capability. The running companion should request changes from a separate build/update worker using an isolated source workspace pinned to the installed version. Run checks, inspect the candidate, keep the existing installation intact, then install/restart at an appropriate time. A packaged application needs a defined extension/update format; source editing alone does not update a packaged executable.

Shared changes can become maintained upstream features; personal configurations remain user data. Local user-created extensions and maintainer-issued releases need distinct trust and update handling. Record build provenance and provide recovery. Do not distribute the project's release-signing private key in teacher installations.

Some requests exceed current hardware or the quality of the selected model. The assistant should say what it can apply immediately, what needs development and what needs physical/user action. “Ask and it happens” should describe successful verified automation, not unqualified promises about arbitrary software generation.

## Recommended implementation order

1. **History foundation:** persistent request/response storage, saved text and copy/reuse; integrate the existing GUI and background companion through shared services. Preserve recording, focus and paste behaviour.
2. **Embedded administration:** Groq tool loop, compact application knowledge, live status and bounded diagnostic/restart/settings tools. Keep existing controls responsive while the assistant runs.
3. **Runtime device personalisation:** page/action schema, firmware renderer and authenticated configuration transport. Start with label/shortcut changes, revision sync and Undo.
4. **Supported control library:** presentation/navigation controls, then scrolling if demand supports it. Make new combinations conversationally configurable.
5. **Development worker:** isolated code generation, tests, candidate installation and rollback for requests beyond the schema.

First milestone acceptance: existing Compose/Dictate/Paste Ready still work; completed text survives restart; a saved item can be copied and deliberately queued; a management request uses actual diagnostic tools and reports their result; writing prompts cannot trigger configuration changes. Subsequent hardware acceptance must verify sync after reconnect/reboot and the actual shortcut behaviour in the selected target application.

The recommended product is a familiar desktop application with a conversational way to operate and personalise it. A modular local execution layer and configurable device make that experience practical while allowing Groq, another cloud provider or a capable local model to supply the reasoning.
