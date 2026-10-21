# Embedded assistant architecture review

21 October 2026 — design review only

## Finding

The smallest viable first step is a management/chat feature inside the existing Windows Tk companion. It should call Groq through a separate assistant service that offers a small, typed set of local actions. Conversation history and reusable response clips belong in local companion storage. Keep the existing Compose/Dictate text-generation path separate: it currently builds one request and calls Groq or Ollama, while this management assistant needs its own multi-turn history and tool-call loop.

The ESP32 should continue to render and dispatch a fixed, firmware-defined set of actions in the first increment. Runtime-configurable button/page manifests can follow as a separate feature. Arbitrary future capabilities require reviewed source changes, builds and firmware delivery; a model response cannot safely become executable code or an unrestricted device command.

## Current architecture

- `tools/compose/compose_gui.py` owns a single Tk window and constructs its buttons, status cards and help text directly in Python. It already has the Groq key/model settings and calls `LlmPipeline.generate()` for Compose/Dictate.
- `tools/compose/llm_pipeline.py` posts chat-completion messages to Groq or local Ollama, handles fallback and truncation continuation, and returns text. It has no persistent conversational session or local function registry.
- ESP32 page content is compile-time data: `NUM_PAGES` is 8 and `PROFILES` is a fixed array of `MacroProfile` values. Touch routing and rendering index those profiles. Page 5 holds chat turns in RAM, capped at 20 messages, and offers scrolling/clear; this is device voice chat, not persistent history in the Windows Tk app.
- `EnvironmentManager` persists the selected HOME/WORK profile and a discovered WORK host IP in Preferences. Network credentials, endpoint defaults and the button profiles still come from build-time configuration. This is limited dynamic state, not a general configuration channel.
- The firmware currently has Bluetooth keyboard action types (media, key combo, string, voice) and no general remote page/button update protocol identified in these files.

## Proposed shape

1. Add a Tk “Assistant” view and a separate `assistant_service` module. Reuse the existing Groq key and configurable model, but keep separate prompts, history and policy from Compose/Dictate. Persist user/assistant turns and named reusable clips in a local SQLite database with timestamps, delete/export controls, retention settings and content-free operational logs. Make cloud transmission clear at the point of use.
2. Implement local Groq function calling as an allowlisted dispatcher. Start with read-only operations such as companion/device status, configuration validation and diagnostic summaries. Each function has a fixed schema and bounded result. Validate arguments and permissions locally; tools execute in the companion process, never on Groq. Routine reversible configuration changes can follow the explicit user request, with a saved prior revision and Undo. Apply established permissions to service changes and updates; explain and request any actual missing access or physical action when needed. Groq describes this as local tool calling: the model requests a function and application code chooses whether and how it runs. [Groq local tool calling](https://console.groq.com/docs/tool-use/local-tool-calling)
3. Add an explicit “Manage this application” mode. Only that mode loads repository-specific instructions/skills and any application context needed for the request. Keep ordinary chat generic. Gather context locally and narrowly (for example, product/version and a user-selected diagnostic bundle); require a separate choice before sending document text, selected text, recordings, transcripts or logs containing user content. Use versioned bundled skills as application guidance; treat retrieved content and app data as data, never as permission to widen the dispatcher.
4. For custom Tk buttons/pages, use a versioned declarative JSON configuration with stable IDs, supported action enums, length/count limits and validation. The Tk app can render these at runtime, so routine personalisation does not need a rebuild. For ESP32-screen customisation, first add a firmware-defined manifest parser, supported action dispatcher, persistence/migration, page navigation and scroll behavior, plus a local transport and authentication design. The agent may author a manifest, but firmware remains the authority on allowed action types. Firmware and transport changes require build/flash and physical verification.
5. Keep the extension path in two lanes: validated configuration for supported controls; code change/build/install for a genuinely new capability. Have the assistant prepare an isolated patch or branch and report build and verification results. Installation must follow the user-authorised scope and update policy, with any outstanding approval sought only after the candidate is concrete and reviewable. Define rollback and preserve existing user profiles and history during updates.

Groq documents function calling and a separate JSON Schema structured-output feature. The current documentation says structured outputs do not support tool use at the same time, so the implementation should choose a tool-calling response loop and validate every call locally rather than assume the schema mode can wrap the same request. Model availability and feature support should be checked when choosing the configured model. [Groq tool use](https://console.groq.com/docs/tool-use/overview), [Groq structured outputs and limitations](https://console.groq.com/docs/structured-outputs)

## Critical unknowns before implementation

- Is the first configurable surface the Windows Tk companion, the ESP32 touchscreen, or both? The risk and work differ substantially; host-only controls are the smallest useful slice.
- Which actions may the assistant run automatically, which require confirmation, and which remain owner-only (especially file edits, service control, network changes and flashing)?
- Should conversation history/clips sync across devices, or stay on this Windows account? What retention, encryption and delete behavior are required?
- What exact application context is useful for administration, and how should the mode avoid sending classroom documents or student data to Groq?
- How should ESP32 receive manifests: USB serial, authenticated local network, or another existing channel? Confirm memory/flash budget, SD availability, display bounds, action limits and compatibility with all eight pages.
- Which Groq model and supported tool-call behaviour are intended, and what is the offline behavior? The existing Groq-to-Ollama fallback only applies to the current text pipeline and does not by itself establish that the assistant's tool loop works locally.
- What constitutes successful delivery for a new feature: local build, packaged companion update, device flash, or physical interaction in the target application?
