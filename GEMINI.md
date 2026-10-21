# ESP32 Portable MacroPad & Hermes Satellite: Core Engineering Rules

Current programme/policy: [master plan](docs/2026-10-21-companion-media-agent-master-plan.md), [board safety](docs/board-upload-safety.md), [permanent Hermes route](docs/hermes-tailscale-home-work.md). Use Australian English and metric measurements. ES3C28P S3 is the sole application target; keep original installed firmware/write lock until an explicitly approved recoverable trial. CYD records are historical. The route below is a target where implementation/acceptance remains open; preserve production behaviour until staged migration is tested.

These rules represent proven architectural invariants established to prevent regression, network hangs, concurrency deadlocks, and display corruption.

---

### Rule 1: Strict Environment Binding (The Composite Profile Rule)
- **Invariant**: Never decouple Wi-Fi credentials from the server endpoints that live on that subnet.
- **Anti-Pattern**: Opportunistic multi-network roaming (`WiFiMulti`) across environments that have distinct backend servers. (Connecting to phone hotspot while holding Home server IP causes silent 65-second TCP hangs).
- **Enforcement**: Treat each environment as an atomic composite unit in `EnvironmentManager`:
  $$\text{Environment} = \{\text{SSID}, \text{Password}, \text{Receiver URL}, \text{Status URL}, \text{Timeout}, \text{Auth Token}\}$$
  Switching environments must reconfigure the entire stack simultaneously.

---

### Rule 2: Host ownership and explicit backend routing
- The ESP32 sends audio to its local receiver; Windows owns agent/provider credentials and local document actions. Original receiver TCP 8787 and preview TCP 8788 are separate until an approved integration trial.
- Groq remains the embedded assistant's primary provider. This installation will use the same Linux Hermes over private Tailscale at home/work for selected bounded tasks; it is not an already-deployed runtime feature.
- Keep explicit local-only Whisper/Ollama operation independent. Local-only forbids remote Hermes/media/provider calls too. Preserve backend provenance; unavailable or untested components cannot be reported ready.

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
  - Wi-Fi association alone does not prove capture, receiver, transcription or AI readiness; report those separately.
  - Remote Groq/Hermes/media services require connectivity; explicitly configured local models and cached assets have their own offline readiness. A remote outage does not disable working BLE controls.

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

---

### Rule 11: Dual-Path Audio Output & Non-Blocking TTS Fallback
- **Invariant**: When audio mode is enabled on the client, the response must be spoken out loud through the host computer's speakers (`SPEAK_ON_HOST=1`) and synthesized as a 16kHz stereo WAV stream for the ESP32 onboard I2S codec. Unaccelerated or offline neural TTS engines must never cause a silent reply or stall round-trip latency.
- **Anti-Pattern**: Blocking for >10s on a CPU-only 1.7B neural TTS model, or catching an exception and returning `"audio_available": false`, leaving the user with a muted device and silent computer.
- **Enforcement**:
  - Host receiver must spawn background thread for local host speaker playback (`speak_on_host_speaker`, e.g., Windows SAPI `SpVoice`).
  - Implement a fast, zero-dependency local TTS fallback (`synthesize_speech_sapi`, <200ms) whenever high-fidelity engines (Voicebox/Kokoro/Qwen) are unaccelerated, unresponsive, or offline.
  - Maintain macro and environment parity in `server/receiver.env.example` for `SPEAK_ON_HOST`.

---

### Rule 12: Wi-Fi/BLE Coexistence & AP NVS Cache Sanitation
- **Invariant**: On ESP32-S3 hardware running concurrent BLE HID Keyboard and Wi-Fi, modem sleep MUST remain enabled; switching networks must purge stale AP BSSID/channel caches.
- **Anti-Pattern 1**: Calling `WiFi.setSleep(false)` or `esp_wifi_set_ps(WIFI_PS_NONE)` when BLE is initialized. ESP-IDF will panic and abort: `wifi:Error! Should enable WiFi modem sleep when both WiFi and Bluetooth are enabled!!!!!!`.
- **Anti-Pattern 2**: Roaming to a mobile hotspot while retaining cached connection parameters from a home router, causing `Reason code: 15 (WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT)`.
- **Enforcement**:
  - Maintain `WIFI_PS_MIN_MODEM` whenever NimBLE is active.
  - Call `WiFi.disconnect(false, true)` with `erase_ap = true` when reconfiguring environments in `EnvironmentManager` or recovering from connection loss.
  - Mobile phone hotspots must be set to pure `WPA2-Personal` (CCMP) to eliminate WPA3 Transition Mode / SAE negotiation failures on embedded radios.

---

### Rule 13: Gateway Tiering & Zero-Zombie Receiver Daemon Semantics
- **Invariant**: The active local receiver is the device-facing voice telemetry bridge. Receiver loss means local voice unavailable; remote agent/model status is unknown unless independently checked, not falsely proven offline.
- **Enforcement**:
  - Verify the configured receiver port/process and instance identity after restarts (production 8787, preview 8788); avoid duplicate global listeners.
  - Local LLM backends (`gemma3:latest` on Ollama) must be pre-warmed in GPU VRAM with `keep_alive: 8h` to ensure sub-second inference and prevent ESP32 HTTP client timeouts.
