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

---

### Rule 8: Dual-Core Display Isolation (The Non-Blocking UI Invariant)
- **Invariant**: The main Arduino `loop()` on Core 1 must remain 100% non-blocking and dedicated strictly to UI rendering, touch polling (`ts.read()`), and BLE keyboard handling (>50–100 Hz).
- **Anti-Pattern**: Calling synchronous network operations (`WiFiClient`, `HTTPClient::GET`, `WiFi.hostByName`, or `checkInternet`) directly on Core 1. A slow or unreachable server blocks the main thread for 1.5–5.0 seconds, starving touch input and freezing navigation.
- **Enforcement**:
  - All periodic network telemetry, deep health checks, and DNS probes MUST run inside dedicated FreeRTOS worker tasks pinned to **Core 0** (e.g. `telemetryWorkerTask`).
  - Core 1 only reads atomic/mutex-guarded cached status snapshots with zero wait time (`xSemaphoreTake(mutex, 0)`).

---

### Rule 9: Differential Screen Redraws (Zero-Flicker Telemetry)
- **Invariant**: Never redraw structural UI containers, cards, static labels, or button outlines during periodic telemetry updates.
- **Anti-Pattern**: Calling `fillRoundRect` or blanking entire cards every 3–5 seconds to update a few text values on SPI TFT displays without hardware framebuffers.
- **Enforcement**:
  - UI draw functions that display dynamic telemetry must take a `bool fullRedraw` parameter.
  - Set `fullRedraw = true` ONLY on initial page entry or layout changes.
  - When `fullRedraw = false`, overwrite strictly the minimal bounding box of dynamic text (`fillRect` over the value rectangle) and indicator dots in-place.

---

### Rule 10: Safe Cross-Core Concurrency & Bounded Touch Debounce
- **Invariant**: Cross-core data sharing must use FreeRTOS mutexes when allocating memory; touch debouncing loops must never be unbounded.
- **Enforcement**:
  - Never use `portENTER_CRITICAL` spinlocks when copying structs containing dynamic heap allocations (such as Arduino `String`). Always guard shared state with `SemaphoreHandle_t` or use static C-style structs.
  - All touch-release waiting loops (`while (ts.isTouched)`) MUST enforce an explicit safety timeout (e.g., `millis() - start < 1000`) to prevent hardware transients from locking the main loop.
