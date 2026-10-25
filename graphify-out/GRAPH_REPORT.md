# Graph Report - ESP32 project  (2026-10-25)

## Corpus Check
- 250 files · ~1,361,547 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3906 nodes · 8773 edges · 189 communities (156 shown, 20 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 736 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `14664785`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- MacroPadGUI
- hermes_voice_receiver.py
- EnvironmentManager
- AudioRecorder
- network_manager.cpp
- sd_card.cpp
- es8311_bsp.c
- es8311.cpp
- 2026-10-21-companion-media-agent-master-plan.md
- create_enclosure
- bench_llm_paths.py
- HermesService
- start_receiver.sh
- Dashboard-plan.md
- HistoryStore
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
- media_library_server.py
- generate_case_battery_only.py
- test_assistant_service.py
- ChatLine
- drawDashboard
- ESP32_Classroom_Companion_OneNote_Automation_Plan.md
- ESP32 & Windows Compose / Dictate Companion: Architecture & Implementation Plan
- MediaPanel
- Detailed build guide
- Build an ESP32 classroom companion with an AI coding agent
- compose_companion.py
- .do_POST
- synthesize_speech
- GuardTests
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
- SyncClient
- install_media_service.py
- test_board_resource_policy.py
- MediaService
- test_compose.py
- board_trial.py
- ProviderFailure
- test_board_agent.py
- test_image_provider_routing.py
- MediaStore
- test_board_runtime.py
- test_device_feedback.py
- test_gemini_images.py
- test_board_agent_ui.py
- companion_settings.py
- 2026-10-24-gemini-image-provider-plan.md
- 2026-10-25-development-workboard.md
- Image providers: Gemini first
- Classroom companion: consolidated branch programme
- ClientTests
- ResourceCatalogue
- HermesPanel
- board_candidate.py
- Project documentation index
- ComposeApp
- FocusTracker
- ProbeState
- Board upload safety
- ChannelStats
- _coeff_div
- linux_hermes_client.py
- build_companion_preview.py
- test_media_targets.py
- service
- BoardCandidate
- src/main.cpp
- load_env_config
- Create & Paste: approved page 7 device trial
- Three practical routes
- Companion development workboard — 25 October 2026
- Teaching Board: agreed design and development plan
- Hermes readiness — 25 October 2026
- SolidCraft enclosure and MCP investigation
- BoardSession
- test_board_hermes.py
- Bridge
- AudioCapture
- VoiceReceiver
- State
- BoardAgentError
- BoardStore
- test_board_export.py
- media_targets.py
- copy_saved_lesson
- SavedImageLibrary
- SettingsPanel
- test_board_editor_ux.py
- LazyStartTests
- ValueError
- SDCardStatus
- cyd_identifier/src/main.cpp
- test_media_store.py
- test_companion_package.py
- test_media_gui_integration.py
- test_board_image_insertion.py
- AgentPanel
- media_backup.py
- Teaching Board manual feedback — 25 October 2026
- An assistant built into the desktop companion
- compose_gui.py
- Making the classroom companion accessible
- Adoption and onboarding research: ESP32 classroom presentation companion
- BoardCanvas
- MigrationTests
- Windows Compose and Dictate repair — 17 October 2026
- Authorised Hermes consultation
- Hermes and companion orchestration investigation
- forward_transcript
- Consultation lessons
- Image companion feature: testing and recovery
- Permanent Hermes connection over Tailscale
- Media library and insertion workflow investigation
- Media library sync investigation
- Hermes integration development checkpoint
- Embedded companion assistant: first working increment
- FakeHermesService
- Companion Linux deployment tools
- Embedded assistant architecture review
- Image provider investigation: classroom companion
- main
- Linux Hermes collaboration
- Image feature implementation record
- End-of-day checkpoint — 24 October 2026
- Private media sync service
- StageMediaTests
- Home/work architecture
- Further identification and reversible diagnostic
- Install and recover the isolated desktop preview
- whisper_worker.py
- pinout_allocation_f58fa43e.md
- test_board_resize.py
- Teaching Board: reusable lesson-resource library and agent memory
- MediaServerPortableTests
- safe_path
- School arrival guide: Teaching Board and the Linux Hermes
- make_data
- Teaching Board agent and reusable resource library: implementation plan
- ._index
- media_store.py
- create_server
- Board agent: delegated operating defaults
- MediaRequestHandler
- .__init__
- Handler
- School readiness: delivered Windows branch and permanent Linux Hermes route
- Linux Hermes school handoff
- _stub_dependency_wheel
- Teaching Board agent and reusable library candidate
- test_fake_microphone_transcribes_only_after_explicit_gesture_and_requires_send
- Teaching Board saved-lesson discovery — 25 October 2026
- Licensing recommendation for the ESP32 classroom companion
- setup_teaching_board_candidate.ps1
- QGraphicsView

## God Nodes (most connected - your core abstractions)
1. `MediaStore` - 113 edges
2. `ComposeApp` - 96 edges
3. `BoardSession` - 79 edges
4. `MacroPadGUI` - 76 edges
5. `new_object()` - 60 edges
6. `BoardModel` - 59 edges
7. `BoardCandidate` - 52 edges
8. `HermesService` - 52 edges
9. `BoardAgentError` - 51 edges
10. `BoardStore` - 49 edges

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

## Communities (189 total, 20 thin omitted)

### Community 0 - "MacroPadGUI"
Cohesion: 0.06
Nodes (61): String, VoiceUIState, HealthState, VoiceUIState, MacroPadGUI, addVoiceTurn, canScrollDown, canScrollUp (+53 more)

### Community 1 - "hermes_voice_receiver.py"
Cohesion: 0.14
Nodes (19): _env(), get_local_ip_for_target(), get_voice_session_id(), get_whisper_model(), _hermes_sessions_headers(), load_voice_session(), main(), Hermes Voice Satellite Receiver Service (Concurrent Health Authority… (+11 more)

### Community 2 - "EnvironmentManager"
Cohesion: 0.08
Nodes (40): SemaphoreHandle_t, EnvironmentChangeCallback, EnvironmentMode, String, EnvironmentManager, begin, _changeCallback, _currentMode (+32 more)

### Community 3 - "AudioRecorder"
Cohesion: 0.07
Nodes (27): AudioRecorder, begin, _lastRecordDurationMs, _leftStats, logDiagnostics, _maxLeftPeak, _maxRightPeak, _monoStats (+19 more)

### Community 4 - "network_manager.cpp"
Cohesion: 0.08
Nodes (48): IPAddress, String, HostDiscovery, begin, checkBeacon, discoverNow, _lastBeaconCheck, _lastDiscoveryAttempt (+40 more)

### Community 5 - "sd_card.cpp"
Cohesion: 0.16
Nodes (24): sdcard_type_t, refreshStorageExplorer, goToSoftOff(), handleCreateTouch(), loop(), setLedColor(), setup(), waitTouchRelease() (+16 more)

### Community 6 - "es8311_bsp.c"
Cohesion: 0.23
Nodes (25): es8311_clock_config_t, es8311_handle_t, es8311_mic_gain_t, es8311_resolution_t, esp_err_t, i2c_port_t, es8311_clock_config(), es8311_create() (+17 more)

### Community 7 - "es8311.cpp"
Cohesion: 0.25
Nodes (26): es8311_clock_config_t, es8311_handle_t, es8311_mic_gain_t, es8311_resolution_t, esp_err_t, i2c_port_t, es8311_clock_config(), es8311_codec_dump_registers() (+18 more)

### Community 8 - "2026-10-21-companion-media-agent-master-plan.md"
Cohesion: 0.18
Nodes (4): Current programme, Project instructions, Portrait UI — guarded build and recovery guide, CYD identification diagnostic

### Community 10 - "bench_llm_paths.py"
Cohesion: 0.06
Nodes (36): HTTPError, HTTPResponse, Adapter, build_adapters(), build_messages(), count_lines(), count_sentences(), expand_placeholders() (+28 more)

### Community 11 - "HermesService"
Cohesion: 0.06
Nodes (30): _canonical(), _clean_text(), _config_bool(), _extract_text(), HermesHTTPError, HermesService, HermesServiceError, HermesTransportError (+22 more)

### Community 15 - "Dashboard-plan.md"
Cohesion: 0.05
Nodes (36): MacroPad readiness, Phase 0 — Protect what currently works, Phase 10 — Define proper status semantics, Phase 11 — Separate Macro readiness from Voice readiness, Phase 12 — Wi-Fi health information, Phase 13 — Add a genuine Internet test, Phase 14 — Avoid dashboard probes interfering with voice, Phase 15 — Make the Python receiver concurrent (+28 more)

### Community 16 - "HistoryStore"
Cohesion: 0.06
Nodes (37): Misc, _default_database_path(), HistoryStore, Any, Connection, Path, Row, Persistent, text-only history for the classroom companion. (+29 more)

### Community 17 - "ESP32 Portable MacroPad & Hermes Satellite: Core Engineering Rules"
Cohesion: 0.14
Nodes (14): ESP32 Portable MacroPad & Hermes Satellite: Core Engineering Rules, Rule 10: Safe Cross-Core Concurrency & Bounded Touch Debounce, Rule 11: Dual-Path Audio Output & Non-Blocking TTS Fallback, Rule 12: Wi-Fi/BLE Coexistence & AP NVS Cache Sanitation, Rule 13: Gateway Tiering & Zero-Zombie Receiver Daemon Semantics, Rule 1: Strict Environment Binding (The Composite Profile Rule), Rule 2: Host ownership and explicit backend routing, Rule 3: Asynchronous Receiver Concurrency (The Audio Lock Rule) (+6 more)

### Community 22 - "test_web_grounding.py"
Cohesion: 0.07
Nodes (35): Unit tests for web_grounding (keyword router, Jev/Groq model router, Brave…, test_brave_search_client_parses_results(), test_build_search_query_strips_command_prefix(), test_format_search_context(), test_intent_router_jev_ambiguous_triggers_api(), test_intent_router_jev_failure_falls_back_to_groq(), test_intent_router_jev_success(), test_intent_router_total_failure_degrades_gracefully() (+27 more)

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
Cohesion: 0.08
Nodes (26): 1. Goal, 2. Hardware facts that constrain the design, 3.1 Product UI (this part works), 3.2 Attempt A — ESP32 deep sleep + EXT1 on GPIO17, 3.3 Attempt B — Deep sleep, but put touch on EXT0, 3.4 Attempt C — Light sleep + GPIO wakeup + 150 ms I2C poll, 3.5 Attempt D — No sleep at all; poll I2C like the GUI (current flash), 3. What we implemented (and what you saw) (+18 more)

### Community 33 - "media_library_server.py"
Cohesion: 0.20
Nodes (11): ApiError, _image_info(), _json_bytes(), MediaLibrary, Any, Exception, Path, Private, single-host media library sync API. The service is intentionally small… (+3 more)

### Community 34 - "generate_case_battery_only.py"
Cohesion: 0.21
Nodes (26): add_cube(), add_cylinder(), add_standoffs(), add_through_bolts(), apply_boolean(), build_battery(), build_case_bottom(), build_case_top() (+18 more)

### Community 35 - "test_assistant_service.py"
Cohesion: 0.05
Nodes (53): AssistantPanel, Embedded assistant UI; all Tk operations stay on the main thread., AssistantService, Any, Event, Bounded conversational assistant for the desktop companion. The model may…, Accept only bounded user/assistant text; caller roles/tools are ignored., LLM generation pipeline with Groq high-speed cloud generation, local Ollama… (+45 more)

### Community 36 - "ChatLine"
Cohesion: 0.14
Nodes (13): ChatLine, color, text, ChatMessage, isUser, text, TFT_eSPI, vector (+5 more)

### Community 37 - "drawDashboard"
Cohesion: 0.31
Nodes (9): DashboardStatus, EnvironmentMode, HealthState, drawDashboard, drawDashboardPowerButton, drawDashboardVolume, drawStatusBar, drawStatusRow (+1 more)

### Community 38 - "ESP32_Classroom_Companion_OneNote_Automation_Plan.md"
Cohesion: 0.05
Nodes (42): 10. Classroom Companion Command Model, 11. Do Not Hard-Code OneNote Page IDs into Firmware, 12. Dynamic Button Configuration, 13. Lesson Scenes, 14. Windows Companion Providers, 15. Proposed ESP32 Firmware Extension, 16. Reuse Existing ESP32 Networking, 17. Security Model (+34 more)

### Community 39 - "ESP32 & Windows Compose / Dictate Companion: Architecture & Implementation Plan"
Cohesion: 0.07
Nodes (27): 1. Executive Summary, 2.1 Page Allocation & Layout, 2.2 Button Configuration (`src/macropad_config.cpp`), 2.3 Main Loop Hold Logic & Rule 10 Safety Timeout, 2. Firmware Extension (ESP32-S3), 3.1 Architecture & Process Model, 3.2 Hotkey Interception (`F13`–`F15`), 3. Windows Background Companion (`tools/compose/`) (+19 more)

### Community 40 - "MediaPanel"
Cohesion: 0.10
Nodes (15): request(), main(), Path, Inspect and explicitly stage the media service deployment bundle., _sha256(), stage(), MediaPanel, apply() (+7 more)

### Community 41 - "Detailed build guide"
Cohesion: 0.11
Nodes (19): 1. Install the tools, 2. Open the repository and give the agent context, 3. Connect the board, build and upload, 4. Test and customise Bluetooth, 5. Set up the optional voice receiver, 6. Connect Blender MCP, 7. Refine the enclosure and print it, 8. Use a repeatable development loop (+11 more)

### Community 42 - "Build an ESP32 classroom companion with an AI coding agent"
Cohesion: 0.13
Nodes (15): 1. Download and open the project, 2. Connect the ESP32 over USB, 3. Configure, build and upload, 4. Pair Bluetooth and try a shortcut, 5. Make a small change with your IDE agent, 6. Connect Blender MCP and refine the case, 7. Add voice once the basic device works, 8. Test, print and keep improving (+7 more)

### Community 43 - "compose_companion.py"
Cohesion: 0.06
Nodes (25): Image, ComposeCompanion, paste_ready_action(), toggle_local_only(), create_tray_icon_image(), ESP32 & Windows Voice Compose & Dictate Companion Service Resides in the…, F13 Pressed: Begin Compose recording., F13 Released: Stop recording and dispatch Compose pipeline. (+17 more)

### Community 44 - ".do_POST"
Cohesion: 0.23
Nodes (8): BaseHTTPRequestHandler, Phase 20: Validate Authorization: Bearer <VOICE_RECEIVER_TOKEN> if configured., Strips markdown and unsupported characters for clean display on ST7789 TFT…, Returns 'agent' for tool/action/live-data requests, otherwise 'fast'., route_intent(), sanitize_for_display(), VoiceRequestHandler, wait_for_tts_wav()

### Community 45 - "synthesize_speech"
Cohesion: 0.22
Nodes (11): convert_24k_mono_to_16k_stereo_wav(), Converts 24kHz mono 16-bit PCM WAV to 16kHz stereo 16-bit PCM WAV for ESP32 I2S., Prepare text for TTS pronunciation and ensure optimal generation length., Generate audio via Voicebox and format for ESP32 playback., Generates 16kHz stereo WAV using Windows SAPI (instant offline fallback)., Generates 16kHz stereo WAV using Voicebox (primary) or Windows SAPI (instant…, resolve_voicebox_profile_id(), sanitize_for_tts() (+3 more)

### Community 46 - "GuardTests"
Cohesion: 0.09
Nodes (3): FakeConnection, GuardTests, partition_table()

### Community 47 - "ask_fast_llm"
Cohesion: 0.18
Nodes (17): answer_agent_lane(), answer_fast_lane(), ask_fast_llm(), ask_hermes_gateway(), groq_should_try(), hermes_reachable(), _hermes_voice_overrides(), history_messages() (+9 more)

### Community 48 - "Pinout Reference"
Cohesion: 0.25
Nodes (8): Additional Peripherals, Audio System (ES8311 Codec: 0x18 & FM8002 Amplifier), Capacitive Touch (FT6336G — I2C: 0x38), Display (2.8-inch 240×320 IPS SPI), ES3C28P hardware reference, Hardware Overview & Board Identification, Mechanical files, Pinout Reference

### Community 49 - "warmup_fast_llm"
Cohesion: 0.20
Nodes (11): _groq_headers(), _groq_network_failure(), _groq_request(), mark_groq_unreachable(), Exception, School networks often block Groq. Don't pay the connect timeout on every…, One request over a persistent TLS connection (reconnects once if Groq dropped…, Validates the Groq key and opens the TLS connection before the first voice turn. (+3 more)

### Community 50 - "test_media_providers.py"
Cohesion: 0.15
Nodes (16): FakeResponse, FakeSession, openai_response(), png_bytes(), parametrize, test_commons_download_rejects_oversized_stream(), test_commons_download_requires_explicit_rights_acknowledgement_without_network(), test_commons_download_uses_https_wikimedia_and_bounded_no_redirect_request() (+8 more)

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
Nodes (7): LlmPipeline, Executes LLM generation with automatic multi-round continuation if length…, Calls Groq chat completions endpoint. Returns (content, finish_reason)., Calls local Ollama chat completions endpoint. Returns (content, finish_reason)., Cleans up any stray markdown fences or quotes that models occasionally wrap…, sanitize_plain_text(), test_ollama_uses_installed_model_when_configured_model_is_missing()

### Community 58 - "BoardModel"
Cohesion: 0.10
Nodes (37): Save an applied page as one immutable local resource with exact image links., BoardModel, BoardValidationError, canonical_json(), _colour(), _id(), _keys(), new_lesson() (+29 more)

### Community 59 - "SpeechPipeline"
Cohesion: 0.11
Nodes (15): cuda_runtime_usable(), is_cloud_network_failure(), Exception, Speech-to-Text (STT) pipeline with Groq cloud Whisper-large-v3-turbo and local…, Uploads WAV bytes to Groq Whisper endpoint., Transcribes WAV bytes via local faster-whisper., Transcribes audio bytes. Returns: (transcript, provider_used, latency_seconds), True when a cloud call failed because the network blocked or dropped it. (+7 more)

### Community 60 - "SyncClient"
Cohesion: 0.08
Nodes (22): _CommonsLicenceBlockParser, _LazyMediaService, HTMLParser, Collect licence links from a file's structured licence template., Defer optional HTTP dependencies until a teacher requests acquisition., Any, RuntimeError, Authenticated, retry-safe media sync client for MediaStore. (+14 more)

### Community 61 - "install_media_service.py"
Cohesion: 0.07
Nodes (35): CompletedProcess, apply_install(), _atomic_json(), _check_instance(), _check_venv_security(), _copy_sources(), _has_symlink_component(), _is_root() (+27 more)

### Community 62 - "test_board_resource_policy.py"
Cohesion: 0.06
Nodes (54): _atomic_json(), BoardRequestAcquisition, _canonical(), ChartArtifact, _create_claim(), _date_field(), format_attribution(), _https_url() (+46 more)

### Community 63 - "MediaService"
Cohesion: 0.09
Nodes (10): CommonsRetriever, Explicit Commons search; a result's visibility does not grant reuse rights., MediaService, Explicit accounting-only retry for a saved image with a lost ledger ACK., truthy(), test_google_is_explicit_and_never_borrows_openai_allocation_or_falls_back(), test_restart_keeps_frozen_choice_allocation_and_single_dispatch(), parametrize (+2 more)

### Community 64 - "test_compose.py"
Cohesion: 0.10
Nodes (24): HotkeyState, One edge dispatcher for the firmware's held keys, used by both companions., make_app(), Regression checks without recording, network requests or desktop keystrokes., test_busy_pipeline_rejects_new_recording(), test_cached_descriptor_standard_chord_survives_modifier_release(), test_changed_focus_keeps_result_ready_without_paste(), test_dictation_survives_unavailable_cleanup_provider() (+16 more)

### Community 65 - "board_trial.py"
Cohesion: 0.07
Nodes (35): Guarded upload entry point. Implicit ports and unverified demo bins are…, check_port(), EspConnection, guarded_upload(), load_manifest(), load_registry(), main(), profile_for() (+27 more)

### Community 66 - "ProviderFailure"
Cohesion: 0.13
Nodes (19): error_diagnostics(), GeminiImageProvider, Path, Stateless Gemini Interactions image requests. No retries, fallback or URL…, Read bounded error metadata and a redacted summary, never raw response bodies., ProviderFailure, Path, RuntimeError (+11 more)

### Community 67 - "test_board_agent.py"
Cohesion: 0.10
Nodes (62): Useful for a deterministic local composer and offline fixtures; no authority., result_envelope(), new_object(), prepared(), apply(), board(), chart_record(), complete() (+54 more)

### Community 68 - "test_image_provider_routing.py"
Cohesion: 0.11
Nodes (26): Protocol, create_image_provider(), image_readiness(), image_snapshot(), ImageCapabilities, ImageProvider, Path, Image producer contract and local request snapshots; never contains credentials. (+18 more)

### Community 70 - "MediaStore"
Cohesion: 0.11
Nodes (17): _json(), MediaStore, _now(), Any, Connection, Path, Row, Claim a durable attempt across processes without replacing another owner. (+9 more)

### Community 71 - "test_board_runtime.py"
Cohesion: 0.07
Nodes (35): BoardResourceLibrary, Search bounded reusable resource types for the Board chooser., BoardResourcePreparer, Search/acquire a required visual before the composition worker runs., Trust a source override only when the teacher actually named it., Explicit teacher action to reconcile one durable prior paid job., commons_candidate(), context() (+27 more)

### Community 72 - "test_device_feedback.py"
Cohesion: 0.10
Nodes (20): DeviceFeedback, display_text(), frame(), Opt-in, identity-bound USB display feedback. No recording/insertion/provider…, Call only from Tk. Never send a transcript, document text or credential., snapshot(), parametrize, Safe feedback, explicit hotkeys and preservation of pending work. (+12 more)

### Community 73 - "test_gemini_images.py"
Cohesion: 0.15
Nodes (26): check_google_model(), Explicit metadata GET only. Never invoke this during startup/save/setup., make_service(), parametrize, Offline transport, final-output parsing and complete durable Gemini workflows., The live endpoint rejects explicit delivery despite its OpenAPI enum., session(), test_actual_delivery_mode_rejection_is_avoided_for_generation_and_refinement() (+18 more)

### Community 74 - "test_board_agent_ui.py"
Cohesion: 0.05
Nodes (40): app(), editor(), FakeComposer, FakePreparer, generated_image(), png_bytes(), fixture, parametrize (+32 more)

### Community 75 - "companion_settings.py"
Cohesion: 0.09
Nodes (35): atomic_write(), authenticated_get(), main(), NoRedirect, Path, Safely validate and switch the development client's private Hermes origin., _read_json(), readiness() (+27 more)

### Community 76 - "2026-10-24-gemini-image-provider-plan.md"
Cohesion: 0.07
Nodes (27): Established diagnostic defect, First real Gemini attempt: rejected request and diagnostic correction, Offline request-contract check, Real setup and attempt, Verification and delivery, Actual twelve-attempt result, Durable evidence and recovery, Failure and correction (+19 more)

### Community 77 - "2026-10-25-development-workboard.md"
Cohesion: 0.12
Nodes (13): Available teaching actions, Local verification and remaining acceptance, Run and reopen, Teaching Board: isolated B2 desktop candidate, Persistence and editing boundaries, Teacher workflow, Teaching Board image insertion — 25 October 2026, Verification and remaining acceptance (+5 more)

### Community 78 - "Image providers: Gemini first"
Cohesion: 0.18
Nodes (11): Delivery and first action, Existing foundation and necessary changes, Gemini adapter and first settings, Image providers: Gemini first, Intended result, Ordered delivery, Provider contract and durable jobs, Spending and data boundaries (+3 more)

### Community 79 - "Classroom companion: consolidated branch programme"
Cohesion: 0.20
Nodes (10): Approved desktop Teaching Board workstream, Architecture and ownership, Choices and release conditions, Classroom companion: consolidated branch programme, Completion dashboard, Current implementation and verification limits, Ordered delivery backlog, Outcome and fixed decisions (+2 more)

### Community 81 - "ResourceCatalogue"
Cohesion: 0.09
Nodes (35): Connection, Row, _clean_text(), _json_object(), _now(), Any, Path, Local typed, versioned catalogue for reusable Teaching Board resources. This… (+27 more)

### Community 82 - "HermesPanel"
Cohesion: 0.09
Nodes (17): is_catalogue_context(), HermesPanel, Stage a visibly selected catalogue; the existing Send action remains explicit., parametrize, Native regression: Hermes actions must remain usable at supported sizes., test_all_hermes_actions_fit_inside_nested_notebook(), save_panel(), test_busy_submit_keeps_same_request_retry_handle() (+9 more)

### Community 83 - "board_candidate.py"
Cohesion: 0.08
Nodes (24): candidate_directory(), demo_model(), image_resolver(), load_board_settings(), main(), Experimental, isolated Qt Teaching Board candidate with opt-in agent services.…, Actual session/store and synthetic commands; no physical-input acceptance., An explicitly selected profile must be readable on this Windows account. Do not… (+16 more)

### Community 84 - "Project documentation index"
Cohesion: 0.50
Nodes (4): Completion language, Current plans and operating guides, Implementation and historical evidence, Project documentation index

### Community 85 - "ComposeApp"
Cohesion: 0.07
Nodes (13): Tk, ComposeApp, sync_worker(), rollback(), load_env_config(), A blocked school network should not add a cloud timeout to every later button…, truthy(), HWND/title/pid only. Safe to call from the hotkey poller. (+5 more)

### Community 86 - "FocusTracker"
Cohesion: 0.10
Nodes (23): ClipboardManager, Injects text at the current cursor position: 1. Snapshots prior clipboard. 2.…, Attempts to open the Windows clipboard with retries in case another process…, Safely retrieves current text in clipboard if available., Safely empties the Windows clipboard., Safely sets Unicode text on the Windows clipboard., FocusTracker, _key_event() (+15 more)

### Community 87 - "ProbeState"
Cohesion: 0.06
Nodes (19): QWidget, exercise(), identity(), image_bytes(), lesson(), obj(), ProbeState, THROWAWAY B0 fixture. Memory only; never opens user lessons or media stores. (+11 more)

### Community 88 - "Board upload safety"
Cohesion: 0.25
Nodes (8): Board upload safety, Build and check without writing, Historical CYD diagnostic upload route, Registered hardware and roles, S3 trial approval gate, Scoped S3 application trial and recovery, Verification, Verified on 21 October 2026

### Community 89 - "ChannelStats"
Cohesion: 0.14
Nodes (8): ChannelStats, clipCount, count, maxVal, minVal, nonZeroCount, sum, sumSq

### Community 90 - "_coeff_div"
Cohesion: 0.15
Nodes (13): _coeff_div, adc_div, adc_osr, bclk_div, dac_div, dac_osr, fs_mode, lrck_h (+5 more)

### Community 91 - "linux_hermes_client.py"
Cohesion: 0.18
Nodes (24): api_call(), ApiStatus, approve(), bind_dispatch_identity(), check_run_id(), event_name(), events(), exclusive_json() (+16 more)

### Community 92 - "build_companion_preview.py"
Cohesion: 0.67
Nodes (3): build(), Build an allowlisted source preview without credentials or private reports., source_files()

### Community 93 - "test_media_targets.py"
Cohesion: 0.18
Nodes (20): setter, app_target(), keyboard_target(), parametrize, Range, test_explicit_onenote_paste_rechecks_context_after_copy(), test_explicit_onenote_paste_refuses_noncanvas_focus(), test_explicit_onenote_paste_rejects_changed_canvas_or_page_before_copy() (+12 more)

### Community 94 - "service"
Cohesion: 0.23
Nodes (15): test_cross_provider_refinement_requires_deliberate_transfer(), test_legacy_undispatched_job_requires_repreparation(), test_missing_prepared_reference_never_becomes_unreferenced_generation(), test_snapshot_and_sync_payload_never_contain_keys(), png(), parametrize, service(), test_accounting_ack_failure_keeps_durable_image() (+7 more)

### Community 95 - "BoardCandidate"
Cohesion: 0.14
Nodes (7): BoardCandidate, decode_image(), Discovery failures are separate from successful durable lesson saves., One pinned add command, with bytes durable before document publication., Compatibility entry point; editing widgets now schedule this automatically., Explicitly discard a stale form draft and load the current object., Commit the captured draft, or retain it and refuse the dependent action.

### Community 96 - "src/main.cpp"
Cohesion: 0.15
Nodes (12): MacroButton, Preferences, TFT_eSPI, vector, calculateBatteryPercentage(), companionCommand(), HealthState, String (+4 more)

### Community 97 - "load_env_config"
Cohesion: 0.19
Nodes (14): fallback_env_paths(), load_env_config(), _merge_nonempty(), _parse_env_file(), Path, Shared companion settings. Cloud keys may live in compose.env, server/.env, or…, Load Groq fallbacks, Compose, protected feature settings, then process…, test_env_loader_reuses_hermes_groq_key_when_compose_env_is_empty() (+6 more)

### Community 98 - "Create & Paste: approved page 7 device trial"
Cohesion: 0.40
Nodes (5): Attached feedback, Candidate, Create & Paste: approved page 7 device trial, Live result, Recovery and verification before writing

### Community 99 - "Three practical routes"
Cohesion: 0.25
Nodes (8): Durable lessons and transactional undo, Integration, packaging and licence audit, Next decision and later prototype evidence, Pen, touch and ink, Settled needs and unresolved choices, Teacher and pupil windows, Teaching-board renderer options, Three practical routes

### Community 100 - "Companion development workboard — 25 October 2026"
Cohesion: 0.17
Nodes (12): Companion development workboard — 25 October 2026, Decisions already settled, Evidence and acceptance ledger, Later participant Teaching Board feedback, Latest agent/library build checkpoint, Open decisions and facts to establish, Saved-lesson discovery follow-up, School-readiness follow-up (+4 more)

### Community 101 - "Teaching Board: agreed design and development plan"
Cohesion: 0.29
Nodes (7): Agreed implementation increments, Capability boundary, Decision register, First accepted lesson scenario, Outcome and design tree, Teaching Board: agreed design and development plan, Technical options, still open

### Community 102 - "Hermes readiness — 25 October 2026"
Cohesion: 0.33
Nodes (6): Acceptance remains open, Environment distinction, Exact remaining transport blocker, Hermes readiness — 25 October 2026, Later school-readiness inspection on 25 October, Today's observations

### Community 103 - "SolidCraft enclosure and MCP investigation"
Cohesion: 0.11
Nodes (15): Capabilities and migration, MCP connection to the visible desktop, Pilot acceptance, Recommendation, SolidCraft enclosure and MCP investigation, Dimension and feature matrix, Enclosure dimension and feature reconciliation, Evidence and coordinate basis (+7 more)

### Community 104 - "BoardSession"
Cohesion: 0.11
Nodes (27): BoardAuthorityError, BoardMediaError, BoardSession, BoardSessionError, BoardSessionSaveError, RuntimeError, Local teacher/pupil authority, atomic presentation and explicit autosave…, Capture the editable lesson/history without transient display state. (+19 more)

### Community 105 - "test_board_hermes.py"
Cohesion: 0.15
Nodes (43): apply_result(), BoardConfirmationRequired, BoardProposalError, _manifest(), _nonfinite(), _pairs(), _parse(), prepare_request() (+35 more)

### Community 106 - "Bridge"
Cohesion: 0.23
Nodes (8): Bridge, forward(), discover(), listening(), main(), open_window(), Discover MCP tools quietly; open the visible CAD app on the first real request., Use a short-lived CLI, never the GUI, to obtain this installation's schemas.

### Community 107 - "AudioCapture"
Cohesion: 0.13
Nodes (7): ndarray, AudioCapture, find_default_wasapi_input_device(), Audio capture module using sounddevice and WASAPI for high-fidelity PC…, Starts recording audio from the PC microphone via WASAPI., Stops recording and returns: (wav_bytes_16khz, duration_seconds, rms_level), Finds the default Windows WASAPI recording device and its native sample rate.

### Community 108 - "VoiceReceiver"
Cohesion: 0.18
Nodes (10): Path, Runs the Hermes voice receiver as a child of the desktop companion., VoiceReceiver, Path, The companion starts the voice receiver without duplicating one that is already…, _service(), test_start_launches_the_receiver_script(), test_start_leaves_an_existing_receiver_alone() (+2 more)

### Community 109 - "State"
Cohesion: 0.19
Nodes (12): Action, State, active, down, latched, started, swallowed, Step (+4 more)

### Community 110 - "BoardAgentError"
Cohesion: 0.10
Nodes (27): BoardValidationError, BoardAgentCancelled, BoardAgentController, report(), BoardAgentError, _effective(), _images(), load_profile() (+19 more)

### Community 111 - "BoardStore"
Cohesion: 0.16
Nodes (19): BoardConflictError, BoardStore, BoardStoreError, _nonfinite(), RuntimeError, Isolated local Teaching Board autosave with validated previous-checkpoint…, _unique_pairs(), parametrize (+11 more)

### Community 112 - "test_board_export.py"
Cohesion: 0.11
Nodes (47): BoardModel, BoardStore, MediaStore, _as_model(), _catalogue_closure(), export_lesson(), export_pdf(), _image_credit() (+39 more)

### Community 113 - "media_targets.py"
Cohesion: 0.17
Nodes (19): _Input, _InputUnion, _KeyboardInput, Clipboard manager for Windows with atomic snapshot, paste injection, prior…, Send a checked native Ctrl+V, independently of the pointer position., send_paste_shortcut(), GUITHREADINFO, capture_target() (+11 more)

### Community 115 - "copy_saved_lesson"
Cohesion: 0.08
Nodes (43): _atomic_catalogue_write(), _catalogue_key(), _catalogue_script(), copy_saved_lesson(), _directory(), _documents(), _entry_bytes(), is_catalogue_lesson() (+35 more)

### Community 116 - "SavedImageLibrary"
Cohesion: 0.14
Nodes (22): Teacher-only offline image chooser with an explicit preview before insertion., import_prepared(), prepare_file(), PreparedImage, Explicit, offline image imports into a lesson-owned immutable media store.…, Recheck the displayed immutable record before reading its bounded blob., Store bytes durably before publishing the document reference. Library…, read_image() (+14 more)

### Community 117 - "SettingsPanel"
Cohesion: 0.11
Nodes (10): SettingsPanel, worker(), test_successful_connection_check_updates_google_readiness_without_claiming_rendering(), descendants(), parametrize, Native layout and masking at both supported companion window sizes., test_frozen_choice_and_image_actions_fit_nested_media_page(), test_full_companion_device_feedback_and_media_actions_fit() (+2 more)

### Community 118 - "test_board_editor_ux.py"
Cohesion: 0.09
Nodes (27): fixture(), Synthetic Interactions REST fixtures, checked against Google's 24 Oct 2026…, app(), editor(), Live editor and lesson controls using native Qt and synthetic input only., selected_object(), test_catalogue_failure_reports_saved_data_separately(), test_close_flushes_live_text_to_saved_lesson() (+19 more)

### Community 120 - "ValueError"
Cohesion: 0.32
Nodes (16): _activate(), _atomic(), _check_inside(), _hash(), inspect_package(), install(), main(), Verified, per-user source-preview install, update, rollback and removal. No… (+8 more)

### Community 121 - "SDCardStatus"
Cohesion: 0.14
Nodes (14): String, SDCardStatus, cardTypeStr, freeBytesMB, is4BitMode, mounted, selfTestPassed, totalBytesGB (+6 more)

### Community 122 - "cyd_identifier/src/main.cpp"
Cohesion: 0.32
Nodes (12): initializer_list, adc(), cmd(), esp_err_t, initDisplay(), loop(), pattern(), readReg() (+4 more)

### Community 123 - "test_media_store.py"
Cohesion: 0.20
Nodes (17): image_bytes(), parametrize, test_acknowledged_events_are_idempotent_when_pulled_back_and_restart_recovers_jobs(), test_canonical_selection_uses_optimistic_local_revision_and_keeps_versions(), test_canonical_title_is_shared_only_with_successful_compare_and_set(), test_concurrent_identical_imports_share_one_blob_safely(), test_history_database_is_untouched_and_media_recovers_after_restart(), test_import_builds_immutable_versions_and_content_deduplicated_blob() (+9 more)

### Community 124 - "test_companion_package.py"
Cohesion: 0.28
Nodes (11): archive(), directory_link(), parametrize, test_ancestor_link_cannot_redirect_uninstall_to_external_file(), test_changed_installed_sources_block_update_and_uninstall(), test_install_update_rollback_uninstall_preserves_data_and_extra_files(), test_releases_junction_cannot_redirect_update(), test_symlink_in_installed_release_refused() (+3 more)

### Community 125 - "test_media_gui_integration.py"
Cohesion: 0.30
Nodes (11): fixture_app(), test_automatic_word_target_does_not_grant_onenote_keyboard_permission(), test_blocked_onenote_image_shows_feedback_on_visible_media_panel(), test_changed_live_caret_retains_image_without_insertion(), test_keyboard_permission_is_only_granted_for_explicit_paste_ready(), test_live_retrieved_image_inserts_only_at_original_word_target(), test_media_microphone_routes_transcript_to_media_not_text_paste(), test_queue_does_not_discard_existing_text() (+3 more)

### Community 126 - "test_board_image_insertion.py"
Cohesion: 0.16
Nodes (12): QDialog, ImagePicker, prepared_file(), Native Qt image picker/editor tests, with synthetic local input only., test_add_image_button_accepts_one_prepared_choice(), accept_choice(), test_frozen_insertion_is_private_until_resume(), test_insert_move_resize_undo_redo_and_offline_reopen() (+4 more)

### Community 127 - "AgentPanel"
Cohesion: 0.07
Nodes (14): AgentPanel, transcribe(), local_composer(), QWidget, Teacher-only Board agent controls; workers never manipulate Qt widgets., An explicit local reuse action uses the same staged agent contract., validate_page_layout(), create_resource_service() (+6 more)

### Community 128 - "media_backup.py"
Cohesion: 0.55
Nodes (10): _assert_no_symlinks(), backup(), _blob_hashes(), _digest(), main(), Path, Verified, no-overwrite backup and restore for the media service data directory.…, restore() (+2 more)

### Community 129 - "Teaching Board manual feedback — 25 October 2026"
Cohesion: 0.29
Nodes (7): Confirmed design decisions, Current saving semantics and open gates, Implemented candidate and next participant retest, Independent copy backend — local engineering evidence, Requested changes, Results reported by the user, Teaching Board manual feedback — 25 October 2026

### Community 130 - "An assistant built into the desktop companion"
Cohesion: 0.20
Nodes (10): An assistant built into the desktop companion, Application knowledge and skills, Current code and the main gap, Groq supplies reasoning; the local application performs actions, Make common changes configuration, New code and self-updates, One assistant interface, separate jobs, Recommended implementation order (+2 more)

### Community 131 - "compose_gui.py"
Cohesion: 0.16
Nodes (22): review(), ESP32 & Windows Voice Compose & Dictate Companion - Interactive Desktop App…, _catalogue_item(), prepare_catalogue(), Bounded, opt-in library metadata for Hermes; recommendations confer no…, Resolve an untrusted result against its immutable submitted catalogue and local…, resolve_recommendation(), Explicit Hermes task UI. Work and callbacks are kept off the Tk worker path. (+14 more)

### Community 132 - "Making the classroom companion accessible"
Cohesion: 0.20
Nodes (10): Accessibility and school adoption, Getting it into teachers' hands, Licensing recommendation, Make agent management a real feature, Making the classroom companion accessible, Product proposition, Proposed sequence and evidence gates, Simplify connectivity (+2 more)

### Community 133 - "Adoption and onboarding research: ESP32 classroom presentation companion"
Cohesion: 0.20
Nodes (9): Adoption and onboarding research: ESP32 classroom presentation companion, AI-agent-managed product pattern, Decision summary, Firmware distribution and Wi-Fi setup, Primary sources, Recommended onboarding shape, Scope and evidence boundary, What a teacher can do today (+1 more)

### Community 134 - "BoardCanvas"
Cohesion: 0.20
Nodes (3): QGraphicsView, BoardCanvas, size_changes()

### Community 136 - "Windows Compose and Dictate repair — 17 October 2026"
Cohesion: 0.50
Nodes (4): Everyday use, Repairs, Verification, Windows Compose and Dictate repair — 17 October 2026

### Community 137 - "Authorised Hermes consultation"
Cohesion: 0.22
Nodes (8): Actual review results, Authenticated Linux access, Authorisation and scope, Authorised Hermes consultation, Completed Linux-agent inventory and evidence, Linux LAN endpoint follow-up, Next useful collaboration step, Verified connection facts

### Community 138 - "Hermes and companion orchestration investigation"
Cohesion: 0.22
Nodes (8): Hermes and companion orchestration investigation, Product boundary and job design, Read-only runtime observation, Recommendation, Sources, Supportability, licensing and staged path, What exists in this checkout, What Hermes offers, and the boundary it leaves

### Community 139 - "forward_transcript"
Cohesion: 0.24
Nodes (6): forward_transcript(), Token-protected loopback handoff from a feature-owned handheld receiver., VoiceBridge, do_POST(), test_handheld_transcript_is_durable_idempotent_and_local_only(), test_handoff_rejects_remote_endpoint_without_network_io()

### Community 140 - "Consultation lessons"
Cohesion: 0.25
Nodes (8): API lifecycle observations, Connection and identity, Consultation lessons, Current direction after the consultation, Design and scope, Later host verification and helper staging, Response quality and evidence, Sources and privacy

### Community 141 - "Image companion feature: testing and recovery"
Cohesion: 0.25
Nodes (8): Agent and generation workflow, Evidence and rollback, Explicit Hermes tasks and offline policy, First-image-release sign-off, Image companion feature: testing and recovery, Private sync and hardware tests, Start the feature preview, Word and OneNote

### Community 142 - "Permanent Hermes connection over Tailscale"
Cohesion: 0.25
Nodes (8): Completion record, Delivery sequence, Host identity check during implementation, Meaning of permanent, Permanent Hermes connection over Tailscale, Required acceptance matrix, Secrets, privacy and authority, Topology and responsibilities

### Community 143 - "Media library and insertion workflow investigation"
Cohesion: 0.25
Nodes (7): Acceptance plan once a destination is selected, Candidate insertion support matrix, Media library and insertion workflow investigation, Proposed data model and storage, Recommended product flow, Scope and current baseline, Security, privacy and school deployment

### Community 144 - "Media library sync investigation"
Cohesion: 0.25
Nodes (7): Credential and content boundary, Media library sync investigation, Proposed data and conflict model, Recommended gate, Sync mechanism options, User direction and open decisions, User-selected hosting direction: private Linux cloud on the Hermes machine

### Community 145 - "Hermes integration development checkpoint"
Cohesion: 0.29
Nodes (7): Current connection evidence, Hermes integration development checkpoint, Implemented, Main reconciliation: 24 October 2026, Remaining delivery gates, Verification and limits, Verified host identity and administrator prerequisite

### Community 146 - "Embedded companion assistant: first working increment"
Cohesion: 0.33
Nodes (6): Assistant behaviour, Available now, Embedded companion assistant: first working increment, Next bounded increment, Persistence and recovery, Verification

### Community 147 - "FakeHermesService"
Cohesion: 0.12
Nodes (9): HermesBoardComposer, Actual bounded-service adapter, not an assertion of live deployment. No…, FakeHermesService, ManualExecutor, test_hermes_adapter_uses_exact_prepared_service_identity_poll_and_preview(), test_hermes_cancel_after_dispatch_requests_stop_without_claiming_termination(), test_hermes_cancel_before_dispatch_discards_same_prepared_identity(), test_hermes_failure_uncertainty_and_approval_do_not_retry_or_publish() (+1 more)

### Community 148 - "Companion Linux deployment tools"
Cohesion: 0.33
Nodes (6): Acceptance still required, Backup, verification and restore, Companion Linux deployment tools, Hermes endpoint migration on Windows, Linux media service staging, Required inventory before Tailscale Serve changes

### Community 149 - "Embedded assistant architecture review"
Cohesion: 0.33
Nodes (5): Critical unknowns before implementation, Current architecture, Embedded assistant architecture review, Finding, Proposed shape

### Community 150 - "Image provider investigation: classroom companion"
Cohesion: 0.33
Nodes (5): Capability comparison, Image provider investigation: classroom companion, Official source register, Recommendation, Recommended small evaluation: “our water cycle image”

### Community 152 - "Linux Hermes collaboration"
Cohesion: 0.40
Nodes (5): Establish the connection and scope, Handle remote checks and approvals, Linux Hermes collaboration, Prepare, dispatch and reconcile, Protect configuration and authority

### Community 153 - "Image feature implementation record"
Cohesion: 0.40
Nodes (5): Image feature implementation record, Implemented candidate, Isolation and preservation, Remaining acceptance and programme, Verification

### Community 154 - "End-of-day checkpoint — 24 October 2026"
Cohesion: 0.40
Nodes (5): Case and enclosure work, Companion and device, End-of-day checkpoint — 24 October 2026, Final local verification, Hermes: next integration priority

### Community 155 - "Private media sync service"
Cohesion: 0.40
Nodes (5): API, Client integration, Local development, Private host deployment boundary, Private media sync service

### Community 157 - "Home/work architecture"
Cohesion: 0.50
Nodes (4): Connectivity and independent readiness, Data and credentials, Home/work architecture, One handheld, same personal agent

### Community 158 - "Further identification and reversible diagnostic"
Cohesion: 0.67
Nodes (3): Further identification and reversible diagnostic, Physical confirmation, Second board: initial inspection

### Community 159 - "Install and recover the isolated desktop preview"
Cohesion: 0.67
Nodes (3): Build and verify, Install and recover the isolated desktop preview, Update, rollback and removal

### Community 163 - "test_board_resize.py"
Cohesion: 0.24
Nodes (19): page_from(), handle_positions(), local_to_scene(), Pure geometry for teacher frame handles, in logical canvas units., Keep the opposite handle fixed; sides grow symmetrically when locked. Crossing…, resize_frame(), mouse_drag(), parametrize (+11 more)

### Community 167 - "Teaching Board: reusable lesson-resource library and agent memory"
Cohesion: 0.12
Nodes (17): Confirmed intent and remaining decisions, Deduplication, recovery, migration and sync, Evidence limits, Four separate kinds of state, General agent-memory systems: do not adopt for this slice, Hybrid retrieval: design now, add after a measured comparison, Next interview frontier, Proposed catalogue and agent organisation (+9 more)

### Community 168 - "MediaServerPortableTests"
Cohesion: 0.23
Nodes (6): MediaServerPortableTests, reserve(), png_sample(), skipUnless, Portable, standard-library smoke tests for the private media API. Run from any…, Return a tiny deterministic image generated with Pillow.

### Community 169 - "safe_path"
Cohesion: 0.21
Nodes (8): safe_path(), _no_private_paths(), Local catalogue integration; source libraries remain read-only. Only selected,…, Merge a validated portable catalogue while keeping roots private. The importer…, Catalogue that recognises verified source blobs without copying them., Resolve only a registered source identity and reverify its blob., _ResolvedResourceCatalogue, _strict_json()

### Community 170 - "School arrival guide: Teaching Board and the Linux Hermes"
Cohesion: 0.18
Nodes (11): Before leaving home, Configure a school-local Hermes credential, only after route acceptance, Create the isolated Board and local data, On the school PC: check the machine and working tree, One short classroom acceptance pass, Prove the school route before using a task, Read this first, Record what the school trial actually proves (+3 more)

### Community 171 - "make_data"
Cohesion: 0.36
Nodes (5): make_data(), MediaBackupTests, Path, skipIf, skipUnless

### Community 172 - "Teaching Board agent and reusable resource library: implementation plan"
Cohesion: 0.20
Nodes (10): Acquisition and spending, Contracts, Deliverable and boundaries, Dependency graph and worker ownership, Execution and acceptance gates, Implementation evidence — local candidate complete, Request and publication, Resource identity and catalogue (+2 more)

### Community 173 - "._index"
Cohesion: 0.20
Nodes (4): Resumable metadata backfill. No prompts, jobs or credentials are read., Resolve and validate without importing or changing review state., Resolve an exact current catalogue row, verify bytes, retain both caches., Resolve a single exact approved image alias, ignoring other types.

### Community 174 - "media_store.py"
Cohesion: 0.29
Nodes (8): Local, versioned image library for the classroom companion. Media has its own…, _source(), app(), image_object(), png(), Independent synthetic lesson lifecycle checks for the requested image workflow., test_fresh_local_image_mouse_numeric_resize_and_process_restart(), test_library_version_survives_source_loss_undo_reopen_and_independent_copy()

### Community 175 - "create_server"
Cohesion: 0.25
Nodes (5): create_server(), main(), MediaHTTPServer, ThreadingHTTPServer, api()

### Community 176 - "Board agent: delegated operating defaults"
Cohesion: 0.25
Nodes (8): 1. Google spending, 2. Source routing, 3. Chart data and reproducibility, 4. Cloud indexing and teaching-profile privacy, 5. Automatic web reuse, Board agent: delegated operating defaults, Implementation status and next step, Publication and the existing generated-image preview condition

### Community 180 - "School readiness: delivered Windows branch and permanent Linux Hermes route"
Cohesion: 0.29
Nodes (7): Delivery and evidence record, Outcome and actual starting facts, School acceptance: distinguish connectivity from working tasks, School readiness: delivered Windows branch and permanent Linux Hermes route, What Hermes may run and what remains in Windows, What the user does on Linux before leaving home, Work packages and owners

### Community 181 - "Linux Hermes school handoff"
Cohesion: 0.33
Nodes (6): Copy-ready message for the existing Linux Hermes, Linux Hermes school handoff, Linux-side read-only inventory, Official operational references, Readiness at handoff, Setup and school-PC acceptance sequence

### Community 182 - "_stub_dependency_wheel"
Cohesion: 0.40
Nodes (5): Path, The portable Board setup creates a usable venv at its final path., Make a tiny offline wheel containing import-only Board dependency stubs., _stub_dependency_wheel(), test_missing_environment_setup_installs_offline_and_keeps_final_venv_path()

### Community 183 - "Teaching Board agent and reusable library candidate"
Cohesion: 0.40
Nodes (5): Limits and acceptance, Open the candidate, Supported first chart format, Teacher controls, Teaching Board agent and reusable library candidate

### Community 185 - "Teaching Board saved-lesson discovery — 25 October 2026"
Cohesion: 0.50
Nodes (4): Reproduction and cause, Resulting behaviour, Teaching Board saved-lesson discovery — 25 October 2026, Verification and remaining acceptance

### Community 186 - "Licensing recommendation for the ESP32 classroom companion"
Cohesion: 0.50
Nodes (4): Licence distinctions and sources, Licensing recommendation for the ESP32 classroom companion, Recommendation, Repository findings and release blockers

## Knowledge Gaps
- **594 isolated node(s):** `Outcome and fixed decisions`, `Current implementation and verification limits`, `Architecture and ownership`, `Teacher workflow`, `Ordered delivery backlog` (+589 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1351 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MediaStore` connect `MediaStore` to `compose_gui.py`, `forward_transcript`, `test_board_resize.py`, `media_store.py`, `BoardModel`, `SyncClient`, `MediaService`, `ProviderFailure`, `test_image_provider_routing.py`, `test_device_feedback.py`, `test_gemini_images.py`, `board_candidate.py`, `ComposeApp`, `service`, `copy_saved_lesson`, `SavedImageLibrary`, `SettingsPanel`, `test_board_editor_ux.py`, `test_media_store.py`, `test_media_gui_integration.py`, `test_board_image_insertion.py`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `ComposeApp` connect `ComposeApp` to `compose_gui.py`, `HermesService`, `forward_transcript`, `HistoryStore`, `test_web_grounding.py`, `test_assistant_service.py`, `MediaPanel`, `LlmPipeline`, `SpeechPipeline`, `SyncClient`, `MediaService`, `test_compose.py`, `MediaStore`, `test_device_feedback.py`, `companion_settings.py`, `HermesPanel`, `FocusTracker`, `AudioCapture`, `VoiceReceiver`, `SettingsPanel`, `test_media_gui_integration.py`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `MediaStore` (e.g. with `import_prepared()` and `prepare_file()`) actually correct?**
  _`MediaStore` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 105 inferred relationships involving `ValueError` (e.g. with `api_call()` and `approve()`) actually correct?**
  _`ValueError` has 105 INFERRED edges - model-reasoned connections that need verification._
- **Are the 38 inferred relationships involving `ComposeApp` (e.g. with `AssistantPanel` and `AssistantService`) actually correct?**
  _`ComposeApp` has 38 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `BoardSession` (e.g. with `BoardAgentController` and `AgentPanel`) actually correct?**
  _`BoardSession` has 17 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Outcome and fixed decisions`, `Current implementation and verification limits`, `Architecture and ownership` to the rest of the system?**
  _594 weakly-connected nodes found - possible documentation gaps or missing edges._