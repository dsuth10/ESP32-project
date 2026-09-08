# ESP32 Portable MacroPad & Hermes Satellite: Core Engineering Rules

These rules represent proven architectural invariants established to prevent regression, network hangs, concurrency deadlocks, and display corruption.

---

### Rule 1: Strict Environment Binding (The Composite Profile Rule)
- **Invariant**: Never decouple Wi-Fi credentials from the server endpoints that live on that subnet.
- **Anti-Pattern**: Opportunistic multi-network roaming (`WiFiMulti`) across environments that have distinct backend servers. (Connecting to phone hotspot while holding Home server IP causes silent 65-second TCP hangs).
- **Enforcement**: Treat each environment as an atomic composite unit in `EnvironmentManager`:
  $$\text{Environment} = \{\text{SSID}, \text{Password}, \text{Receiver URL}, \text{Status URL}, \text{Timeout}, \text{Auth Token}\}$$
  Switching environments must reconfigure the entire stack simultaneously.

---

### Rule 2: The Contract Principle & Visible Degradation
- **Invariant**: The ESP32 only ever talks to the Voice Receiver (`:8787`); the Receiver only ever orchestrates through Hermes (`:8642`).
- **Enforcement**:
  - At Home: Hermes uses its configured cloud/local provider.
  - At School/Work: Hermes uses local Ollama via `127.0.0.1:11434/v1`.
  - Never allow silent bypassing of Hermes. If a diagnostic fallback is used, it must explicitly tag `[Fallback]` and reflect in telemetry and the dashboard so the system never reports "All Green" when Hermes is offline.

---

### Rule 3: Asynchronous Receiver Concurrency (The Audio Lock Rule)
- **Invariant**: Always use Python's `ThreadingHTTPServer` with an explicit `threading.Lock()` (`voice_lock`) around audio processing.
- **Enforcement**:
  - Background health and telemetry probes (`GET /health`, `GET /status`) must run concurrently on worker threads and return in $<50\text{ ms}$ even during active Whisper transcription or LLM inference.
  - Competing `/voice` uploads during active processing must be rejected immediately with **HTTP 429 (Busy)** rather than corrupting audio buffer files on disk.

---

### Rule 4: Host-Side Display Sanitization (TFT Buffer Defense)
- **Invariant**: Embedded TFT display controllers (ST7789/ILI9341 `drawString`) have no UTF-8 emoji renderer and no markdown engine.
- **Enforcement**: Sanitize text on the Python host before transmitting to the ESP32 (`sanitize_for_display`). Strip markdown asterisks, hashes, backticks, bullet points, and emojis. Clamp text length to ~100–120 characters to prevent buffer and screen overflow.

---

### Rule 5: Decouple Subsystem Readiness (Degraded vs. Failed Semantics)
- **Invariant**: MacroPad (BLE HID) and Voice Satellite (Wi-Fi + AI) are separate subsystems.
- **Enforcement**:
  - If BLE is connected, macros are ready.
  - If Wi-Fi is connected, local voice is ready.
  - At School/Work, mobile internet is optional because Ollama runs 100% locally on the GPU. Never mark the device as globally "FAILED" if mobile data is toggled off on your phone.

---

### Rule 6: Zero-Reflash Portability (NVS Persistence)
- **Invariant**: The user must never need to connect a USB cable, edit `#define` macros, or recompile firmware just to move between home and school.
- **Enforcement**: All user profile selections (`ENV_HOME` vs. `ENV_WORK`) must be persisted in ESP32 Non-Volatile Storage (NVS via Arduino `Preferences`) and survive battery reboots and power cycles.

---

### Rule 7: Config Template Parity & Rollback Tagging
- **Invariant**: Keep private credentials separate from version control while maintaining template parity.
- **Enforcement**:
  - Never commit `src/wifi_config.h` (enforced via `.gitignore`).
  - Always maintain 100% macro define parity in `src/wifi_config.h.example` whenever new configuration options are introduced.
  - Always tag known-good baseline states (`tag-<context>-baseline`) before performing major cross-branch architectural merges.
