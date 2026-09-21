# Graph Report - ESP32 project  (2026-09-21)

## Corpus Check
- 51 files · ~1,139,895 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 643 nodes · 1133 edges · 41 communities (25 shown, 9 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 88 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `33bc067a`
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
- Soft power-off and touch-to-wake — investigation report
- power_manager.cpp
- generate_case_battery_only.py
- gui.cpp
- gui.h
- drawDashboard
- pinout_allocation_f58fa43e.md
- drawStorageExplorer
- addVoiceTurn

## God Nodes (most connected - your core abstractions)
1. `MacroPadGUI` - 67 edges
2. `AudioRecorder` - 32 edges
3. `EnvironmentManager` - 24 edges
4. `NetworkManager` - 23 edges
5. `EnvironmentProfile` - 16 edges
6. `HostDiscovery` - 15 edges
7. `ChannelStats` - 14 edges
8. `ESP32 Portable MacroPad & Hermes Satellite: Core Engineering Rules` - 14 edges
9. `es8311_write_reg()` - 13 edges
10. `_coeff_div` - 13 edges

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

## Communities (41 total, 9 thin omitted)

### Community 0 - "MacroPadGUI"
Cohesion: 0.09
Nodes (23): HealthState, VoiceUIState, MacroPadGUI, _chatLines, _currentStoragePath, drawButton, getButtonRect, getTouchTarget (+15 more)

### Community 1 - "hermes_voice_receiver.py"
Cohesion: 0.06
Nodes (45): BaseHTTPRequestHandler, ask_hermes_gateway(), check_voicebox_online(), convert_24k_mono_to_16k_stereo_wav(), dispatch_telegram_mirror(), _async_send(), get_composite_status(), get_local_ip_for_target() (+37 more)

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
Cohesion: 0.21
Nodes (17): IPAddress, String, HostDiscovery, begin, checkBeacon, discoverNow, _lastBeaconCheck, _lastDiscoveryAttempt (+9 more)

### Community 23 - "Automated Background Updating"
Cohesion: 0.25
Nodes (7): 1. Git Commit Hook (Zero-Touch), 2. Live File Watcher (Continuous Auto-Update on Save), 3. Antigravity Agent Rule (Automated Turn-End Maintenance), Automated Background Updating, Everyday Command Reference (`.\graph.ps1`), Graphify Toolkit & Automation System, Slash Commands in Antigravity Chat

### Community 30 - "Voice Satellite Operations Runbook"
Cohesion: 0.29
Nodes (6): Mobile Hotspot Connection Troubleshooting (Reason 15), Pre-Warming Ollama in GPU VRAM, Quick Health Check, Starting the Voice Receiver Daemon, Verifying Host Speakers & Audio Pipeline, Voice Satellite Operations Runbook

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
Nodes (20): TFT_eSPI, drawWrappedText(), canScrollDown, canScrollUp, clearConversation, drawDashboardSwitching, drawPowerConfirmDialog, drawSleepSplash (+12 more)

### Community 36 - "gui.h"
Cohesion: 0.20
Nodes (9): ChatLine, color, text, ChatMessage, isUser, text, String, TFT_eSPI (+1 more)

### Community 37 - "drawDashboard"
Cohesion: 0.25
Nodes (11): DashboardStatus, EnvironmentMode, HealthState, drawAll, drawDashboard, drawDashboardPowerButton, drawDashboardVolume, drawStatusBar (+3 more)

### Community 39 - "drawStorageExplorer"
Cohesion: 0.29
Nodes (7): String, drawStorageExplorer, drawStorageListOnly, navigateStorageTo, navigateStorageUp, refreshStorageExplorer, scrollStorageList

### Community 40 - "addVoiceTurn"
Cohesion: 0.29
Nodes (7): vector, VoiceUIState, addVoiceTurn, drawVoiceCard, rebuildChatLines, scrollToLatestResponse, wrapTextToChatLines()

## Knowledge Gaps
- **206 isolated node(s):** `start_receiver.sh script`, `count`, `minVal`, `maxVal`, `sum` (+201 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 301 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MacroPadGUI` connect `MacroPadGUI` to `gui.cpp`, `gui.h`, `drawDashboard`, `main.cpp`, `drawStorageExplorer`, `addVoiceTurn`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **What connects `start_receiver.sh script`, `count`, `minVal` to the rest of the system?**
  _206 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `MacroPadGUI` be split into smaller, more focused modules?**
  _Cohesion score 0.08666666666666667 - nodes in this community are weakly interconnected._
- **Should `hermes_voice_receiver.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06274509803921569 - nodes in this community are weakly interconnected._
- **Should `EnvironmentManager` be split into smaller, more focused modules?**
  _Cohesion score 0.07641196013289037 - nodes in this community are weakly interconnected._
- **Should `AudioRecorder` be split into smaller, more focused modules?**
  _Cohesion score 0.05272108843537415 - nodes in this community are weakly interconnected._
- **Should `network_manager.cpp` be split into smaller, more focused modules?**
  _Cohesion score 0.12941176470588237 - nodes in this community are weakly interconnected._