# Graph Report - ESP32 project  (2026-09-19)

## Corpus Check
- 45 files · ~518,722 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 528 nodes · 878 edges · 31 communities (16 shown, 8 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 76 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `60d6ce91`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- MacroPadGUI
- hermes_voice_receiver.py
- EnvironmentManager
- AudioRecorder
- NetworkManager
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

## God Nodes (most connected - your core abstractions)
1. `MacroPadGUI` - 61 edges
2. `AudioRecorder` - 31 edges
3. `EnvironmentManager` - 24 edges
4. `NetworkManager` - 21 edges
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
- `loop()` --calls--> `es8311_codec_set_voice_volume()`  [INFERRED]
  src/main.cpp → src/es8311.cpp
- `setup()` --calls--> `es8311_codec_set_voice_volume()`  [INFERRED]
  src/main.cpp → src/es8311.cpp

## Import Cycles
- None detected.

## Communities (31 total, 8 thin omitted)

### Community 0 - "MacroPadGUI"
Cohesion: 0.05
Nodes (71): ChatLine, color, text, ChatMessage, isUser, text, DashboardStatus, EnvironmentMode (+63 more)

### Community 1 - "hermes_voice_receiver.py"
Cohesion: 0.06
Nodes (45): BaseHTTPRequestHandler, ask_hermes_gateway(), check_voicebox_online(), convert_24k_mono_to_16k_stereo_wav(), dispatch_telegram_mirror(), _async_send(), get_composite_status(), get_local_ip_for_target() (+37 more)

### Community 2 - "EnvironmentManager"
Cohesion: 0.08
Nodes (41): Preferences, SemaphoreHandle_t, EnvironmentChangeCallback, EnvironmentMode, String, EnvironmentManager, begin, _changeCallback (+33 more)

### Community 3 - "AudioRecorder"
Cohesion: 0.05
Nodes (34): AudioRecorder, begin, _lastRecordDurationMs, _leftStats, logDiagnostics, _maxLeftPeak, _maxRightPeak, _monoStats (+26 more)

### Community 4 - "NetworkManager"
Cohesion: 0.14
Nodes (29): DashboardStatus, EnvironmentMode, function, String, extractJsonBool(), extractJsonField(), extractJsonInt(), extractJsonObject() (+21 more)

### Community 5 - "main.cpp"
Cohesion: 0.07
Nodes (41): MacroButton, sdcard_type_t, calculateBatteryPercentage(), HealthState, executeMacro(), loop(), sampleBatteryTelemetry(), setLedColor() (+33 more)

### Community 6 - "es8311_bsp.c"
Cohesion: 0.23
Nodes (25): es8311_clock_config_t, es8311_handle_t, es8311_mic_gain_t, es8311_resolution_t, esp_err_t, i2c_port_t, es8311_clock_config(), es8311_create() (+17 more)

### Community 7 - "es8311.cpp"
Cohesion: 0.25
Nodes (25): es8311_clock_config_t, es8311_handle_t, es8311_mic_gain_t, es8311_resolution_t, esp_err_t, i2c_port_t, es8311_clock_config(), es8311_codec_dump_registers() (+17 more)

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

## Knowledge Gaps
- **182 isolated node(s):** `start_receiver.sh script`, `count`, `minVal`, `maxVal`, `sum` (+177 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 272 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MacroPadGUI` connect `MacroPadGUI` to `main.cpp`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **What connects `start_receiver.sh script`, `count`, `minVal` to the rest of the system?**
  _182 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `MacroPadGUI` be split into smaller, more focused modules?**
  _Cohesion score 0.051929824561403506 - nodes in this community are weakly interconnected._
- **Should `hermes_voice_receiver.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06274509803921569 - nodes in this community are weakly interconnected._
- **Should `EnvironmentManager` be split into smaller, more focused modules?**
  _Cohesion score 0.07641196013289037 - nodes in this community are weakly interconnected._
- **Should `AudioRecorder` be split into smaller, more focused modules?**
  _Cohesion score 0.05230496453900709 - nodes in this community are weakly interconnected._
- **Should `NetworkManager` be split into smaller, more focused modules?**
  _Cohesion score 0.13636363636363635 - nodes in this community are weakly interconnected._