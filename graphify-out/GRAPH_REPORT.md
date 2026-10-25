# Graph Report - ESP32 project  (2026-10-25)

## Corpus Check
- 214 files · ~1,294,917 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2068 nodes · 4173 edges · 115 communities (90 shown, 16 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 361 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `81b8eac2`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- MacroPadGUI
- hermes_voice_receiver.py
- EnvironmentManager
- AudioRecorder
- network_manager.cpp
- main.cpp
- es8311_bsp.c
- es8311.cpp
- README.md
- create_enclosure
- bench_llm_paths.py
- flash.py
- start_receiver.sh
- Dashboard-plan.md
- Portable Home/Work Architecture & System Dashboard Guide
- ESP32 Portable MacroPad & Hermes Satellite: Core Engineering Rules
- rules/graphify.md
- workflows/graphify.md
- test_web_grounding.py
- Automated Background Updating
- Workflow: /graph-query
- Workflow: /graph-update
- Workflow: /graph-visualize
- Voice Satellite Operations Runbook
- generate_case_battery.py
- Soft power-off and touch-to-wake — investigation report
- addVoiceTurn
- generate_case_battery_only.py
- gui.cpp
- gui.h
- drawAll
- ESP32_Classroom_Companion_OneNote_Automation_Plan.md
- ESP32 & Windows Compose / Dictate Companion: Architecture & Implementation Plan
- MediaPanel
- Detailed build guide
- Build an ESP32 classroom companion with an AI coding agent
- ComposeCompanion
- .do_POST
- synthesize_speech
- drawStorageExplorer
- ask_fast_llm
- Pinout Reference
- warmup_fast_llm
- test_media_providers.py
- get_composite_status
- queue_lazy_tts
- power_manager.cpp
- 4. Problems Encountered & Root Causes
- dispatch_telegram_mirror
- StatusOverlay
- LlmPipeline
- BoardModel
- SpeechPipeline
- compose_companion.py
- ClipboardManager
- parametrize
- MediaService
- test_compose.py
- TrialTests
- .generate
- companion_settings.py
- test_image_provider_routing.py
- MediaStore
- First real Gemini attempt: rejected request and diagnostic correction
- test_device_feedback.py
- test_gemini_images.py
- Response
- Path
- Gemini home trial: generation and refinement working
- docs/README.md
- Image providers: Gemini first
- Classroom companion: consolidated branch programme
- parametrize
- Gemini rendering and workflow: offline implementation
- HermesPanel
- BoardCandidate
- Project documentation index
- ComposeApp
- FocusTracker
- ProbeState
- Board upload safety
- ChannelStats
- _coeff_div
- drawButton
- build_companion_preview.py
- DashboardStatus
- EnvironmentMode
- SettingsPanel
- Teaching Board B0 renderer trial
- load_env_config
- Create & Paste: approved page 7 device trial
- Three practical routes
- Companion development workboard — 25 October 2026
- Teaching Board: agreed design and development plan
- Hermes readiness — 25 October 2026
- Enclosure dimension and feature reconciliation
- BoardSession
- test_board_hermes.py
- .log
- AudioCapture
- test_image_provider_layout.py
- HotkeyState
- compose_gui.py
- clipboard_manager.py
- Image producers: first offline implementation slice
- Teaching Board: isolated B2 desktop candidate

## God Nodes (most connected - your core abstractions)
1. `MacroPadGUI` - 76 edges
2. `ComposeApp` - 59 edges
3. `MediaStore` - 54 edges
4. `BoardSession` - 48 edges
5. `BoardModel` - 48 edges
6. `BoardValidationError` - 39 edges
7. `MediaPanel` - 38 edges
8. `HermesPanel` - 35 edges
9. `AudioRecorder` - 32 edges
10. `BoardStore` - 31 edges

## Surprising Connections (you probably didn't know these)
- `test_commons_download_rejects_oversized_stream()` --uses--> `CommonsRetriever`  [INFERRED]
  tests/test_media_providers.py → tools/compose/media_providers.py
- `test_commons_download_requires_explicit_rights_acknowledgement_without_network()` --uses--> `CommonsRetriever`  [INFERRED]
  tests/test_media_providers.py → tools/compose/media_providers.py
- `test_commons_download_uses_https_wikimedia_and_bounded_no_redirect_request()` --uses--> `CommonsRetriever`  [INFERRED]
  tests/test_media_providers.py → tools/compose/media_providers.py
- `test_commons_rejects_non_https_or_non_wikimedia_download_hosts()` --uses--> `CommonsRetriever`  [INFERRED]
  tests/test_media_providers.py → tools/compose/media_providers.py
- `test_reopen_preserves_state_history_and_invalidates_previous_session()` --uses--> `BoardSessionError`  [INFERRED]
  tools/compose/tests/test_board_candidate.py → tools/compose/board_session.py

## Import Cycles
- None detected.

## Communities (115 total, 16 thin omitted)

### Community 0 - "MacroPadGUI"
Cohesion: 0.07
Nodes (25): SDFileEntry, HealthState, VoiceUIState, MacroPadGUI, _chatLines, _companionDetail, _companionLinked, _companionState (+17 more)

### Community 1 - "hermes_voice_receiver.py"
Cohesion: 0.13
Nodes (22): ask_hermes_gateway(), _env(), get_local_ip_for_target(), get_voice_session_id(), get_whisper_model(), _hermes_sessions_headers(), _hermes_voice_overrides(), load_voice_session() (+14 more)

### Community 2 - "EnvironmentManager"
Cohesion: 0.08
Nodes (41): Preferences, SemaphoreHandle_t, EnvironmentChangeCallback, EnvironmentMode, String, EnvironmentManager, begin, _changeCallback (+33 more)

### Community 3 - "AudioRecorder"
Cohesion: 0.07
Nodes (27): AudioRecorder, begin, _lastRecordDurationMs, _leftStats, logDiagnostics, _maxLeftPeak, _maxRightPeak, _monoStats (+19 more)

### Community 4 - "network_manager.cpp"
Cohesion: 0.08
Nodes (48): IPAddress, String, HostDiscovery, begin, checkBeacon, discoverNow, _lastBeaconCheck, _lastDiscoveryAttempt (+40 more)

### Community 5 - "main.cpp"
Cohesion: 0.05
Nodes (57): Action, MacroButton, sdcard_type_t, State, active, down, latched, started (+49 more)

### Community 6 - "es8311_bsp.c"
Cohesion: 0.23
Nodes (25): es8311_clock_config_t, es8311_handle_t, es8311_mic_gain_t, es8311_resolution_t, esp_err_t, i2c_port_t, es8311_clock_config(), es8311_create() (+17 more)

### Community 7 - "es8311.cpp"
Cohesion: 0.25
Nodes (26): es8311_clock_config_t, es8311_handle_t, es8311_mic_gain_t, es8311_resolution_t, esp_err_t, i2c_port_t, es8311_clock_config(), es8311_codec_dump_registers() (+18 more)

### Community 8 - "README.md"
Cohesion: 0.13
Nodes (9): Everyday use, Repairs, Verification, Windows Compose and Dictate repair — 17 October 2026, 1. Flash legacy landscape env, 2. Emergency: flash archived golden binaries (no rebuild), Flash portrait (default), Portrait UI — Flash & Revert Guide (+1 more)

### Community 10 - "bench_llm_paths.py"
Cohesion: 0.06
Nodes (36): HTTPError, HTTPResponse, Path, Adapter, build_adapters(), build_messages(), count_lines(), count_sentences() (+28 more)

### Community 15 - "Dashboard-plan.md"
Cohesion: 0.05
Nodes (36): MacroPad readiness, Phase 0 — Protect what currently works, Phase 10 — Define proper status semantics, Phase 11 — Separate Macro readiness from Voice readiness, Phase 12 — Wi-Fi health information, Phase 13 — Add a genuine Internet test, Phase 14 — Avoid dashboard probes interfering with voice, Phase 15 — Make the Python receiver concurrent (+28 more)

### Community 16 - "Portable Home/Work Architecture & System Dashboard Guide"
Cohesion: 0.17
Nodes (12): 1. System Topology, 2. Component Directory, 3. Security Model: Secret Separation, 4. Work Privacy Hardening & Ollama Performance, 5. Page 6 System Dashboard, 6. Host Setup Instructions, Architectural Principles, Home Setup (Linux Server) (+4 more)

### Community 17 - "ESP32 Portable MacroPad & Hermes Satellite: Core Engineering Rules"
Cohesion: 0.14
Nodes (14): ESP32 Portable MacroPad & Hermes Satellite: Core Engineering Rules, Rule 10: Safe Cross-Core Concurrency & Bounded Touch Debounce, Rule 11: Dual-Path Audio Output & Non-Blocking TTS Fallback, Rule 12: Wi-Fi/BLE Coexistence & AP NVS Cache Sanitation, Rule 13: Gateway Tiering & Zero-Zombie Receiver Daemon Semantics, Rule 1: Strict Environment Binding (The Composite Profile Rule), Rule 2: The Contract Principle & Visible Degradation, Rule 3: Asynchronous Receiver Concurrency (The Audio Lock Rule) (+6 more)

### Community 22 - "test_web_grounding.py"
Cohesion: 0.07
Nodes (35): Session, Unit tests for web_grounding (keyword router, Jev/Groq model router, Brave…, test_brave_search_client_parses_results(), test_build_search_query_strips_command_prefix(), test_format_search_context(), test_intent_router_jev_ambiguous_triggers_api(), test_intent_router_jev_failure_falls_back_to_groq(), test_intent_router_jev_success() (+27 more)

### Community 23 - "Automated Background Updating"
Cohesion: 0.25
Nodes (7): 1. Git Commit Hook (Zero-Touch), 2. Live File Watcher (Continuous Auto-Update on Save), 3. Antigravity Agent Rule (Automated Turn-End Maintenance), Automated Background Updating, Everyday Command Reference (`.\graph.ps1`), Graphify Toolkit & Automation System, Slash Commands in Antigravity Chat

### Community 30 - "Voice Satellite Operations Runbook"
Cohesion: 0.22
Nodes (8): Hybrid Fast Lane, LLM Path Benchmark, Mobile Hotspot Connection Troubleshooting (Reason 15), Pre-Warming Ollama in GPU VRAM, Quick Health Check, Starting the Voice Receiver Daemon, Verifying Host Speakers & Audio Pipeline, Voice Satellite Operations Runbook

### Community 31 - "generate_case_battery.py"
Cohesion: 0.21
Nodes (28): add_battery_rails(), add_bottom_grill(), add_cube(), add_cylinder(), add_standoffs(), add_through_bolts(), apply_boolean(), build_battery_and_speaker() (+20 more)

### Community 32 - "Soft power-off and touch-to-wake — investigation report"
Cohesion: 0.07
Nodes (26): 1. Goal, 2. Hardware facts that constrain the design, 3.1 Product UI (this part works), 3.2 Attempt A — ESP32 deep sleep + EXT1 on GPIO17, 3.3 Attempt B — Deep sleep, but put touch on EXT0, 3.4 Attempt C — Light sleep + GPIO wakeup + 150 ms I2C poll, 3.5 Attempt D — No sleep at all; poll I2C like the GUI (current flash), 3. What we implemented (and what you saw) (+18 more)

### Community 33 - "addVoiceTurn"
Cohesion: 0.33
Nodes (6): String, VoiceUIState, addVoiceTurn, drawVoiceCard, scrollToLatestResponse, setCompanionStatus

### Community 34 - "generate_case_battery_only.py"
Cohesion: 0.21
Nodes (26): add_cube(), add_cylinder(), add_standoffs(), add_through_bolts(), apply_boolean(), build_battery(), build_case_bottom(), build_case_top() (+18 more)

### Community 35 - "gui.cpp"
Cohesion: 0.11
Nodes (23): TFT_eSPI, drawWrappedText(), canScrollDown, canScrollUp, clearConversation, drawDashboardSwitching, drawPowerConfirmDialog, drawSleepSplash (+15 more)

### Community 36 - "gui.h"
Cohesion: 0.14
Nodes (12): ChatLine, color, text, ChatMessage, isUser, text, vector, String (+4 more)

### Community 37 - "drawAll"
Cohesion: 0.23
Nodes (12): DashboardStatus, EnvironmentMode, HealthState, drawAll, drawCompanionStatus, drawDashboard, drawDashboardPowerButton, drawDashboardVolume (+4 more)

### Community 38 - "ESP32_Classroom_Companion_OneNote_Automation_Plan.md"
Cohesion: 0.05
Nodes (42): 10. Classroom Companion Command Model, 11. Do Not Hard-Code OneNote Page IDs into Firmware, 12. Dynamic Button Configuration, 13. Lesson Scenes, 14. Windows Companion Providers, 15. Proposed ESP32 Firmware Extension, 16. Reuse Existing ESP32 Networking, 17. Security Model (+34 more)

### Community 39 - "ESP32 & Windows Compose / Dictate Companion: Architecture & Implementation Plan"
Cohesion: 0.07
Nodes (27): 1. Executive Summary, 2.1 Page Allocation & Layout, 2.2 Button Configuration (`src/macropad_config.cpp`), 2.3 Main Loop Hold Logic & Rule 10 Safety Timeout, 2. Firmware Extension (ESP32-S3), 3.1 Architecture & Process Model, 3.2 Hotkey Interception (`F13`–`F15`), 3. Windows Background Companion (`tools/compose/`) (+19 more)

### Community 40 - "MediaPanel"
Cohesion: 0.12
Nodes (8): MediaPanel, apply(), reconcile(), reconcile_saved(), work(), worker(), acquire(), Reveal an externally selected saved version with consistent library controls.

### Community 41 - "Detailed build guide"
Cohesion: 0.11
Nodes (19): 1. Install the tools, 2. Open the repository and give the agent context, 3. Connect the board, build and upload, 4. Test and customise Bluetooth, 5. Set up the optional voice receiver, 6. Connect Blender MCP, 7. Refine the enclosure and print it, 8. Use a repeatable development loop (+11 more)

### Community 42 - "Build an ESP32 classroom companion with an AI coding agent"
Cohesion: 0.14
Nodes (14): 1. Download and open the project, 2. Connect the ESP32 over USB, 3. Configure, build and upload, 4. Pair Bluetooth and try a shortcut, 5. Make a small change with your IDE agent, 6. Connect Blender MCP and refine the case, 7. Add voice once the basic device works, 8. Test, print and keep improving (+6 more)

### Community 43 - "ComposeCompanion"
Cohesion: 0.10
Nodes (12): Image, ComposeCompanion, paste_ready_action(), toggle_local_only(), create_tray_icon_image(), F13 Pressed: Begin Compose recording., F13 Released: Stop recording and dispatch Compose pipeline., F14 Pressed: Begin Dictate recording. (+4 more)

### Community 44 - ".do_POST"
Cohesion: 0.23
Nodes (8): BaseHTTPRequestHandler, Phase 20: Validate Authorization: Bearer <VOICE_RECEIVER_TOKEN> if configured., Strips markdown and unsupported characters for clean display on ST7789 TFT…, Returns 'agent' for tool/action/live-data requests, otherwise 'fast'., route_intent(), sanitize_for_display(), VoiceRequestHandler, wait_for_tts_wav()

### Community 45 - "synthesize_speech"
Cohesion: 0.22
Nodes (11): convert_24k_mono_to_16k_stereo_wav(), Converts 24kHz mono 16-bit PCM WAV to 16kHz stereo 16-bit PCM WAV for ESP32 I2S., Prepare text for TTS pronunciation and ensure optimal generation length., Generate audio via Voicebox and format for ESP32 playback., Generates 16kHz stereo WAV using Windows SAPI (instant offline fallback)., Generates 16kHz stereo WAV using Voicebox (primary) or Windows SAPI (instant…, resolve_voicebox_profile_id(), sanitize_for_tts() (+3 more)

### Community 46 - "drawStorageExplorer"
Cohesion: 0.33
Nodes (6): drawStorageExplorer, navigateStorageTo, navigateStorageUp, refreshStorageExplorer, getSDCardStatus(), sdCardGetStorageSpace()

### Community 47 - "ask_fast_llm"
Cohesion: 0.22
Nodes (14): answer_agent_lane(), answer_fast_lane(), ask_fast_llm(), groq_should_try(), hermes_reachable(), history_messages(), query_ollama_fallback(), Skip Groq when it has no key, the model is wrong, or the network just failed. (+6 more)

### Community 48 - "Pinout Reference"
Cohesion: 0.22
Nodes (8): Additional Peripherals, Audio System (ES8311 Codec: 0x18 & FM8002 Amplifier), Capacitive Touch (FT6336G — I2C: 0x38), Display (2.8-inch 240×320 IPS SPI), ES3C28P hardware reference, Hardware Overview & Board Identification, Mechanical files, Pinout Reference

### Community 49 - "warmup_fast_llm"
Cohesion: 0.20
Nodes (11): _groq_headers(), _groq_network_failure(), _groq_request(), mark_groq_unreachable(), Exception, School networks often block Groq. Don't pay the connect timeout on every…, One request over a persistent TLS connection (reconnects once if Groq dropped…, Validates the Groq key and opens the TLS connection before the first voice turn. (+3 more)

### Community 50 - "test_media_providers.py"
Cohesion: 0.14
Nodes (18): FakeResponse, FakeSession, openai_response(), png_bytes(), parametrize, test_commons_download_rejects_oversized_stream(), test_commons_download_requires_explicit_rights_acknowledgement_without_network(), test_commons_download_uses_https_wikimedia_and_bounded_no_redirect_request() (+10 more)

### Community 51 - "get_composite_status"
Cohesion: 0.29
Nodes (7): check_voicebox_online(), get_composite_status(), probe_hermes_health(), probe_ollama_health(), Probes Hermes Gateway for liveness and detailed readiness., Probes local Ollama for service reachability and model VRAM residency., Returns composite health authority state, cached for 2.5 seconds to minimize…

### Community 52 - "queue_lazy_tts"
Cohesion: 0.33
Nodes (6): queue_lazy_tts(), _run(), Asynchronously speaks text out loud on the host computer's speakers., Start TTS in the background so the JSON reply can leave before audio is ready., speak_on_host_speaker(), _run()

### Community 53 - "power_manager.cpp"
Cohesion: 0.22
Nodes (15): esp_sleep_wakeup_cause_t, gpio_num_t, PowerManager, begin, detachBacklightPwm, enterSoftOff, PowerManager::enterSoftOffDiag(), fadeBacklightOff (+7 more)

### Community 54 - "4. Problems Encountered & Root Causes"
Cohesion: 0.11
Nodes (18): 1. Executive Summary & Objective, 2. Architecture & Topology, 3.1 Firmware Enhancements, 3.2 Windows Companion Subsystem (`tools/compose/`), 3. Work Completed, 4.1 Problem 1: Windows Bluetooth HID Descriptor Caching, 4.2 Problem 2: Tap vs. Hold Debounce Filter, 4.3 Problem 3: `pyautogui.FailSafeException` Crash on Key Down (+10 more)

### Community 55 - "dispatch_telegram_mirror"
Cohesion: 0.50
Nodes (4): dispatch_telegram_mirror(), _async_send(), Phase 19: Asynchronously mirrors voice conversation to Telegram without…, send_telegram_message()

### Community 56 - "StatusOverlay"
Cohesion: 0.16
Nodes (5): Floating non-activating HUD status overlay pill using Tkinter & Win32 styles.…, Displays or updates the HUD overlay non-blockingly., Hides the HUD overlay., Thread-safe floating HUD status pill., StatusOverlay

### Community 57 - "LlmPipeline"
Cohesion: 0.18
Nodes (7): Response, load_env_config(), Loads configuration from compose.env and system environment., LlmPipeline, Calls Groq chat completions endpoint. Returns (content, finish_reason)., Calls local Ollama chat completions endpoint. Returns (content, finish_reason)., test_ollama_uses_installed_model_when_configured_model_is_missing()

### Community 58 - "BoardModel"
Cohesion: 0.08
Nodes (52): demo_model(), BoardConflictError, BoardModel, BoardValidationError, canonical_json(), _colour(), _id(), _keys() (+44 more)

### Community 59 - "SpeechPipeline"
Cohesion: 0.19
Nodes (7): Transcribes audio bytes. Returns: (transcript, provider_used, latency_seconds), Uploads WAV bytes to Groq Whisper endpoint., Transcribes WAV bytes via local faster-whisper., SpeechPipeline, run(), test_auto_whisper_retries_lazy_cuda_failure_on_cpu(), test_explicit_cuda_configuration_does_not_silently_switch_device()

### Community 60 - "compose_companion.py"
Cohesion: 0.12
Nodes (18): ESP32 & Windows Voice Compose & Dictate Companion Service Resides in the…, LLM generation pipeline with Groq high-speed cloud generation, local Ollama…, Executes LLM generation with automatic multi-round continuation if length…, build_compose_messages(), build_dictate_messages(), Prompt engine for Australian English text generation, grammar cleaning, and…, Builds the message list for the Compose pipeline., Builds the message list for the Dictate grammar cleaning pipeline. (+10 more)

### Community 61 - "ClipboardManager"
Cohesion: 0.15
Nodes (13): ClipboardManager, Injects text at the current cursor position: 1. Snapshots prior clipboard. 2.…, Attempts to open the Windows clipboard with retries in case another process…, Safely retrieves current text in clipboard if available., Safely empties the Windows clipboard., Safely sets Unicode text on the Windows clipboard., GUITHREADINFO, _key_event() (+5 more)

### Community 63 - "MediaService"
Cohesion: 0.11
Nodes (8): CommonsRetriever, Explicit Commons search; a result's visibility does not grant reuse rights., MediaService, Application-owned image workflow. Models propose; explicit UI actions dispatch…, Explicit accounting-only retry for a saved image with a lost ledger ACK., truthy(), test_google_is_explicit_and_never_borrows_openai_allocation_or_falls_back(), test_restart_keeps_frozen_choice_allocation_and_single_dispatch()

### Community 64 - "test_compose.py"
Cohesion: 0.19
Nodes (14): make_app(), Regression checks without recording, network requests or desktop keystrokes., test_busy_pipeline_rejects_new_recording(), test_changed_focus_keeps_result_ready_without_paste(), test_dictation_survives_unavailable_cleanup_provider(), test_failed_paste_keeps_payload_for_retry(), test_groq_stt_network_failure_stays_on_local_whisper(), groq() (+6 more)

### Community 65 - "TrialTests"
Cohesion: 0.09
Nodes (15): EspConnection, backup(), candidate_data(), checked_device(), execute(), main(), prepare(), Single-candidate S3 application trial and recovery; stable registration never… (+7 more)

### Community 66 - ".generate"
Cohesion: 0.27
Nodes (5): error_diagnostics(), Read bounded error metadata and a redacted summary, never raw response bodies., Path, safe_identifier(), safe_usage()

### Community 67 - "companion_settings.py"
Cohesion: 0.33
Nodes (15): _atomic_write(), _Blob, _crypt(), data_directory(), _decode_journal(), _journal_bytes(), load_settings(), _load_settings_unlocked() (+7 more)

### Community 68 - "test_image_provider_routing.py"
Cohesion: 0.10
Nodes (24): Protocol, create_image_provider(), image_readiness(), image_snapshot(), ImageCapabilities, ImageProvider, Path, Image producer contract and local request snapshots; never contains credentials. (+16 more)

### Community 70 - "MediaStore"
Cohesion: 0.08
Nodes (23): Any, Connection, Row, RuntimeError, _json(), MediaStore, _now(), Path (+15 more)

### Community 71 - "First real Gemini attempt: rejected request and diagnostic correction"
Cohesion: 0.40
Nodes (5): Established diagnostic defect, First real Gemini attempt: rejected request and diagnostic correction, Offline request-contract check, Real setup and attempt, Verification and delivery

### Community 72 - "test_device_feedback.py"
Cohesion: 0.09
Nodes (21): DeviceFeedback, display_text(), frame(), Opt-in, identity-bound USB display feedback. No recording/insertion/provider…, Call only from Tk. Never send a transcript, document text or credential., snapshot(), Safe feedback, explicit hotkeys and preservation of pending work., test_busy_generation_is_not_advertised_as_ready() (+13 more)

### Community 73 - "test_gemini_images.py"
Cohesion: 0.10
Nodes (37): parametrize, check_google_model(), GeminiImageProvider, Stateless Gemini Interactions image requests. No retries, fallback or URL…, Explicit metadata GET only. Never invoke this during startup/save/setup., Explicit image generation/edit and external retrieval adapters. No provider…, fixture(), Synthetic Interactions REST fixtures, checked against Google's 24 Oct 2026… (+29 more)

### Community 76 - "Gemini home trial: generation and refinement working"
Cohesion: 0.33
Nodes (6): Actual twelve-attempt result, Durable evidence and recovery, Failure and correction, Gemini home trial: generation and refinement working, Verification and remaining acceptance, Visual inspection and accounting

### Community 78 - "Image providers: Gemini first"
Cohesion: 0.18
Nodes (11): Delivery and first action, Existing foundation and necessary changes, Gemini adapter and first settings, Image providers: Gemini first, Intended result, Ordered delivery, Provider contract and durable jobs, Spending and data boundaries (+3 more)

### Community 79 - "Classroom companion: consolidated branch programme"
Cohesion: 0.20
Nodes (10): Approved desktop Teaching Board workstream, Architecture and ownership, Choices and release conditions, Classroom companion: consolidated branch programme, Completion dashboard, Current implementation and verification limits, Ordered delivery backlog, Outcome and fixed decisions (+2 more)

### Community 81 - "Gemini rendering and workflow: offline implementation"
Cohesion: 0.33
Nodes (6): Configuration check, Delivery and remaining gates, Gemini rendering and workflow: offline implementation, Local verification, Provider and request boundary, Workflow and spending

### Community 82 - "HermesPanel"
Cohesion: 0.08
Nodes (26): fixture, review(), _catalogue_item(), is_catalogue_context(), prepare_catalogue(), Bounded, opt-in library metadata for Hermes; recommendations confer no…, Resolve an untrusted result against its immutable submitted catalogue and local…, resolve_recommendation() (+18 more)

### Community 83 - "BoardCandidate"
Cohesion: 0.05
Nodes (25): QWidget, BoardCandidate, BoardCanvas, candidate_directory(), decode_image(), image_resolver(), main(), page_from() (+17 more)

### Community 84 - "Project documentation index"
Cohesion: 0.50
Nodes (4): Completion language, Current plans and operating guides, Implementation and historical evidence, Project documentation index

### Community 85 - "ComposeApp"
Cohesion: 0.11
Nodes (4): ComposeApp, sync_worker(), rollback(), ValueError

### Community 86 - "FocusTracker"
Cohesion: 0.20
Nodes (11): FocusTracker, Finds the specific child control with keyboard focus (e.g. Scintilla inside…, Multi-tier document selection extraction: 1. UI Automation TextPattern (Word,…, test_capture_selected_text_extracts_via_text_pattern(), test_capture_selected_text_falls_back_to_chord_ctrl_c(), test_capture_selected_text_falls_back_to_parent(), test_capture_selected_text_falls_back_to_wm_copy_for_scintilla(), test_capture_selected_text_ignores_this_process() (+3 more)

### Community 87 - "ProbeState"
Cohesion: 0.06
Nodes (18): QGraphicsView, exercise(), identity(), image_bytes(), lesson(), obj(), ProbeState, THROWAWAY B0 fixture. Memory only; never opens user lessons or media stores. (+10 more)

### Community 88 - "Board upload safety"
Cohesion: 0.25
Nodes (8): Board upload safety, Build and check without writing, Historical CYD diagnostic upload route, Registered hardware and roles, S3 trial approval gate, Scoped S3 application trial and recovery, Verification, Verified on 21 October 2026

### Community 89 - "ChannelStats"
Cohesion: 0.14
Nodes (8): ChannelStats, clipCount, count, maxVal, minVal, nonZeroCount, sum, sumSq

### Community 90 - "_coeff_div"
Cohesion: 0.15
Nodes (13): _coeff_div, adc_div, adc_osr, bclk_div, dac_div, dac_osr, fs_mode, lrck_h (+5 more)

### Community 91 - "drawButton"
Cohesion: 0.50
Nodes (4): companionCanPaste, drawButton, getButtonRect, getTouchTarget

### Community 92 - "build_companion_preview.py"
Cohesion: 0.67
Nodes (3): build(), Build an allowlisted source preview without credentials or private reports., source_files()

### Community 96 - "Teaching Board B0 renderer trial"
Cohesion: 0.50
Nodes (4): Environment and scope, Executed local checks, Teaching Board B0 renderer trial, What the comparison establishes

### Community 97 - "load_env_config"
Cohesion: 0.36
Nodes (8): fallback_env_paths(), load_env_config(), _merge_nonempty(), _parse_env_file(), Path, Shared companion settings. Cloud keys may live in compose.env, server/.env, or…, Load Groq fallbacks, Compose, protected feature settings, then process…, test_google_key_is_never_loaded_from_environment_or_plain_file()

### Community 98 - "Create & Paste: approved page 7 device trial"
Cohesion: 0.40
Nodes (5): Attached feedback, Candidate, Create & Paste: approved page 7 device trial, Live result, Recovery and verification before writing

### Community 99 - "Three practical routes"
Cohesion: 0.25
Nodes (8): Durable lessons and transactional undo, Integration, packaging and licence audit, Next decision and later prototype evidence, Pen, touch and ink, Settled needs and unresolved choices, Teacher and pupil windows, Teaching-board renderer options, Three practical routes

### Community 100 - "Companion development workboard — 25 October 2026"
Cohesion: 0.29
Nodes (7): Companion development workboard — 25 October 2026, Decisions already settled, Evidence and acceptance ledger, Open decisions and facts to establish, Starting state and verified delivery, Working method for today's continuation, Workstreams and dependencies

### Community 101 - "Teaching Board: agreed design and development plan"
Cohesion: 0.29
Nodes (7): Agreed implementation increments, Capability boundary, Decision register, First accepted lesson scenario, Outcome and design tree, Teaching Board: agreed design and development plan, Technical options, still open

### Community 102 - "Hermes readiness — 25 October 2026"
Cohesion: 0.33
Nodes (5): Acceptance remains open, Environment distinction, Exact remaining transport blocker, Hermes readiness — 25 October 2026, Today's observations

### Community 103 - "Enclosure dimension and feature reconciliation"
Cohesion: 0.33
Nodes (5): Dimension and feature matrix, Enclosure dimension and feature reconciliation, Evidence and coordinate basis, Missing physical measurements and decisions, Next bounded CAD slices on a copied candidate

### Community 104 - "BoardSession"
Cohesion: 0.11
Nodes (25): BoardAuthorityError, BoardMediaError, BoardSession, BoardSessionError, BoardSessionSaveError, Local teacher/pupil authority, atomic presentation and explicit autosave…, Synchronous autosave boundary; token-bound UI timers must reschedule stale…, Return pinned local bytes only; the trusted resolver owns store lookup. The… (+17 more)

### Community 105 - "test_board_hermes.py"
Cohesion: 0.14
Nodes (44): BoardValidationError, apply_result(), BoardConfirmationRequired, BoardProposalError, _manifest(), _nonfinite(), _pairs(), _parse() (+36 more)

### Community 106 - ".log"
Cohesion: 0.19
Nodes (3): A blocked school network should not add a cloud timeout to every later button…, Snapshots the active foreground window HWND and focused UI Automation control., Verifies if the current foreground window and control still match the snapshot.

### Community 107 - "AudioCapture"
Cohesion: 0.14
Nodes (7): ndarray, AudioCapture, find_default_wasapi_input_device(), Audio capture module using sounddevice and WASAPI for high-fidelity PC…, Starts recording audio from the PC microphone via WASAPI., Stops recording and returns: (wav_bytes_16khz, duration_seconds, rms_level), Finds the default Windows WASAPI recording device and its native sample rate.

### Community 108 - "test_image_provider_layout.py"
Cohesion: 0.24
Nodes (8): Accessible library-first image UI; background I/O never manipulates Tk., descendants(), parametrize, Native layout and masking at both supported companion window sizes., test_frozen_choice_and_image_actions_fit_nested_media_page(), test_full_companion_device_feedback_and_media_actions_fit(), test_gemini_wait_keeps_ui_responsive_and_records_display_timing(), test_image_settings_masks_key_and_keeps_save_reachable()

### Community 109 - "HotkeyState"
Cohesion: 0.18
Nodes (6): HotkeyState, One edge dispatcher for the firmware's held keys, used by both companions., test_cached_descriptor_standard_chord_survives_modifier_release(), test_firmware_dual_keys_produce_one_press_and_one_release(), test_unmodified_function_keys_do_not_record(), test_new_keys_coalesce_extended_and_fallback_chords()

### Community 110 - "compose_gui.py"
Cohesion: 0.29
Nodes (4): Tk, load_env_config(), ESP32 & Windows Voice Compose & Dictate Companion - Interactive Desktop App…, truthy()

### Community 111 - "clipboard_manager.py"
Cohesion: 0.33
Nodes (6): _Input, _InputUnion, _KeyboardInput, Clipboard manager for Windows with atomic snapshot, paste injection, prior…, Send a checked native Ctrl+V, independently of the pointer position., send_paste_shortcut()

### Community 112 - "Image producers: first offline implementation slice"
Cohesion: 0.50
Nodes (4): Changes, Delivery and remaining gates, Image producers: first offline implementation slice, Local verification

### Community 113 - "Teaching Board: isolated B2 desktop candidate"
Cohesion: 0.50
Nodes (4): Available teaching actions, Local verification and remaining acceptance, Run and reopen, Teaching Board: isolated B2 desktop candidate

## Knowledge Gaps
- **394 isolated node(s):** `Outcome and fixed decisions`, `Current implementation and verification limits`, `Architecture and ownership`, `Teacher workflow`, `Ordered delivery backlog` (+389 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 783 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MediaStore` connect `MediaStore` to `.generate`, `test_image_provider_routing.py`, `test_device_feedback.py`, `test_gemini_images.py`, `test_image_provider_layout.py`, `compose_gui.py`, `test_media_providers.py`, `BoardCandidate`, `HermesPanel`, `MediaService`?**
  _High betweenness centrality (0.083) - this node is a cross-community bridge._
- **Why does `ComposeApp` connect `ComposeApp` to `test_compose.py`, `MediaPanel`, `.log`, `AudioCapture`, `test_image_provider_layout.py`, `HotkeyState`, `compose_gui.py`, `HermesPanel`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Why does `BoardSession` connect `BoardSession` to `test_board_hermes.py`, `BoardCandidate`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `ComposeApp` (e.g. with `HermesPanel` and `MediaPanel`) actually correct?**
  _`ComposeApp` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `MediaStore` (e.g. with `main()` and `.__init__()`) actually correct?**
  _`MediaStore` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `BoardSession` (e.g. with `BoardCandidate` and `candidate()`) actually correct?**
  _`BoardSession` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `BoardModel` (e.g. with `demo_model()` and `main()`) actually correct?**
  _`BoardModel` has 8 INFERRED edges - model-reasoned connections that need verification._