# Graph Report - ESP32 project  (2026-10-24)

## Corpus Check
- 181 files · ~1,264,988 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1633 nodes · 3007 edges · 96 communities (75 shown, 13 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 228 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5940fa54`
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
- .run
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
- HotkeyState
- SpeechPipeline
- compose_companion.py
- ClipboardManager
- parametrize
- MediaService
- test_compose.py
- TrialTests
- media_service.py
- compose_gui.py
- test_image_provider_routing.py
- MediaStore
- First real Gemini attempt: rejected request and diagnostic correction
- test_device_feedback.py
- test_gemini_images.py
- test_image_workflow_two_desktops_and_offline_cache_without_history_sync
- Path
- Gemini home trial: generation and refinement working
- docs/README.md
- Image providers: Gemini first
- Classroom companion: consolidated branch programme
- parametrize
- Gemini rendering and workflow: offline implementation
- HostDiscovery
- Compose_Dictate_Repair_2026-10-17.md
- Project documentation index
- ComposeApp
- FocusTracker
- State
- Board upload safety
- drawButton
- build_companion_preview.py
- DashboardStatus
- EnvironmentMode
- test_image_provider_layout.py
- clipboard_manager.py
- Create & Paste: approved page 7 device trial

## God Nodes (most connected - your core abstractions)
1. `MacroPadGUI` - 76 edges
2. `ComposeApp` - 52 edges
3. `MediaStore` - 51 edges
4. `MediaPanel` - 33 edges
5. `AudioRecorder` - 32 edges
6. `session()` - 29 edges
7. `GeminiImageProvider` - 25 edges
8. `EnvironmentManager` - 24 edges
9. `NetworkManager` - 23 edges
10. `MediaService` - 23 edges

## Surprising Connections (you probably didn't know these)
- `test_openai_redirect_is_not_followed_and_key_is_not_in_error()` --uses--> `ProviderFailure`  [INFERRED]
  tests/test_media_providers.py → tools/compose/media_providers.py
- `test_openai_rejects_decoded_image_over_20_mib()` --uses--> `ProviderFailure`  [INFERRED]
  tests/test_media_providers.py → tools/compose/media_providers.py
- `test_openai_rejects_malformed_or_non_image_bytes()` --uses--> `ProviderFailure`  [INFERRED]
  tests/test_media_providers.py → tools/compose/media_providers.py
- `test_openai_timeout_is_ambiguous_and_never_retried_or_leaked()` --uses--> `ProviderFailure`  [INFERRED]
  tests/test_media_providers.py → tools/compose/media_providers.py
- `test_commons_download_rejects_oversized_stream()` --uses--> `CommonsRetriever`  [INFERRED]
  tests/test_media_providers.py → tools/compose/media_providers.py

## Import Cycles
- None detected.

## Communities (96 total, 13 thin omitted)

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
Cohesion: 0.05
Nodes (35): AudioRecorder, begin, _lastRecordDurationMs, _leftStats, logDiagnostics, _maxLeftPeak, _maxRightPeak, _monoStats (+27 more)

### Community 4 - "network_manager.cpp"
Cohesion: 0.13
Nodes (31): DashboardStatus, EnvironmentMode, function, String, extractJsonBool(), extractJsonField(), extractJsonInt(), extractJsonObject() (+23 more)

### Community 5 - "main.cpp"
Cohesion: 0.07
Nodes (45): MacroButton, sdcard_type_t, calculateBatteryPercentage(), companionCommand(), HealthState, String, executeMacro(), goToSoftOff() (+37 more)

### Community 6 - "es8311_bsp.c"
Cohesion: 0.23
Nodes (25): es8311_clock_config_t, es8311_handle_t, es8311_mic_gain_t, es8311_resolution_t, esp_err_t, i2c_port_t, es8311_clock_config(), es8311_create() (+17 more)

### Community 7 - "es8311.cpp"
Cohesion: 0.13
Nodes (39): _coeff_div, adc_div, adc_osr, bclk_div, dac_div, dac_osr, fs_mode, lrck_h (+31 more)

### Community 8 - "README.md"
Cohesion: 0.22
Nodes (5): 1. Flash legacy landscape env, 2. Emergency: flash archived golden binaries (no rebuild), Flash portrait (default), Portrait UI — Flash & Revert Guide, Revert to landscape (cheapest first)

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
Nodes (38): Session, build_compose_messages(), Builds the message list for the Compose pipeline., Unit tests for web_grounding (keyword router, Jev/Groq model router, Brave…, test_brave_search_client_parses_results(), test_build_search_query_strips_command_prefix(), test_format_search_context(), test_intent_router_jev_ambiguous_triggers_api() (+30 more)

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
Cohesion: 0.13
Nodes (7): MediaPanel, apply(), reconcile(), reconcile_saved(), work(), worker(), acquire()

### Community 41 - "Detailed build guide"
Cohesion: 0.11
Nodes (19): 1. Install the tools, 2. Open the repository and give the agent context, 3. Connect the board, build and upload, 4. Test and customise Bluetooth, 5. Set up the optional voice receiver, 6. Connect Blender MCP, 7. Refine the enclosure and print it, 8. Use a repeatable development loop (+11 more)

### Community 42 - "Build an ESP32 classroom companion with an AI coding agent"
Cohesion: 0.14
Nodes (14): 1. Download and open the project, 2. Connect the ESP32 over USB, 3. Configure, build and upload, 4. Pair Bluetooth and try a shortcut, 5. Make a small change with your IDE agent, 6. Connect Blender MCP and refine the case, 7. Add voice once the basic device works, 8. Test, print and keep improving (+6 more)

### Community 43 - ".run"
Cohesion: 0.18
Nodes (6): Image, paste_ready_action(), toggle_local_only(), create_tray_icon_image(), F15 Tapped: Inject pending payload if in READY status., Creates a tray icon with amber/emerald indicator dot.

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
Cohesion: 0.11
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
Cohesion: 0.24
Nodes (5): Response, LlmPipeline, Calls Groq chat completions endpoint. Returns (content, finish_reason)., Calls local Ollama chat completions endpoint. Returns (content, finish_reason)., test_ollama_uses_installed_model_when_configured_model_is_missing()

### Community 58 - "HotkeyState"
Cohesion: 0.18
Nodes (6): HotkeyState, One edge dispatcher for the firmware's held keys, used by both companions., test_cached_descriptor_standard_chord_survives_modifier_release(), test_firmware_dual_keys_produce_one_press_and_one_release(), test_unmodified_function_keys_do_not_record(), test_new_keys_coalesce_extended_and_fallback_chords()

### Community 59 - "SpeechPipeline"
Cohesion: 0.19
Nodes (7): Transcribes audio bytes. Returns: (transcript, provider_used, latency_seconds), Uploads WAV bytes to Groq Whisper endpoint., Transcribes WAV bytes via local faster-whisper., SpeechPipeline, run(), test_auto_whisper_retries_lazy_cuda_failure_on_cpu(), test_explicit_cuda_configuration_does_not_silently_switch_device()

### Community 60 - "compose_companion.py"
Cohesion: 0.12
Nodes (11): ComposeCompanion, load_env_config(), ESP32 & Windows Voice Compose & Dictate Companion Service Resides in the…, F13 Pressed: Begin Compose recording., F13 Released: Stop recording and dispatch Compose pipeline., F14 Pressed: Begin Dictate recording., F14 Released: Stop recording and dispatch Dictate pipeline., A blocked school network should not add a cloud timeout to every later button… (+3 more)

### Community 61 - "ClipboardManager"
Cohesion: 0.26
Nodes (7): ClipboardManager, Injects text at the current cursor position: 1. Snapshots prior clipboard. 2.…, Attempts to open the Windows clipboard with retries in case another process…, Safely retrieves current text in clipboard if available., Safely empties the Windows clipboard., Safely sets Unicode text on the Windows clipboard., test_paste_failure_restores_previous_clipboard()

### Community 63 - "MediaService"
Cohesion: 0.20
Nodes (4): MediaService, Explicit accounting-only retry for a saved image with a lost ledger ACK., truthy(), test_restart_keeps_frozen_choice_allocation_and_single_dispatch()

### Community 64 - "test_compose.py"
Cohesion: 0.16
Nodes (17): Grammar Guard: strictly verifies transcript-to-output word overlap (>80%) and…, verify_dictate_overlap(), make_app(), Regression checks without recording, network requests or desktop keystrokes., test_busy_pipeline_rejects_new_recording(), test_changed_focus_keeps_result_ready_without_paste(), test_dictate_guard_accepts_punctuation(), test_dictation_survives_unavailable_cleanup_provider() (+9 more)

### Community 65 - "TrialTests"
Cohesion: 0.09
Nodes (15): EspConnection, backup(), candidate_data(), checked_device(), execute(), main(), prepare(), Single-candidate S3 application trial and recovery; stable registration never… (+7 more)

### Community 66 - "media_service.py"
Cohesion: 0.22
Nodes (9): error_diagnostics(), Read bounded error metadata and a redacted summary, never raw response bodies., ProviderFailure, Path, Explicit image generation/edit and external retrieval adapters. No provider…, A request failed after dispatch; its billing outcome may be unknown., safe_identifier(), safe_usage() (+1 more)

### Community 67 - "compose_gui.py"
Cohesion: 0.07
Nodes (37): _atomic_write(), _Blob, _crypt(), data_directory(), _decode_journal(), _journal_bytes(), load_settings(), _load_settings_unlocked() (+29 more)

### Community 68 - "test_image_provider_routing.py"
Cohesion: 0.09
Nodes (25): Protocol, create_image_provider(), image_readiness(), image_snapshot(), ImageCapabilities, ImageProvider, Path, Image producer contract and local request snapshots; never contains credentials. (+17 more)

### Community 70 - "MediaStore"
Cohesion: 0.10
Nodes (20): Any, Connection, Row, RuntimeError, _json(), MediaStore, _now(), Path (+12 more)

### Community 71 - "First real Gemini attempt: rejected request and diagnostic correction"
Cohesion: 0.40
Nodes (5): Established diagnostic defect, First real Gemini attempt: rejected request and diagnostic correction, Offline request-contract check, Real setup and attempt, Verification and delivery

### Community 72 - "test_device_feedback.py"
Cohesion: 0.09
Nodes (21): DeviceFeedback, display_text(), frame(), Opt-in, identity-bound USB display feedback. No recording/insertion/provider…, Call only from Tk. Never send a transcript, document text or credential., snapshot(), Safe feedback, explicit hotkeys and preservation of pending work., test_busy_generation_is_not_advertised_as_ready() (+13 more)

### Community 73 - "test_gemini_images.py"
Cohesion: 0.10
Nodes (36): parametrize, check_google_model(), GeminiImageProvider, Stateless Gemini Interactions image requests. No retries, fallback or URL…, Explicit metadata GET only. Never invoke this during startup/save/setup., fixture(), Synthetic Interactions REST fixtures, checked against Google's 24 Oct 2026…, HTTP rejection diagnostics must be useful without copying private response text. (+28 more)

### Community 74 - "test_image_workflow_two_desktops_and_offline_cache_without_history_sync"
Cohesion: 0.18
Nodes (4): Response, parametrize, One synthetic image through jobs, shared budget, private API and two caches., test_image_workflow_two_desktops_and_offline_cache_without_history_sync()

### Community 76 - "Gemini home trial: generation and refinement working"
Cohesion: 0.33
Nodes (6): Actual twelve-attempt result, Durable evidence and recovery, Failure and correction, Gemini home trial: generation and refinement working, Verification and remaining acceptance, Visual inspection and accounting

### Community 77 - "docs/README.md"
Cohesion: 0.29
Nodes (4): Changes, Delivery and remaining gates, Image producers: first offline implementation slice, Local verification

### Community 78 - "Image providers: Gemini first"
Cohesion: 0.18
Nodes (11): Delivery and first action, Existing foundation and necessary changes, Gemini adapter and first settings, Image providers: Gemini first, Intended result, Ordered delivery, Provider contract and durable jobs, Spending and data boundaries (+3 more)

### Community 79 - "Classroom companion: consolidated branch programme"
Cohesion: 0.22
Nodes (9): Architecture and ownership, Choices and release conditions, Classroom companion: consolidated branch programme, Completion dashboard, Current implementation and verification limits, Ordered delivery backlog, Outcome and fixed decisions, Stable S3 trial and recovery (+1 more)

### Community 81 - "Gemini rendering and workflow: offline implementation"
Cohesion: 0.33
Nodes (6): Configuration check, Delivery and remaining gates, Gemini rendering and workflow: offline implementation, Local verification, Provider and request boundary, Workflow and spending

### Community 82 - "HostDiscovery"
Cohesion: 0.21
Nodes (17): IPAddress, String, HostDiscovery, begin, checkBeacon, discoverNow, _lastBeaconCheck, _lastDiscoveryAttempt (+9 more)

### Community 83 - "Compose_Dictate_Repair_2026-10-17.md"
Cohesion: 0.33
Nodes (4): Everyday use, Repairs, Verification, Windows Compose and Dictate repair — 17 October 2026

### Community 84 - "Project documentation index"
Cohesion: 0.50
Nodes (4): Completion language, Current plans and operating guides, Implementation and historical evidence, Project documentation index

### Community 85 - "ComposeApp"
Cohesion: 0.06
Nodes (15): ndarray, Tk, AudioCapture, find_default_wasapi_input_device(), Audio capture module using sounddevice and WASAPI for high-fidelity PC…, Starts recording audio from the PC microphone via WASAPI., Stops recording and returns: (wav_bytes_16khz, duration_seconds, rms_level), Finds the default Windows WASAPI recording device and its native sample rate. (+7 more)

### Community 86 - "FocusTracker"
Cohesion: 0.13
Nodes (17): FocusTracker, GUITHREADINFO, _key_event(), _key_is_down(), Focus tracking, UI Automation target lock, and multi-tier selection capture for…, Finds the specific child control with keyboard focus (e.g. Scintilla inside…, Sends WM_COPY directly to window handle without simulating keyboard events., Synthesizes Ctrl+C while the ESP32 chord is holding Alt/Shift. Keys this method… (+9 more)

### Community 87 - "State"
Cohesion: 0.19
Nodes (12): Action, State, active, down, latched, started, swallowed, Step (+4 more)

### Community 88 - "Board upload safety"
Cohesion: 0.25
Nodes (8): Board upload safety, Build and check without writing, Historical CYD diagnostic upload route, Registered hardware and roles, S3 trial approval gate, Scoped S3 application trial and recovery, Verification, Verified on 21 October 2026

### Community 91 - "drawButton"
Cohesion: 0.50
Nodes (4): companionCanPaste, drawButton, getButtonRect, getTouchTarget

### Community 92 - "build_companion_preview.py"
Cohesion: 0.67
Nodes (3): build(), Build an allowlisted source preview without credentials or private reports., source_files()

### Community 96 - "test_image_provider_layout.py"
Cohesion: 0.31
Nodes (7): descendants(), parametrize, Native layout and masking at both supported companion window sizes., test_frozen_choice_and_image_actions_fit_nested_media_page(), test_full_companion_device_feedback_and_media_actions_fit(), test_gemini_wait_keeps_ui_responsive_and_records_display_timing(), test_image_settings_masks_key_and_keeps_save_reachable()

### Community 97 - "clipboard_manager.py"
Cohesion: 0.33
Nodes (6): _Input, _InputUnion, _KeyboardInput, Clipboard manager for Windows with atomic snapshot, paste injection, prior…, Send a checked native Ctrl+V, independently of the pointer position., send_paste_shortcut()

### Community 98 - "Create & Paste: approved page 7 device trial"
Cohesion: 0.40
Nodes (5): Attached feedback, Candidate, Create & Paste: approved page 7 device trial, Live result, Recovery and verification before writing

## Knowledge Gaps
- **360 isolated node(s):** `Outcome and fixed decisions`, `Current implementation and verification limits`, `Architecture and ownership`, `Teacher workflow`, `Ordered delivery backlog` (+355 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 684 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ComposeApp` connect `ComposeApp` to `test_compose.py`, `HotkeyState`, `compose_gui.py`, `test_image_provider_layout.py`?**
  _High betweenness centrality (0.035) - this node is a cross-community bridge._
- **Why does `MediaStore` connect `MediaStore` to `test_image_provider_layout.py`, `media_service.py`, `test_image_provider_routing.py`, `test_device_feedback.py`, `test_gemini_images.py`, `test_image_workflow_two_desktops_and_offline_cache_without_history_sync`, `test_media_providers.py`, `ComposeApp`, `MediaService`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Why does `MacroPadGUI` connect `MacroPadGUI` to `addVoiceTurn`, `gui.cpp`, `gui.h`, `drawAll`, `drawStorageExplorer`, `drawButton`?**
  _High betweenness centrality (0.013) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `ComposeApp` (e.g. with `make_app()` and `test_full_companion_device_feedback_and_media_actions_fit()`) actually correct?**
  _`ComposeApp` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `MediaStore` (e.g. with `.__init__()` and `OpenAIImageProvider`) actually correct?**
  _`MediaStore` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `MediaPanel` (e.g. with `._build_ui()` and `test_frozen_choice_and_image_actions_fit_nested_media_page()`) actually correct?**
  _`MediaPanel` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Outcome and fixed decisions`, `Current implementation and verification limits`, `Architecture and ownership` to the rest of the system?**
  _360 weakly-connected nodes found - possible documentation gaps or missing edges._