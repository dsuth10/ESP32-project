# Graph Report - ESP32 project  (2026-09-20)

## Corpus Check
- 49 files · ~1,000,952 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 585 nodes · 1025 edges · 39 communities (23 shown, 9 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 85 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d0537b9a`
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
- _coeff_div
- create_enclosure
- benchmark_hermes_standalone.py
- flash.py
- start_receiver.sh
- Dashboard-plan.md
- ESP32-S3 2.8" Touch Display (ES3C28P) — Hermes Voice Satellite & MacroPad
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
- gui.cpp
- power_manager.cpp
- redrawVoiceCard
- gui.h
- drawDashboard
- drawStorageExplorer
- pinout_allocation_f58fa43e.md

## God Nodes (most connected - your core abstractions)
1. `MacroPadGUI` - 66 edges
2. `AudioRecorder` - 32 edges
3. `EnvironmentManager` - 24 edges
4. `NetworkManager` - 22 edges
5. `EnvironmentProfile` - 16 edges
6. `HostDiscovery` - 15 edges
7. `ChannelStats` - 14 edges
8. `PowerManager` - 14 edges
9. `ESP32 Portable MacroPad & Hermes Satellite: Core Engineering Rules` - 14 edges
10. `es8311_write_reg()` - 13 edges

## Surprising Connections (you probably didn't know these)
- `begin` --calls--> `es8311_codec_init()`  [INFERRED]
  src/audio_recorder.h → src/es8311.cpp
- `logDiagnostics` --calls--> `es8311_codec_dump_registers()`  [INFERRED]
  src/audio_recorder.h → src/es8311.cpp
- `prepareForSleep` --calls--> `es8311_codec_sleep()`  [INFERRED]
  src/audio_recorder.h → src/es8311.cpp
- `loop()` --calls--> `es8311_codec_set_voice_volume()`  [INFERRED]
  src/main.cpp → src/es8311.cpp
- `setup()` --calls--> `es8311_codec_set_voice_volume()`  [INFERRED]
  src/main.cpp → src/es8311.cpp

## Import Cycles
- None detected.

## Communities (39 total, 9 thin omitted)

### Community 0 - "MacroPadGUI"
Cohesion: 0.09
Nodes (20): HealthState, VoiceUIState, MacroPadGUI, _chatLines, _currentStoragePath, _history, _lastDrawnBatHealth, _lastDrawnBatPercent (+12 more)

### Community 1 - "hermes_voice_receiver.py"
Cohesion: 0.06
Nodes (45): BaseHTTPRequestHandler, ask_hermes_gateway(), check_voicebox_online(), convert_24k_mono_to_16k_stereo_wav(), dispatch_telegram_mirror(), _async_send(), get_composite_status(), get_local_ip_for_target() (+37 more)

### Community 2 - "EnvironmentManager"
Cohesion: 0.07
Nodes (41): Preferences, SemaphoreHandle_t, EnvironmentChangeCallback, EnvironmentMode, String, EnvironmentManager, begin, _changeCallback (+33 more)

### Community 3 - "AudioRecorder"
Cohesion: 0.05
Nodes (35): AudioRecorder, begin, _lastRecordDurationMs, _leftStats, logDiagnostics, _maxLeftPeak, _maxRightPeak, _monoStats (+27 more)

### Community 4 - "network_manager.cpp"
Cohesion: 0.15
Nodes (29): DashboardStatus, EnvironmentMode, function, String, extractJsonBool(), extractJsonField(), extractJsonInt(), extractJsonObject() (+21 more)

### Community 5 - "main.cpp"
Cohesion: 0.08
Nodes (41): MacroButton, sdcard_type_t, calculateBatteryPercentage(), HealthState, executeMacro(), goToSoftOff(), loop(), sampleBatteryTelemetry() (+33 more)

### Community 6 - "es8311_bsp.c"
Cohesion: 0.23
Nodes (25): es8311_clock_config_t, es8311_handle_t, es8311_mic_gain_t, es8311_resolution_t, esp_err_t, i2c_port_t, es8311_clock_config(), es8311_create() (+17 more)

### Community 7 - "es8311.cpp"
Cohesion: 0.25
Nodes (26): es8311_clock_config_t, es8311_handle_t, es8311_mic_gain_t, es8311_resolution_t, esp_err_t, i2c_port_t, es8311_clock_config(), es8311_codec_dump_registers() (+18 more)

### Community 8 - "_coeff_div"
Cohesion: 0.15
Nodes (13): _coeff_div, adc_div, adc_osr, bclk_div, dac_div, dac_osr, fs_mode, lrck_h (+5 more)

### Community 10 - "benchmark_hermes_standalone.py"
Cohesion: 0.60
Nodes (4): main(), query_cli(), query_gateway(), Hermes Standalone Benchmark Tool Compares execution time of one-shot…

### Community 15 - "Dashboard-plan.md"
Cohesion: 0.05
Nodes (36): MacroPad readiness, Phase 0 — Protect what currently works, Phase 10 — Define proper status semantics, Phase 11 — Separate Macro readiness from Voice readiness, Phase 12 — Wi-Fi health information, Phase 13 — Add a genuine Internet test, Phase 14 — Avoid dashboard probes interfering with voice, Phase 15 — Make the Python receiver concurrent (+28 more)

### Community 16 - "ESP32-S3 2.8" Touch Display (ES3C28P) — Hermes Voice Satellite & MacroPad"
Cohesion: 0.05
Nodes (35): 1. System Topology, 2. Component Directory, 3. Security Model: Secret Separation, 4. Work Privacy Hardening & Ollama Performance, 5. Page 6 System Dashboard, 6. Host Setup Instructions, Architectural Principles, Home Setup (Linux Server) (+27 more)

### Community 17 - "ESP32 Portable MacroPad & Hermes Satellite: Core Engineering Rules"
Cohesion: 0.13
Nodes (14): ESP32 Portable MacroPad & Hermes Satellite: Core Engineering Rules, Rule 10: Safe Cross-Core Concurrency & Bounded Touch Debounce, Rule 11: Dual-Path Audio Output & Non-Blocking TTS Fallback, Rule 12: Wi-Fi/BLE Coexistence & AP NVS Cache Sanitation, Rule 13: Gateway Tiering & Zero-Zombie Receiver Daemon Semantics, Rule 1: Strict Environment Binding (The Composite Profile Rule), Rule 2: The Contract Principle & Visible Degradation, Rule 3: Asynchronous Receiver Concurrency (The Audio Lock Rule) (+6 more)

### Community 22 - "HostDiscovery"
Cohesion: 0.19
Nodes (18): IPAddress, String, HostDiscovery, begin, checkBeacon, discoverNow, _lastBeaconCheck, _lastDiscoveryAttempt (+10 more)

### Community 23 - "Automated Background Updating"
Cohesion: 0.25
Nodes (7): 1. Git Commit Hook (Zero-Touch), 2. Live File Watcher (Continuous Auto-Update on Save), 3. Antigravity Agent Rule (Automated Turn-End Maintenance), Automated Background Updating, Everyday Command Reference (`.\graph.ps1`), Graphify Toolkit & Automation System, Slash Commands in Antigravity Chat

### Community 30 - "Voice Satellite Operations Runbook"
Cohesion: 0.29
Nodes (6): Mobile Hotspot Connection Troubleshooting (Reason 15), Pre-Warming Ollama in GPU VRAM, Quick Health Check, Starting the Voice Receiver Daemon, Verifying Host Speakers & Audio Pipeline, Voice Satellite Operations Runbook

### Community 31 - "generate_case_battery.py"
Cohesion: 0.21
Nodes (28): add_cube(), add_cylinder(), add_end_vents(), add_speaker_grill(), add_standoffs(), add_through_bolts(), apply_boolean(), build_battery_and_speaker() (+20 more)

### Community 32 - "gui.cpp"
Cohesion: 0.14
Nodes (17): canScrollDown, canScrollUp, drawButton, drawDashboardSwitching, drawPowerConfirmDialog, drawSleepSplash, getButtonRect, getPowerDialogTarget (+9 more)

### Community 33 - "power_manager.cpp"
Cohesion: 0.25
Nodes (13): esp_sleep_wakeup_cause_t, PowerManager, begin, configureWakeSources, enterDeepSleep, fadeBacklightOff, holdSleepPins, logWakeCause (+5 more)

### Community 34 - "redrawVoiceCard"
Cohesion: 0.14
Nodes (15): String, TFT_eSPI, vector, VoiceUIState, drawWrappedText(), addVoiceTurn, clearConversation, drawVoiceCard (+7 more)

### Community 35 - "gui.h"
Cohesion: 0.18
Nodes (9): ChatLine, color, text, ChatMessage, isUser, text, String, TFT_eSPI (+1 more)

### Community 36 - "drawDashboard"
Cohesion: 0.24
Nodes (11): DashboardStatus, EnvironmentMode, HealthState, drawAll, drawDashboard, drawDashboardPowerButton, drawDashboardVolume, drawStatusBar (+3 more)

### Community 37 - "drawStorageExplorer"
Cohesion: 0.33
Nodes (6): drawStorageExplorer, drawStorageListOnly, refreshStorageExplorer, scrollStorageList, getSDCardStatus(), sdCardGetStorageSpace()

## Knowledge Gaps
- **185 isolated node(s):** `start_receiver.sh script`, `count`, `minVal`, `maxVal`, `sum` (+180 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 278 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MacroPadGUI` connect `MacroPadGUI` to `gui.cpp`, `redrawVoiceCard`, `gui.h`, `drawDashboard`, `drawStorageExplorer`, `main.cpp`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **What connects `start_receiver.sh script`, `count`, `minVal` to the rest of the system?**
  _185 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `MacroPadGUI` be split into smaller, more focused modules?**
  _Cohesion score 0.09090909090909091 - nodes in this community are weakly interconnected._
- **Should `hermes_voice_receiver.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06274509803921569 - nodes in this community are weakly interconnected._
- **Should `EnvironmentManager` be split into smaller, more focused modules?**
  _Cohesion score 0.07399577167019028 - nodes in this community are weakly interconnected._
- **Should `AudioRecorder` be split into smaller, more focused modules?**
  _Cohesion score 0.05142857142857143 - nodes in this community are weakly interconnected._
- **Should `network_manager.cpp` be split into smaller, more focused modules?**
  _Cohesion score 0.14623655913978495 - nodes in this community are weakly interconnected._