# Graph Report - ESP32 project  (2026-10-18)

## Corpus Check
- 74 files · ~1,168,383 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1117 nodes · 1933 edges · 69 communities (52 shown, 8 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 132 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `364e48fe`
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
- Portrait UI — Flash & Revert Guide
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
- power_manager.cpp
- generate_case_battery_only.py
- gui.cpp
- ChatLine
- drawDashboard
- ESP32_Classroom_Companion_OneNote_Automation_Plan.md
- ESP32 & Windows Compose / Dictate Companion: Architecture & Implementation Plan
- addVoiceTurn
- Detailed build guide
- Build an ESP32 classroom companion with an AI coding agent
- compose_companion.py
- .do_POST
- synthesize_speech
- drawStorageExplorer
- ask_fast_llm
- Pinout Reference
- warmup_fast_llm
- FocusTracker
- get_composite_status
- queue_lazy_tts
- wrapTextToChatLines
- 4. Problems Encountered & Root Causes
- dispatch_telegram_mirror
- StatusOverlay
- LlmPipeline
- AudioCapture
- SpeechPipeline
- .run
- ClipboardManager
- ComposeApp
- _coeff_div
- test_compose.py
- HostDiscovery
- ComposeCompanion

## God Nodes (most connected - your core abstractions)
1. `MacroPadGUI` - 68 edges
2. `AudioRecorder` - 32 edges
3. `ComposeApp` - 27 edges
4. `EnvironmentManager` - 24 edges
5. `NetworkManager` - 23 edges
6. `FocusTracker` - 20 edges
7. `ComposeCompanion` - 18 edges
8. `LlmPipeline` - 17 edges
9. `SpeechPipeline` - 16 edges
10. `EnvironmentProfile` - 16 edges

## Surprising Connections (you probably didn't know these)
- `ComposeCompanion` --uses--> `ClipboardManager`  [INFERRED]
  tools/compose/compose_companion.py → tools/compose/clipboard_manager.py
- `ComposeApp` --uses--> `ClipboardManager`  [INFERRED]
  tools/compose/compose_gui.py → tools/compose/clipboard_manager.py
- `FocusTracker` --uses--> `ClipboardManager`  [INFERRED]
  tools/compose/focus_tracker.py → tools/compose/clipboard_manager.py
- `ComposeCompanion` --uses--> `FocusTracker`  [INFERRED]
  tools/compose/compose_companion.py → tools/compose/focus_tracker.py
- `ComposeCompanion` --uses--> `LlmPipeline`  [INFERRED]
  tools/compose/compose_companion.py → tools/compose/llm_pipeline.py

## Import Cycles
- None detected.

## Communities (69 total, 8 thin omitted)

### Community 0 - "MacroPadGUI"
Cohesion: 0.09
Nodes (23): HealthState, VoiceUIState, MacroPadGUI, _chatLines, _currentStoragePath, drawButton, getButtonRect, getTouchTarget (+15 more)

### Community 1 - "hermes_voice_receiver.py"
Cohesion: 0.13
Nodes (22): ask_hermes_gateway(), _env(), get_local_ip_for_target(), get_voice_session_id(), get_whisper_model(), _hermes_sessions_headers(), _hermes_voice_overrides(), load_voice_session() (+14 more)

### Community 2 - "EnvironmentManager"
Cohesion: 0.08
Nodes (40): SemaphoreHandle_t, EnvironmentChangeCallback, EnvironmentMode, String, EnvironmentManager, begin, _changeCallback, _currentMode (+32 more)

### Community 3 - "AudioRecorder"
Cohesion: 0.05
Nodes (35): AudioRecorder, begin, _lastRecordDurationMs, _leftStats, logDiagnostics, _maxLeftPeak, _maxRightPeak, _monoStats (+27 more)

### Community 4 - "network_manager.cpp"
Cohesion: 0.14
Nodes (31): DashboardStatus, EnvironmentMode, function, String, extractJsonBool(), extractJsonField(), extractJsonInt(), extractJsonObject() (+23 more)

### Community 5 - "main.cpp"
Cohesion: 0.07
Nodes (44): MacroButton, Preferences, sdcard_type_t, TFT_eSPI, vector, calculateBatteryPercentage(), HealthState, executeMacro() (+36 more)

### Community 6 - "es8311_bsp.c"
Cohesion: 0.23
Nodes (25): es8311_clock_config_t, es8311_handle_t, es8311_mic_gain_t, es8311_resolution_t, esp_err_t, i2c_port_t, es8311_clock_config(), es8311_create() (+17 more)

### Community 7 - "es8311.cpp"
Cohesion: 0.25
Nodes (26): es8311_clock_config_t, es8311_handle_t, es8311_mic_gain_t, es8311_resolution_t, esp_err_t, i2c_port_t, es8311_clock_config(), es8311_codec_dump_registers() (+18 more)

### Community 8 - "Portrait UI — Flash & Revert Guide"
Cohesion: 0.33
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

### Community 33 - "power_manager.cpp"
Cohesion: 0.22
Nodes (15): esp_sleep_wakeup_cause_t, gpio_num_t, PowerManager, begin, detachBacklightPwm, enterSoftOff, PowerManager::enterSoftOffDiag(), fadeBacklightOff (+7 more)

### Community 34 - "generate_case_battery_only.py"
Cohesion: 0.21
Nodes (26): add_cube(), add_cylinder(), add_standoffs(), add_through_bolts(), apply_boolean(), build_battery(), build_case_bottom(), build_case_top() (+18 more)

### Community 35 - "gui.cpp"
Cohesion: 0.13
Nodes (18): canScrollDown, canScrollUp, clearConversation, drawDashboardSwitching, drawPowerConfirmDialog, drawSleepSplash, getPowerDialogTarget, highlightStorageRow (+10 more)

### Community 36 - "ChatLine"
Cohesion: 0.25
Nodes (7): ChatLine, color, text, ChatMessage, isUser, text, String

### Community 37 - "drawDashboard"
Cohesion: 0.25
Nodes (11): DashboardStatus, EnvironmentMode, HealthState, drawAll, drawDashboard, drawDashboardPowerButton, drawDashboardVolume, drawStatusBar (+3 more)

### Community 38 - "ESP32_Classroom_Companion_OneNote_Automation_Plan.md"
Cohesion: 0.05
Nodes (42): 10. Classroom Companion Command Model, 11. Do Not Hard-Code OneNote Page IDs into Firmware, 12. Dynamic Button Configuration, 13. Lesson Scenes, 14. Windows Companion Providers, 15. Proposed ESP32 Firmware Extension, 16. Reuse Existing ESP32 Networking, 17. Security Model (+34 more)

### Community 39 - "ESP32 & Windows Compose / Dictate Companion: Architecture & Implementation Plan"
Cohesion: 0.07
Nodes (27): 1. Executive Summary, 2.1 Page Allocation & Layout, 2.2 Button Configuration (`src/macropad_config.cpp`), 2.3 Main Loop Hold Logic & Rule 10 Safety Timeout, 2. Firmware Extension (ESP32-S3), 3.1 Architecture & Process Model, 3.2 Hotkey Interception (`F13`–`F15`), 3. Windows Background Companion (`tools/compose/`) (+19 more)

### Community 40 - "addVoiceTurn"
Cohesion: 0.29
Nodes (7): String, VoiceUIState, addVoiceTurn, drawVoiceCard, navigateStorageTo, navigateStorageUp, scrollToLatestResponse

### Community 41 - "Detailed build guide"
Cohesion: 0.11
Nodes (19): 1. Install the tools, 2. Open the repository and give the agent context, 3. Connect the board, build and upload, 4. Test and customise Bluetooth, 5. Set up the optional voice receiver, 6. Connect Blender MCP, 7. Refine the enclosure and print it, 8. Use a repeatable development loop (+11 more)

### Community 42 - "Build an ESP32 classroom companion with an AI coding agent"
Cohesion: 0.15
Nodes (13): 1. Download and open the project, 2. Connect the ESP32 over USB, 3. Configure, build and upload, 4. Pair Bluetooth and try a shortcut, 5. Make a small change with your IDE agent, 6. Connect Blender MCP and refine the case, 7. Add voice once the basic device works, 8. Test, print and keep improving (+5 more)

### Community 43 - "compose_companion.py"
Cohesion: 0.11
Nodes (20): ESP32 & Windows Voice Compose & Dictate Companion Service Resides in the…, ESP32 & Windows Voice Compose & Dictate Companion - Interactive Desktop App…, One edge dispatcher for the firmware's held keys, used by both companions., LLM generation pipeline with Groq high-speed cloud generation, local Ollama…, Executes LLM generation with automatic multi-round continuation if length…, build_compose_messages(), build_dictate_messages(), Prompt engine for Australian English text generation, grammar cleaning, and… (+12 more)

### Community 44 - ".do_POST"
Cohesion: 0.23
Nodes (8): BaseHTTPRequestHandler, Phase 20: Validate Authorization: Bearer <VOICE_RECEIVER_TOKEN> if configured., Strips markdown and unsupported characters for clean display on ST7789 TFT…, Returns 'agent' for tool/action/live-data requests, otherwise 'fast'., route_intent(), sanitize_for_display(), VoiceRequestHandler, wait_for_tts_wav()

### Community 45 - "synthesize_speech"
Cohesion: 0.22
Nodes (11): convert_24k_mono_to_16k_stereo_wav(), Converts 24kHz mono 16-bit PCM WAV to 16kHz stereo 16-bit PCM WAV for ESP32 I2S., Prepare text for TTS pronunciation and ensure optimal generation length., Generate audio via Voicebox and format for ESP32 playback., Generates 16kHz stereo WAV using Windows SAPI (instant offline fallback)., Generates 16kHz stereo WAV using Voicebox (primary) or Windows SAPI (instant…, resolve_voicebox_profile_id(), sanitize_for_tts() (+3 more)

### Community 46 - "drawStorageExplorer"
Cohesion: 0.33
Nodes (6): drawStorageExplorer, drawStorageListOnly, refreshStorageExplorer, scrollStorageList, getSDCardStatus(), sdCardGetStorageSpace()

### Community 47 - "ask_fast_llm"
Cohesion: 0.22
Nodes (14): answer_agent_lane(), answer_fast_lane(), ask_fast_llm(), groq_should_try(), hermes_reachable(), history_messages(), query_ollama_fallback(), Skip Groq when it has no key, the model is wrong, or the network just failed. (+6 more)

### Community 48 - "Pinout Reference"
Cohesion: 0.22
Nodes (8): Additional Peripherals, Audio System (ES8311 Codec: 0x18 & FM8002 Amplifier), Capacitive Touch (FT6336G — I2C: 0x38), Display (2.8-inch 240×320 IPS SPI), ES3C28P hardware reference, Hardware Overview & Board Identification, Mechanical files, Pinout Reference

### Community 49 - "warmup_fast_llm"
Cohesion: 0.20
Nodes (11): _groq_headers(), _groq_network_failure(), _groq_request(), mark_groq_unreachable(), Exception, School networks often block Groq. Don't pay the connect timeout on every…, One request over a persistent TLS connection (reconnects once if Groq dropped…, Validates the Groq key and opens the TLS connection before the first voice turn. (+3 more)

### Community 50 - "FocusTracker"
Cohesion: 0.15
Nodes (16): FocusTracker, GUITHREADINFO, _key_event(), _key_is_down(), Focus tracking, UI Automation target lock, and multi-tier selection capture for…, Finds the specific child control with keyboard focus (e.g. Scintilla inside…, Synthesizes Ctrl+C while the ESP32 chord is holding Alt/Shift. Keys this method…, Multi-tier document selection extraction: 1. UI Automation TextPattern (Word,… (+8 more)

### Community 51 - "get_composite_status"
Cohesion: 0.29
Nodes (7): check_voicebox_online(), get_composite_status(), probe_hermes_health(), probe_ollama_health(), Probes Hermes Gateway for liveness and detailed readiness., Probes local Ollama for service reachability and model VRAM residency., Returns composite health authority state, cached for 2.5 seconds to minimize…

### Community 52 - "queue_lazy_tts"
Cohesion: 0.33
Nodes (6): queue_lazy_tts(), _run(), Asynchronously speaks text out loud on the host computer's speakers., Start TTS in the background so the JSON reply can leave before audio is ready., speak_on_host_speaker(), _run()

### Community 53 - "wrapTextToChatLines"
Cohesion: 0.33
Nodes (6): TFT_eSPI, vector, drawWrappedText(), MacroPadGUI::MacroPadGUI(), rebuildChatLines, wrapTextToChatLines()

### Community 54 - "4. Problems Encountered & Root Causes"
Cohesion: 0.08
Nodes (22): Everyday use, Repairs, Verification, Windows Compose and Dictate repair — 17 October 2026, 1. Executive Summary & Objective, 2. Architecture & Topology, 3.1 Firmware Enhancements, 3.2 Windows Companion Subsystem (`tools/compose/`) (+14 more)

### Community 55 - "dispatch_telegram_mirror"
Cohesion: 0.50
Nodes (4): dispatch_telegram_mirror(), _async_send(), Phase 19: Asynchronously mirrors voice conversation to Telegram without…, send_telegram_message()

### Community 56 - "StatusOverlay"
Cohesion: 0.16
Nodes (5): Floating non-activating HUD status overlay pill using Tkinter & Win32 styles.…, Displays or updates the HUD overlay non-blockingly., Hides the HUD overlay., Thread-safe floating HUD status pill., StatusOverlay

### Community 57 - "LlmPipeline"
Cohesion: 0.24
Nodes (5): Response, LlmPipeline, Calls Groq chat completions endpoint. Returns (content, finish_reason)., Calls local Ollama chat completions endpoint. Returns (content, finish_reason)., test_ollama_uses_installed_model_when_configured_model_is_missing()

### Community 58 - "AudioCapture"
Cohesion: 0.12
Nodes (9): ndarray, AudioCapture, find_default_wasapi_input_device(), Audio capture module using sounddevice and WASAPI for high-fidelity PC…, Starts recording audio from the PC microphone via WASAPI., Stops recording and returns: (wav_bytes_16khz, duration_seconds, rms_level), Finds the default Windows WASAPI recording device and its native sample rate., load_env_config() (+1 more)

### Community 59 - "SpeechPipeline"
Cohesion: 0.19
Nodes (7): Transcribes audio bytes. Returns: (transcript, provider_used, latency_seconds), Uploads WAV bytes to Groq Whisper endpoint., Transcribes WAV bytes via local faster-whisper., SpeechPipeline, run(), test_auto_whisper_retries_lazy_cuda_failure_on_cpu(), test_explicit_cuda_configuration_does_not_silently_switch_device()

### Community 60 - ".run"
Cohesion: 0.18
Nodes (6): Image, paste_ready_action(), toggle_local_only(), create_tray_icon_image(), F15 Tapped: Inject pending payload if in READY status., Creates a tray icon with amber/emerald indicator dot.

### Community 61 - "ClipboardManager"
Cohesion: 0.14
Nodes (14): ClipboardManager, _Input, _InputUnion, _KeyboardInput, Clipboard manager for Windows with atomic snapshot, paste injection, prior…, Injects text at the current cursor position: 1. Snapshots prior clipboard. 2.…, Send a checked native Ctrl+V, independently of the pointer position., Attempts to open the Windows clipboard with retries in case another process… (+6 more)

### Community 62 - "ComposeApp"
Cohesion: 0.17
Nodes (5): Tk, ComposeApp, load_env_config(), A blocked school network should not add a cloud timeout to every later button…, Snapshots the active foreground window HWND and focused UI Automation control.

### Community 63 - "_coeff_div"
Cohesion: 0.15
Nodes (13): _coeff_div, adc_div, adc_osr, bclk_div, dac_div, dac_osr, fs_mode, lrck_h (+5 more)

### Community 64 - "test_compose.py"
Cohesion: 0.12
Nodes (18): HotkeyState, make_app(), Regression checks without recording, network requests or desktop keystrokes., test_busy_pipeline_rejects_new_recording(), test_cached_descriptor_standard_chord_survives_modifier_release(), test_changed_focus_keeps_result_ready_without_paste(), test_dictation_survives_unavailable_cleanup_provider(), test_failed_paste_keeps_payload_for_retry() (+10 more)

### Community 65 - "HostDiscovery"
Cohesion: 0.21
Nodes (17): IPAddress, String, HostDiscovery, begin, checkBeacon, discoverNow, _lastBeaconCheck, _lastDiscoveryAttempt (+9 more)

### Community 66 - "ComposeCompanion"
Cohesion: 0.16
Nodes (7): ComposeCompanion, F13 Pressed: Begin Compose recording., F13 Released: Stop recording and dispatch Compose pipeline., F14 Pressed: Begin Dictate recording., F14 Released: Stop recording and dispatch Dictate pipeline., A blocked school network should not add a cloud timeout to every later button…, Verifies if the current foreground window and control still match the snapshot.

## Knowledge Gaps
- **299 isolated node(s):** `_InputUnion`, `_chatLines`, `_currentStoragePath`, `_history`, `_lastDrawnBatHealth` (+294 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 508 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MacroPadGUI` connect `MacroPadGUI` to `gui.cpp`, `ChatLine`, `drawDashboard`, `main.cpp`, `addVoiceTurn`, `drawStorageExplorer`, `wrapTextToChatLines`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Why does `EnvironmentProfile` connect `EnvironmentManager` to `main.cpp`?**
  _High betweenness centrality (0.015) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `ComposeApp` (e.g. with `ClipboardManager` and `FocusTracker`) actually correct?**
  _`ComposeApp` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `_InputUnion`, `_chatLines`, `_currentStoragePath` to the rest of the system?**
  _299 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `MacroPadGUI` be split into smaller, more focused modules?**
  _Cohesion score 0.08666666666666667 - nodes in this community are weakly interconnected._
- **Should `hermes_voice_receiver.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12648221343873517 - nodes in this community are weakly interconnected._
- **Should `EnvironmentManager` be split into smaller, more focused modules?**
  _Cohesion score 0.07804878048780488 - nodes in this community are weakly interconnected._