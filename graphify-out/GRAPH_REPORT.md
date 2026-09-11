# Graph Report - ESP32 project  (2026-09-12)

## Corpus Check
- 39 files · ~508,726 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 395 nodes · 626 edges · 28 communities (14 shown, 9 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 40 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5486fd22`
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
- pinout_allocation_f58fa43e.md
- Automated Background Updating
- Workflow: /graph-query
- Workflow: /graph-update
- Workflow: /graph-visualize

## God Nodes (most connected - your core abstractions)
1. `MacroPadGUI` - 35 edges
2. `AudioRecorder` - 28 edges
3. `NetworkManager` - 20 edges
4. `EnvironmentManager` - 17 edges
5. `ChannelStats` - 14 edges
6. `es8311_write_reg()` - 13 edges
7. `_coeff_div` - 13 edges
8. `EnvironmentProfile` - 12 edges
9. `es8311_read_reg()` - 11 edges
10. `es8311_write_reg()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `begin` --calls--> `es8311_codec_init()`  [INFERRED]
  src/audio_recorder.h → src/es8311.cpp
- `logDiagnostics` --calls--> `es8311_codec_dump_registers()`  [INFERRED]
  src/audio_recorder.h → src/es8311.cpp
- `EnvironmentManager::EnvironmentManager()` --calls--> `initProfiles`  [INFERRED]
  src/environment_manager.cpp → src/environment_manager.h
- `wrapTextToChatLines()` --references--> `ChatLine`  [EXTRACTED]
  src/gui.cpp → src/gui.h
- `redrawVoiceCard` --calls--> `drawWrappedText()`  [EXTRACTED]
  src/gui.h → src/gui.cpp

## Import Cycles
- None detected.

## Communities (28 total, 9 thin omitted)

### Community 0 - "MacroPadGUI"
Cohesion: 0.10
Nodes (40): HealthState, DashboardStatus, EnvironmentMode, String, TFT_eSPI, vector, VoiceUIState, drawWrappedText() (+32 more)

### Community 1 - "hermes_voice_receiver.py"
Cohesion: 0.10
Nodes (27): BaseHTTPRequestHandler, ask_hermes_gateway(), dispatch_telegram_mirror(), _async_send(), get_composite_status(), get_whisper_model(), _hermes_sessions_headers(), load_voice_session() (+19 more)

### Community 2 - "EnvironmentManager"
Cohesion: 0.10
Nodes (29): Preferences, EnvironmentChangeCallback, EnvironmentMode, EnvironmentManager, begin, _changeCallback, _currentMode, EnvironmentManager::EnvironmentManager() (+21 more)

### Community 3 - "AudioRecorder"
Cohesion: 0.05
Nodes (29): AudioRecorder, begin, _lastRecordDurationMs, _leftStats, logDiagnostics, _maxLeftPeak, _maxRightPeak, _monoStats (+21 more)

### Community 4 - "NetworkManager"
Cohesion: 0.16
Nodes (27): DashboardStatus, EnvironmentMode, String, extractJsonBool(), extractJsonField(), extractJsonInt(), extractJsonObject(), String (+19 more)

### Community 5 - "main.cpp"
Cohesion: 0.13
Nodes (14): MacroButton, ChatLine, color, text, ChatMessage, isUser, text, String (+6 more)

### Community 6 - "es8311_bsp.c"
Cohesion: 0.25
Nodes (25): es8311_clock_config_t, es8311_handle_t, es8311_mic_gain_t, es8311_resolution_t, esp_err_t, i2c_port_t, es8311_clock_config(), es8311_create() (+17 more)

### Community 7 - "es8311.cpp"
Cohesion: 0.26
Nodes (23): es8311_clock_config_t, es8311_handle_t, es8311_mic_gain_t, es8311_resolution_t, esp_err_t, i2c_port_t, es8311_clock_config(), es8311_codec_dump_registers() (+15 more)

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
Cohesion: 0.17
Nodes (11): ESP32 Portable MacroPad & Hermes Satellite: Core Engineering Rules, Rule 10: Safe Cross-Core Concurrency & Bounded Touch Debounce, Rule 1: Strict Environment Binding (The Composite Profile Rule), Rule 2: The Contract Principle & Visible Degradation, Rule 3: Asynchronous Receiver Concurrency (The Audio Lock Rule), Rule 4: Host-Side Display Sanitization (TFT Buffer Defense), Rule 5: Decouple Subsystem Readiness (Degraded vs. Failed Semantics), Rule 6: Zero-Reflash Portability (NVS Persistence) (+3 more)

### Community 23 - "Automated Background Updating"
Cohesion: 0.25
Nodes (7): 1. Git Commit Hook (Zero-Touch), 2. Live File Watcher (Continuous Auto-Update on Save), 3. Antigravity Agent Rule (Automated Turn-End Maintenance), Automated Background Updating, Everyday Command Reference (`.\graph.ps1`), Graphify Toolkit & Automation System, Slash Commands in Antigravity Chat

## Knowledge Gaps
- **145 isolated node(s):** `start_receiver.sh script`, `count`, `minVal`, `maxVal`, `sum` (+140 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 214 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MacroPadGUI` connect `MacroPadGUI` to `main.cpp`?**
  _High betweenness centrality (0.097) - this node is a cross-community bridge._
- **Why does `NetworkManager` connect `NetworkManager` to `main.cpp`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **What connects `start_receiver.sh script`, `count`, `minVal` to the rest of the system?**
  _145 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `MacroPadGUI` be split into smaller, more focused modules?**
  _Cohesion score 0.09878048780487805 - nodes in this community are weakly interconnected._
- **Should `hermes_voice_receiver.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0967741935483871 - nodes in this community are weakly interconnected._
- **Should `EnvironmentManager` be split into smaller, more focused modules?**
  _Cohesion score 0.0989247311827957 - nodes in this community are weakly interconnected._
- **Should `AudioRecorder` be split into smaller, more focused modules?**
  _Cohesion score 0.05496828752642706 - nodes in this community are weakly interconnected._