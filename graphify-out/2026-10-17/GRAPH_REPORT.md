# Graph Report - ESP32 project  (2026-10-17)

## Corpus Check
- 68 files · ~1,161,939 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 982 nodes · 1674 edges · 66 communities (50 shown, 8 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 112 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `86bae7e2`
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
- HostDiscovery
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
- gui.h
- drawDashboard
- ESP32_Classroom_Companion_OneNote_Automation_Plan.md
- ESP32 & Windows Compose / Dictate Companion: Architecture & Implementation Plan
- redrawVoiceCard
- Detailed build guide
- Build an ESP32 classroom companion with an AI coding agent
- compose_companion.py
- .do_POST
- synthesize_speech
- drawStorageExplorer
- ask_fast_llm
- Pinout Reference
- _groq_request
- ask_hermes_gateway
- get_composite_status
- queue_lazy_tts
- ComposeCompanion
- 4. Problems Encountered & Root Causes
- dispatch_telegram_mirror
- StatusOverlay
- LlmPipeline
- AudioCapture
- SpeechPipeline
- .run
- 5. Set up the optional voice receiver
- ComposeApp
- _coeff_div
- 6. Connect Blender MCP

## God Nodes (most connected - your core abstractions)
1. `MacroPadGUI` - 68 edges
2. `AudioRecorder` - 32 edges
3. `EnvironmentManager` - 24 edges
4. `NetworkManager` - 23 edges
5. `ComposeCompanion` - 19 edges
6. `ComposeApp` - 19 edges
7. `EnvironmentProfile` - 16 edges
8. `HostDiscovery` - 15 edges
9. `StatusOverlay` - 15 edges
10. `ChannelStats` - 14 edges

## Surprising Connections (you probably didn't know these)
- `refreshStorageExplorer` --calls--> `sdCardGetStorageSpace()`  [INFERRED]
  src/gui.h → src/sd_card.cpp
- `begin` --calls--> `es8311_codec_init()`  [INFERRED]
  src/audio_recorder.h → src/es8311.cpp
- `logDiagnostics` --calls--> `es8311_codec_dump_registers()`  [INFERRED]
  src/audio_recorder.h → src/es8311.cpp
- `prepareForSleep` --calls--> `es8311_codec_sleep()`  [INFERRED]
  src/audio_recorder.h → src/es8311.cpp
- `loop()` --calls--> `es8311_codec_set_voice_volume()`  [INFERRED]
  src/main.cpp → src/es8311.cpp

## Import Cycles
- None detected.

## Communities (66 total, 8 thin omitted)

### Community 0 - "MacroPadGUI"
Cohesion: 0.09
Nodes (20): HealthState, VoiceUIState, MacroPadGUI, _chatLines, _currentStoragePath, _history, _lastDrawnBatHealth, _lastDrawnBatPercent (+12 more)

### Community 1 - "hermes_voice_receiver.py"
Cohesion: 0.22
Nodes (12): _env(), get_local_ip_for_target(), get_whisper_model(), main(), Hermes Voice Satellite Receiver Service (Concurrent Health Authority…, Phase 17: Preload the active Ollama model into GPU VRAM to prevent first-query…, Process environment first, then the first .env file that defines the key., Returns the primary outbound IP address of this machine. (+4 more)

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
Nodes (43): MacroButton, sdcard_type_t, calculateBatteryPercentage(), HealthState, executeMacro(), goToSoftOff(), loop(), sampleBatteryTelemetry() (+35 more)

### Community 6 - "es8311_bsp.c"
Cohesion: 0.23
Nodes (25): es8311_clock_config_t, es8311_handle_t, es8311_mic_gain_t, es8311_resolution_t, esp_err_t, i2c_port_t, es8311_clock_config(), es8311_create() (+17 more)

### Community 7 - "es8311.cpp"
Cohesion: 0.25
Nodes (26): es8311_clock_config_t, es8311_handle_t, es8311_mic_gain_t, es8311_resolution_t, esp_err_t, i2c_port_t, es8311_clock_config(), es8311_codec_dump_registers() (+18 more)

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
Cohesion: 0.15
Nodes (12): 1. System Topology, 2. Component Directory, 3. Security Model: Secret Separation, 4. Work Privacy Hardening & Ollama Performance, 5. Page 6 System Dashboard, 6. Host Setup Instructions, Architectural Principles, Home Setup (Linux Server) (+4 more)

### Community 17 - "ESP32 Portable MacroPad & Hermes Satellite: Core Engineering Rules"
Cohesion: 0.14
Nodes (14): ESP32 Portable MacroPad & Hermes Satellite: Core Engineering Rules, Rule 10: Safe Cross-Core Concurrency & Bounded Touch Debounce, Rule 11: Dual-Path Audio Output & Non-Blocking TTS Fallback, Rule 12: Wi-Fi/BLE Coexistence & AP NVS Cache Sanitation, Rule 13: Gateway Tiering & Zero-Zombie Receiver Daemon Semantics, Rule 1: Strict Environment Binding (The Composite Profile Rule), Rule 2: The Contract Principle & Visible Degradation, Rule 3: Asynchronous Receiver Concurrency (The Audio Lock Rule) (+6 more)

### Community 22 - "HostDiscovery"
Cohesion: 0.21
Nodes (17): IPAddress, String, HostDiscovery, begin, checkBeacon, discoverNow, _lastBeaconCheck, _lastDiscoveryAttempt (+9 more)

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
Nodes (19): canScrollDown, canScrollUp, drawButton, drawDashboardSwitching, drawPowerConfirmDialog, drawSleepSplash, getButtonRect, getPowerDialogTarget (+11 more)

### Community 36 - "gui.h"
Cohesion: 0.20
Nodes (9): ChatLine, color, text, ChatMessage, isUser, text, String, TFT_eSPI (+1 more)

### Community 37 - "drawDashboard"
Cohesion: 0.25
Nodes (11): DashboardStatus, EnvironmentMode, HealthState, drawAll, drawDashboard, drawDashboardPowerButton, drawDashboardVolume, drawStatusBar (+3 more)

### Community 38 - "ESP32_Classroom_Companion_OneNote_Automation_Plan.md"
Cohesion: 0.05
Nodes (42): 10. Classroom Companion Command Model, 11. Do Not Hard-Code OneNote Page IDs into Firmware, 12. Dynamic Button Configuration, 13. Lesson Scenes, 14. Windows Companion Providers, 15. Proposed ESP32 Firmware Extension, 16. Reuse Existing ESP32 Networking, 17. Security Model (+34 more)

### Community 39 - "ESP32 & Windows Compose / Dictate Companion: Architecture & Implementation Plan"
Cohesion: 0.07
Nodes (27): 1. Executive Summary, 2.1 Page Allocation & Layout, 2.2 Button Configuration (`src/macropad_config.cpp`), 2.3 Main Loop Hold Logic & Rule 10 Safety Timeout, 2. Firmware Extension (ESP32-S3), 3.1 Architecture & Process Model, 3.2 Hotkey Interception (`F13`–`F15`), 3. Windows Background Companion (`tools/compose/`) (+19 more)

### Community 40 - "redrawVoiceCard"
Cohesion: 0.18
Nodes (12): TFT_eSPI, vector, VoiceUIState, drawWrappedText(), addVoiceTurn, clearConversation, drawVoiceCard, MacroPadGUI::MacroPadGUI() (+4 more)

### Community 41 - "Detailed build guide"
Cohesion: 0.18
Nodes (11): 1. Install the tools, 2. Open the repository and give the agent context, 3. Connect the board, build and upload, 4. Test and customise Bluetooth, 7. Refine the enclosure and print it, 8. Use a repeatable development loop, Build, upload and inspect, Create the local configuration (+3 more)

### Community 42 - "Build an ESP32 classroom companion with an AI coding agent"
Cohesion: 0.15
Nodes (13): 1. Download and open the project, 2. Connect the ESP32 over USB, 3. Configure, build and upload, 4. Pair Bluetooth and try a shortcut, 5. Make a small change with your IDE agent, 6. Connect Blender MCP and refine the case, 7. Add voice once the basic device works, 8. Test, print and keep improving (+5 more)

### Community 43 - "compose_companion.py"
Cohesion: 0.13
Nodes (16): ClipboardManager, Clipboard manager for Windows with atomic snapshot, paste injection, prior…, ESP32 & Windows Voice Compose & Dictate Companion Service Resides in the…, ESP32 & Windows Voice Compose & Dictate Companion - Interactive Desktop App…, FocusTracker, Focus tracking and UI Automation target lock module for Windows. Ensures…, Verifies if the current foreground window and control still match the snapshot., LLM generation pipeline with Groq high-speed cloud generation, local Ollama… (+8 more)

### Community 44 - ".do_POST"
Cohesion: 0.23
Nodes (8): BaseHTTPRequestHandler, Phase 20: Validate Authorization: Bearer <VOICE_RECEIVER_TOKEN> if configured., Strips markdown and unsupported characters for clean display on ST7789 TFT…, Returns 'agent' for tool/action/live-data requests, otherwise 'fast'., route_intent(), sanitize_for_display(), VoiceRequestHandler, wait_for_tts_wav()

### Community 45 - "synthesize_speech"
Cohesion: 0.22
Nodes (11): convert_24k_mono_to_16k_stereo_wav(), Converts 24kHz mono 16-bit PCM WAV to 16kHz stereo 16-bit PCM WAV for ESP32 I2S., Prepare text for TTS pronunciation and ensure optimal generation length., Generate audio via Voicebox and format for ESP32 playback., Generates 16kHz stereo WAV using Windows SAPI (instant offline fallback)., Generates 16kHz stereo WAV using Voicebox (primary) or Windows SAPI (instant…, resolve_voicebox_profile_id(), sanitize_for_tts() (+3 more)

### Community 46 - "drawStorageExplorer"
Cohesion: 0.29
Nodes (7): String, drawStorageExplorer, drawStorageListOnly, navigateStorageTo, navigateStorageUp, refreshStorageExplorer, scrollStorageList

### Community 47 - "ask_fast_llm"
Cohesion: 0.31
Nodes (10): answer_agent_lane(), answer_fast_lane(), ask_fast_llm(), history_messages(), query_ollama_fallback(), Answers directly via Groq's OpenAI-compatible API (no agent, no tools)., Fast lane: Groq (if enabled), then warm local Ollama, then the Hermes agent., Agent lane: Hermes with tools; if it fails, a fast model answers and says tools… (+2 more)

### Community 48 - "Pinout Reference"
Cohesion: 0.22
Nodes (8): Additional Peripherals, Audio System (ES8311 Codec: 0x18 & FM8002 Amplifier), Capacitive Touch (FT6336G — I2C: 0x38), Display (2.8-inch 240×320 IPS SPI), ES3C28P hardware reference, Hardware Overview & Board Identification, Mechanical files, Pinout Reference

### Community 49 - "_groq_request"
Cohesion: 0.25
Nodes (9): _groq_headers(), _groq_request(), One request over a persistent TLS connection (reconnects once if Groq dropped…, Validates the Groq key and opens the TLS connection before the first voice turn., Groq Whisper STT over the same persistent TLS connection as the fast lane., Returns (transcript, stt_provider). Groq first when enabled, then local Whisper., transcribe_audio(), transcribe_with_groq() (+1 more)

### Community 50 - "ask_hermes_gateway"
Cohesion: 0.25
Nodes (8): ask_hermes_gateway(), get_voice_session_id(), _hermes_sessions_headers(), _hermes_voice_overrides(), load_voice_session(), Return the durable voice session ID, creating the session if needed., Cached durable session ID, so each voice turn skips the session lookup round…, Dispatches prompt to persistent Hermes Gateway via HTTP.

### Community 51 - "get_composite_status"
Cohesion: 0.29
Nodes (7): check_voicebox_online(), get_composite_status(), probe_hermes_health(), probe_ollama_health(), Probes local Ollama for service reachability and model VRAM residency., Returns composite health authority state, cached for 2.5 seconds to minimize…, Probes Hermes Gateway for liveness and detailed readiness.

### Community 52 - "queue_lazy_tts"
Cohesion: 0.33
Nodes (6): queue_lazy_tts(), _run(), Asynchronously speaks text out loud on the host computer's speakers., Start TTS in the background so the JSON reply can leave before audio is ready., speak_on_host_speaker(), _run()

### Community 53 - "ComposeCompanion"
Cohesion: 0.16
Nodes (11): KeyboardEvent, ComposeCompanion, F13 Pressed: Begin Compose recording., F13 Released: Stop recording and dispatch Compose pipeline., F14 Pressed: Begin Dictate recording., F14 Released: Stop recording and dispatch Dictate pipeline., F15 Tapped: Inject pending payload if in READY status., Global keyboard hook dispatcher. (+3 more)

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
Cohesion: 0.15
Nodes (8): load_env_config(), Loads configuration from compose.env and system environment., LlmPipeline, Calls Groq chat completions endpoint. Returns (content, finish_reason)., Calls local Ollama chat completions endpoint. Returns (content, finish_reason)., Executes LLM generation with automatic multi-round continuation if length…, Cleans up any stray markdown fences or quotes that models occasionally wrap…, sanitize_plain_text()

### Community 58 - "AudioCapture"
Cohesion: 0.15
Nodes (7): ndarray, AudioCapture, find_default_wasapi_input_device(), Audio capture module using sounddevice and WASAPI for high-fidelity PC…, Starts recording audio from the PC microphone via WASAPI., Stops recording and returns: (wav_bytes_16khz, duration_seconds, rms_level), Finds the default Windows WASAPI recording device and its native sample rate.

### Community 59 - "SpeechPipeline"
Cohesion: 0.31
Nodes (4): Uploads WAV bytes to Groq Whisper endpoint., Transcribes WAV bytes via local faster-whisper., Transcribes audio bytes. Returns: (transcript, provider_used, latency_seconds), SpeechPipeline

### Community 60 - ".run"
Cohesion: 0.22
Nodes (6): Image, open_config_action(), paste_ready_action(), toggle_local_only(), create_tray_icon_image(), Creates a tray icon with amber/emerald indicator dot.

### Community 61 - "5. Set up the optional voice receiver"
Cohesion: 0.50
Nodes (4): 5. Set up the optional voice receiver, Check network reachability, Install Python dependencies, Select the AI route explicitly

### Community 62 - "ComposeApp"
Cohesion: 0.16
Nodes (7): Tk, Attempts to open the Windows clipboard with retries in case another process…, Safely retrieves current text in clipboard if available., Injects text at the current cursor position: 1. Snapshots prior clipboard. 2.…, ComposeApp, load_env_config(), Polls for hardware hotkeys sent by the ESP32 MacroPad or physical PC keyboard:…

### Community 63 - "_coeff_div"
Cohesion: 0.15
Nodes (13): _coeff_div, adc_div, adc_osr, bclk_div, dac_div, dac_osr, fs_mode, lrck_h (+5 more)

### Community 64 - "6. Connect Blender MCP"
Cohesion: 0.50
Nodes (4): 6. Connect Blender MCP, Codex, Cursor, Verify the connection

## Knowledge Gaps
- **295 isolated node(s):** `start_receiver.sh script`, `count`, `minVal`, `maxVal`, `sum` (+290 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 469 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MacroPadGUI` connect `MacroPadGUI` to `gui.cpp`, `gui.h`, `drawDashboard`, `main.cpp`, `redrawVoiceCard`, `drawStorageExplorer`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `ComposeCompanion` (e.g. with `AudioCapture` and `ClipboardManager`) actually correct?**
  _`ComposeCompanion` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `start_receiver.sh script`, `count`, `minVal` to the rest of the system?**
  _295 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `MacroPadGUI` be split into smaller, more focused modules?**
  _Cohesion score 0.09090909090909091 - nodes in this community are weakly interconnected._
- **Should `EnvironmentManager` be split into smaller, more focused modules?**
  _Cohesion score 0.07641196013289037 - nodes in this community are weakly interconnected._
- **Should `AudioRecorder` be split into smaller, more focused modules?**
  _Cohesion score 0.05142857142857143 - nodes in this community are weakly interconnected._
- **Should `network_manager.cpp` be split into smaller, more focused modules?**
  _Cohesion score 0.12941176470588237 - nodes in this community are weakly interconnected._