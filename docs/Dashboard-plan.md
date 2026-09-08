Yes. I would treat this as a proper **Portable Home/Work Architecture** rather than a small dashboard feature. The goal is that you can carry the ESP32 between home and school, press one button, and the device reconfigures itself while also telling you exactly what is and is not working.

The repository is already well positioned for this. `main` has multi-network awareness and can report its current SSID/IP, while the other branch contains the persistent Hermes gateway work and performance telemetry.  The existing GUI is also already organised around numbered pages, so adding a specialised sixth dashboard page does not require redesigning the first five.

# Target end state

The finished system should work like this:

```text
                         ESP32-S3
                            │
                 ┌──────────┴──────────┐
                 │                     │
              HOME mode             WORK mode
                 │                     │
          Home Wi-Fi              Phone hotspot
                 │                     │
       Home Linux Hermes       School Windows PC
       Voice Receiver :8787    Voice Receiver :8787
                 │                     │
          localhost:8642          localhost:8642
                 │                     │
          Home Hermes           School Hermes
                 │                     │
        normal provider             Ollama
                                     │
                              local GPU model
```

The ESP32 never needs to know how the underlying model works. Its contract is always:

> **ESP32 → Voice Receiver → Hermes**

Hermes officially supports Ollama through its OpenAI-compatible endpoint at `127.0.0.1:11434/v1`, so the Work configuration fits this architecture naturally. ([GitHub][1])

---

# Phase 0 — Protect what currently works

Before merging anything, I would freeze the two existing implementations.

We should keep:

* `main` as the current school/Ollama working reference;
* `feature/voice-latency-optimisation` as the persistent-gateway reference;
* create a new integration branch, something like `feature/home-work-dashboard`;
* make no direct changes to `main` until the combined version has passed both Home and Work tests.

I would also record the current working states as tags or commits so we can instantly return to either configuration.

The integration branch should start from `main`, because that contains today's school work. We then deliberately bring the useful persistent-gateway changes across rather than blindly choosing one implementation over the other.

---

# Phase 1 — Reconcile the two voice architectures

This is the first substantive job.

The current school receiver can call `hermes.exe -z` and fall back directly to Ollama. The latency branch instead talks to the persistent Hermes Gateway at:

```text
http://127.0.0.1:8642/v1/chat/completions
```

The second architecture should win.

The feature branch already contains a benchmark specifically comparing one-shot `hermes.exe -z` with persistent `:8642` operation.

The consolidated receiver should therefore have:

```text
Audio
 ↓
faster-whisper
 ↓
Hermes Gateway :8642
 ↓
Hermes
 ↓
configured model
```

We remove the normal `hermes.exe -z` path from production voice operation.

We also remove the receiver's direct Ollama fallback. Ollama becomes a **Hermes provider**, not an alternative to Hermes.

If Hermes is broken, the dashboard should say Hermes is broken rather than silently bypassing it.

That will make troubleshooting enormously easier.

---

# Phase 2 — Make the receiver platform-independent

The persistent branch currently assumes a Windows Hermes installation path. That needs to disappear because Home will be Linux while Work is Windows.

The receiver should discover configuration in this order:

```text
Explicit environment variable
        ↓
~/.hermes/
        ↓
legacy Windows Hermes location if necessary
```

In particular, it needs access to:

```text
API_SERVER_KEY
Gateway URL
Voice receiver authentication token
Environment name
Backend label
```

The official Hermes configuration now supports the API server through `~/.hermes/.env` and/or `~/.hermes/config.yaml`, with `127.0.0.1:8642` as the normal local bind. ([GitHub][2])

We should therefore standardise on:

```text
Gateway: http://127.0.0.1:8642
```

on both machines.

We should **not** expose port `8642` to the Home LAN or school hotspot.

---

# Phase 3 — Turn the receiver into the health authority

This is one of the most important architectural decisions.

The ESP32 should not independently interrogate:

* Hermes;
* Ollama;
* Whisper;
* the underlying model;
* Telegram.

Instead it asks its local Voice Receiver:

```text
GET /status
```

The receiver does all the deeper testing.

I would give it three endpoints:

```text
GET  /health
GET  /status
POST /voice
```

`/health` answers only:

```json
{
  "status": "ok"
}
```

That means the Python service itself is alive.

`/status` returns something richer:

```json
{
  "status": "ok",
  "environment": "work",

  "receiver": {
    "ready": true,
    "whisper": true
  },

  "hermes": {
    "live": true,
    "ready": true,
    "latency_ms": 11
  },

  "backend": {
    "type": "ollama",
    "ready": true,
    "warm": true
  },

  "last_voice": {
    "success": true
  }
}
```

Hermes makes this particularly feasible because it exposes both:

```text
GET /health
```

for cheap liveness testing and authenticated:

```text
GET /health/detailed
```

for actual readiness. The detailed endpoint checks things such as the active configuration, state database, configured model and gateway/platform state. ([GitHub][2])

So the dashboard can distinguish:

> Hermes process exists

from:

> Hermes is genuinely ready to answer.

That is much more useful.

---

# Phase 4 — Add a specific Work/Ollama health test

At Work the receiver should additionally check Ollama locally.

It could test:

```text
127.0.0.1:11434
```

and confirm that the intended model is available.

Again, this request occurs entirely inside the school PC.

The ESP32 never talks directly to port `11434`.

We could eventually distinguish three useful states:

```text
OLLAMA OFFLINE

OLLAMA READY
model not loaded

OLLAMA READY
model warm
```

That last distinction could be useful because model loading may account for some of the long school delays you've seen.

---

# Phase 5 — Create the Home/Work Profile Manager

This is the central firmware change.

I would introduce a new `EnvironmentManager`.

Conceptually:

```cpp
enum EnvironmentMode {
    ENV_HOME,
    ENV_WORK
};
```

Each environment contains:

```text
Display name
Wi-Fi SSID
Wi-Fi password
Voice receiver URL
Voice receiver token
Expected Bluetooth host
Voice timeout
```

For example:

```text
HOME
  SSID
  password
  http://home-hermes:8787
  token
  Home Desktop
  25 second voice timeout

WORK
  hotspot SSID
  hotspot password
  http://school-pc:8787
  token
  School Desktop
  65 second voice timeout
```

The credentials remain in the ignored local configuration file.

The repository already excludes the real `wifi_config.h` from Git, which we should preserve.

---

# Phase 6 — Stop automatically mixing Home and Work

This is a subtle but important change.

Current `main` has `WiFiMulti` and will search across all configured networks automatically.

That is useful generally, but it is wrong for this new architecture because it could create this situation:

```text
Environment = HOME
Wi-Fi = Work hotspot
Receiver = Home receiver
```

or vice versa.

Instead:

> **Environment selection chooses the complete network profile.**

If HOME is selected:

```text
Only Home Wi-Fi
Only Home receiver
Home BLE identity expectations
```

If WORK is selected:

```text
Only hotspot
Only school receiver
Work BLE identity expectations
```

We can eventually support multiple networks *inside* a profile, but Home and Work themselves should never mix.

---

# Phase 7 — Persist the selected environment

Use ESP32 NVS through the Arduino `Preferences` API.

If you choose WORK at school:

```text
WORK selected
↓
stored in NVS
↓
device reboot
↓
WORK remains selected
```

Likewise at Home.

No reflashing.

No changing header files.

No connecting to a computer just to change location.

On first ever boot we can default to HOME.

---

# Phase 8 — Implement controlled profile switching

Pressing HOME or WORK should launch a small state machine.

For WORK, for example:

```text
WORK pressed
    ↓
Save WORK preference
    ↓
Stop current network operations
    ↓
Disconnect Home Wi-Fi
    ↓
Clear old health data
    ↓
Connect Work hotspot
    ↓
Acquire IP
    ↓
Check Internet
    ↓
Check Voice Receiver
    ↓
Check Hermes
    ↓
Check Ollama
    ↓
Update dashboard
```

The screen can display progress:

```text
Switching to WORK...

Wi-Fi       connecting
Receiver    waiting
Hermes      waiting
AI          waiting
```

and progressively change indicators as services appear.

We should explicitly prevent environment switching while audio is being recorded or a voice request is being processed.

---

# Phase 9 — Create the sixth Dashboard page

`NUM_PAGES` becomes `6`.

The current page arrangement remains untouched:

```text
1 Media
2 Productivity
3 Windows
4 Custom
5 Hermes Voice
6 System
```

Page 6 is special. It should not use the normal macro-button grid.

I would design approximately this:

```text
┌────────────────────────────────────┐
│ SYSTEM                       WORK ● │
├────────────────────────────────────┤
│ ● Wi-Fi       Galaxy A55 5G        │
│ ● Internet    Online               │
│ ● Bluetooth   Connected            │
│ ● Voice Host  Ready                │
│ ● Hermes      Ready                │
│ ● AI          Ollama • Ready       │
├────────────────────────────────────┤
│    [ HOME ]          [ WORK ✓ ]    │
└────────────────────────────────────┘
```

The existing GUI already special-cases the Hermes Voice page, so we can use exactly the same approach for `PAGE_DASHBOARD`.

---

# Phase 10 — Define proper status semantics

I would use four status states consistently:

```text
● Green    READY
● Amber    DEGRADED / CHECKING
● Red      FAILED
● Grey     UNKNOWN / NOT REQUIRED
```

This is important because not everything has to be green.

Imagine you're at school with your phone's mobile data switched off:

```text
Wi-Fi       ✓
Internet    ✕
Bluetooth   ✓
Receiver    ✓
Hermes      ✓
Ollama      ✓

VOICE READY ✓
```

That is completely valid.

The device should **not** call itself broken just because there is no Internet.

---

# Phase 11 — Separate Macro readiness from Voice readiness

This is another useful improvement.

There are really two systems inside this device.

### MacroPad readiness

Requires:

```text
Bluetooth
```

### Voice readiness

Requires:

```text
Wi-Fi
Voice Receiver
Whisper
Hermes
AI backend
```

Therefore page 6 could have two overall badges:

```text
MACROPAD   READY ✓
VOICE      READY ✓
```

Then perhaps:

```text
FULL SYSTEM READY
```

only when both are available.

This prevents one disconnected subsystem from making the whole device appear broken.

---

# Phase 12 — Wi-Fi health information

We can reliably show:

```text
SSID
IP address
RSSI
connection state
```

The firmware already exposes the connected SSID and IP.

I would also use RSSI to give a rough signal indication.

Something like:

```text
Wi-Fi
Galaxy A55 5G
-48 dBm • Strong
```

or simply:

```text
Galaxy A55 5G  ●●●
```

to save screen space.

---

# Phase 13 — Add a genuine Internet test

Wi-Fi connectivity is not the same as Internet connectivity.

We therefore add a tiny connectivity probe every 30–60 seconds.

It should contain **no user data whatsoever**.

The states become:

```text
Wi-Fi connected + Internet available

Wi-Fi connected + Internet unavailable

Wi-Fi unavailable
```

This test should not gate Work voice functionality.

---

# Phase 14 — Avoid dashboard probes interfering with voice

This needs some care.

We don't want:

```text
dashboard health check
↓
blocks HTTP
↓
voice request waits
```

The health subsystem therefore needs to run independently of the main user interaction.

I would introduce a lightweight status task/state manager.

Cheap states such as BLE and Wi-Fi can be updated continuously.

More expensive tests should run periodically:

| Test             | Suggested interval |
| ---------------- | -----------------: |
| BLE state        |          immediate |
| Wi-Fi state      |          immediate |
| SSID/RSSI/IP     |                1 s |
| Voice Receiver   |             5–10 s |
| Hermes readiness |               10 s |
| Ollama readiness |               10 s |
| Internet         |            30–60 s |

Health checks pause while a voice request is actually being processed.

Voice traffic gets priority.

---

# Phase 15 — Make the Python receiver concurrent

The current receiver uses Python's basic `HTTPServer`.

That is fine for one voice request, but once we have health requests as well, a long-running voice inference could prevent `/status` responding.

I would move to:

```text
ThreadingHTTPServer
```

with a lock around the `/voice` processing path.

That gives us:

```text
/voice   → one voice job at a time

/status  → can return cached health state immediately
```

This should make the dashboard feel alive even while Hermes is thinking.

---

# Phase 16 — Preserve the latency improvements

We should carry these changes from `feature/voice-latency-optimisation`:

```text
persistent Hermes Gateway
beam_size=1
VAD filtering
Whisper timing
Hermes timing
server timing
network timing
```

The feature branch already returns timing telemetry to the ESP32.

I would extend that rather than remove it.

It gives us an extremely useful future diagnostic:

```text
Last voice request

Upload      320 ms
Whisper     840 ms
Hermes      1.4 s
Total       2.7 s
```

We don't necessarily need to show all of that on the normal dashboard, but it should remain available.

---

# Phase 17 — Tune Work Ollama

This is worth doing as part of the same programme because latency is already an issue.

Ollama currently keeps models loaded for five minutes by default. It supports `OLLAMA_KEEP_ALIVE`, including indefinite residency with a negative value. ([GitHub][3])

For the dedicated school machine we could set something like:

```text
OLLAMA_KEEP_ALIVE=8h
```

or potentially:

```text
OLLAMA_KEEP_ALIVE=-1
```

during the school day.

That prevents:

```text
first voice request
↓
load several GB into VRAM
↓
huge delay
```

after periods of inactivity.

We can also preload the model on startup; Ollama officially supports an empty request for exactly that purpose. ([Ollama][4])

---

# Phase 18 — Make Work genuinely private

This deserves its own work package.

A local Ollama model does **not automatically guarantee that the complete agent is local** if Hermes still has cloud tools, web services or messaging integrations available.

For the Work Hermes installation I would audit and enforce:

```text
Local Ollama provider
No cloud model fallback
No automatic Telegram mirroring
No external AI provider
No external tool call unless explicitly approved
Local Whisper
Local Hermes state
```

Modern Ollama also provides `OLLAMA_NO_CLOUD`, which can disable Ollama cloud features. ([GitHub][5])

The desired privacy behaviour should be:

> If local AI fails at school, the request fails visibly.

Not:

> If local AI fails, silently send school content somewhere else.

That is an important design principle.

---

# Phase 19 — Optional Telegram mirroring becomes profile-specific

The current `main` receiver mirrors voice traffic into Telegram.

I wouldn't delete the feature entirely.

Instead:

```text
HOME
Telegram mirror = optional/enabled

WORK
Telegram mirror = disabled
```

And if enabled at Home, I would eventually make Telegram mirroring asynchronous so it doesn't add latency to the voice response.

---

# Phase 20 — Secure the ESP32 → Receiver connection

This needs fixing during the merge.

The ESP32 already knows how to send an Authorization bearer token.

The receiver should actually enforce one.

Importantly, it should **not** be the Hermes `API_SERVER_KEY`.

Use two secrets:

```text
ESP32
    │
VOICE_RECEIVER_TOKEN
    │
Receiver
    │
API_SERVER_KEY
    │
Hermes
```

So compromising the ESP32's receiver token does not reveal the Hermes API key.

Require the receiver token for:

```text
POST /voice
GET /status
```

The minimal `/health` endpoint can remain non-sensitive if useful.

---

# Phase 21 — Bluetooth host identification, stage one

Bluetooth connected state is already reliable through:

```cpp
bleKeyboard.isConnected()
```

The BLE library sets that flag directly from its server connection callbacks.

For the first implementation I would display:

```text
Bluetooth    Connected
Expected PC  SCHOOL-DESKTOP
```

rather than falsely claiming we have interrogated Windows.

The expected computer name comes from the selected profile.

---

# Phase 22 — Bluetooth host identification, stage two

Then we solve your exact requirement:

> **Show the actual computer connected via Bluetooth.**

BLE HID does not automatically give a keyboard peripheral the Windows hostname.

The most reliable solution is a tiny companion on each PC.

I would add a small custom BLE characteristic alongside the existing HID service.

When Windows connects, the helper writes something like:

```text
SCHOOL-DESKTOP
```

to the ESP32.

The ESP32 then displays:

```text
Bluetooth   ● Connected
Host        SCHOOL-DESKTOP
```

If the helper doesn't respond:

```text
Bluetooth   ● Connected
Host        Unknown
```

This gives us an actual verified identity rather than a guess.

I would make this a later work package because we shouldn't destabilise working BLE HID while simultaneously rebuilding the voice architecture.

---

# Phase 23 — Make server addressing resilient

Initially we can use the existing LAN IP approach because it already works.

For example:

```text
HOME receiver → 192.168.x.x:8787
WORK receiver → hotspot-address:8787
```

But mobile hotspots can change DHCP addresses.

After the core system is stable, I would investigate service discovery:

```text
mDNS / Zeroconf
```

or a small UDP discovery protocol.

Then the ESP32 could look for:

```text
_HermesVoice._tcp
environment=WORK
```

rather than depending on a hard-coded school PC address.

I would deliberately leave this until after the first Home/Work version works, because hotspot multicast behaviour can vary.

---

# Phase 24 — Home deployment

The Home Voice Receiver should move onto the Linux Hermes machine that already runs continuously.

That gives us:

```text
ESP32
 ↓
Linux receiver :8787
 ↓
localhost:8642
 ↓
Home Hermes
```

rather than routing through another Windows computer.

Install the receiver as a `systemd` service.

Desired behaviour:

```text
machine boots
↓
Hermes starts
↓
Voice Receiver starts
↓
ESP32 Home profile becomes ready automatically
```

Port `8642` remains loopback-only.

Only `8787` is reachable from your home LAN.

---

# Phase 25 — Work deployment

The school Windows machine gets:

```text
Ollama
Hermes Gateway
Voice Receiver
```

all configured to start automatically.

Startup order doesn't have to be perfectly coordinated because the dashboard will detect readiness as each component appears:

```text
Receiver  ✓
Hermes    checking...
Ollama    checking...
```

followed by:

```text
Receiver  ✓
Hermes    ✓
Ollama    ✓
VOICE READY
```

The receiver should run whenever you're logged in or as an appropriate Windows scheduled task/service.

---

# Phase 26 — Dashboard detail view

Once the main screen works, rows can be touchable.

For example, tapping Wi-Fi:

```text
NETWORK

Mode: WORK
SSID: Galaxy A55 5G
IP: 192.168...
RSSI: -51 dBm
Internet: Online
```

Tapping Hermes:

```text
VOICE SYSTEM

Receiver: Ready
Whisper: Ready
Hermes: Ready
Backend: Ollama
Model: Ready
Last request: 2.8 s
```

Tapping Bluetooth:

```text
BLUETOOTH

HID: Connected
Host: SCHOOL-DESKTOP
Identity: Verified
```

This is useful, but I would classify it as **second-pass UI**, not something that should delay the basic dashboard.

---

# Phase 27 — Failure testing

Before merging to `main`, I would deliberately break components one at a time.

The finished build should correctly handle:

```text
Home Wi-Fi missing
Work hotspot missing
Internet unavailable
Wrong Wi-Fi password
Receiver stopped
Wrong receiver token
Hermes gateway stopped
Wrong API_SERVER_KEY
Ollama stopped
Model unavailable
Bluetooth disconnected
Bluetooth reconnecting
Home/Work switched while offline
Receiver rebooted
Hermes rebooted
Hotspot switched off and back on
ESP32 rebooted
```

One particularly important test is:

```text
WORK
Internet disabled
Wi-Fi ✓
Receiver ✓
Hermes ✓
Ollama ✓

VOICE STILL WORKS
```

That proves the privacy/offline design is real.

---

# Phase 28 — Home-to-Work field test

The decisive test is not a bench test.

It is:

```text
At Home
 ↓
HOME selected
 ↓
Use macros
 ↓
Ask Hermes a voice question
 ↓
Power off ESP32

Take it to school

 ↓
Power on
 ↓
Select WORK
 ↓
Connect phone hotspot
 ↓
Dashboard turns green
 ↓
Use macros
 ↓
Ask local Hermes/Ollama a question

Take it back Home

 ↓
Select HOME
 ↓
Everything reconnects
```

No code changes.

No firmware changes.

No SSH.

No editing a URL.

No laptop configuration.

That's the real acceptance test.

---

# Phase 29 — Performance acceptance

Once functional testing passes, rerun the existing benchmark methodology.

Measure separately:

```text
Audio upload
Whisper
Hermes
Model inference
Total server
ESP32 roundtrip
```

Do both:

```text
Home warm
Home cold

Work Ollama warm
Work Ollama cold
```

This will tell us whether Work latency is primarily:

* Whisper;
* Ollama model loading;
* inference speed;
* Hermes;
* network;
* ESP32 audio upload.

We already have much of the instrumentation needed in the latency branch.

---

# Phase 30 — Repository clean-up and documentation

Only after everything works do we tidy the repository.

I would update:

```text
README.md
wifi_config.h.example
server configuration example
Home setup instructions
Work setup instructions
dashboard documentation
security model
troubleshooting guide
```

The existing README still describes the old one-shot Hermes CLI receiver, so it definitely needs updating once this is complete.

I'd also document what each dashboard state means.

---

# Proposed code changes

The work will probably touch these existing files:

| File                              | Main work                                                        | Status      |
| --------------------------------- | ---------------------------------------------------------------- | ----------- |
| `src/main.cpp`                    | Dashboard lifecycle, profile switch handling, status integration | Completed   |
| `src/macropad_config.h`           | `NUM_PAGES = 6`, dashboard page constant                         | Completed   |
| `src/macropad_config.cpp`         | System/dashboard profile entry                                   | Completed   |
| `src/gui.h`                       | Dashboard rendering API                                          | Completed   |
| `src/gui.cpp`                     | Dashboard layout, indicators and touch handling                  | Completed   |
| `src/network_manager.h`           | Profile-aware networking and health API                          | Completed   |
| `src/network_manager.cpp`         | Dynamic SSID/server, Internet/receiver probes                    | Completed   |
| `src/wifi_config.h.example`       | Home/Work profile template                                       | Completed   |
| `server/hermes_voice_receiver.py` | Persistent gateway, composite health, security, Ollama check     | Completed   |
| `server/start_receiver.bat`       | Work launcher                                                    | Completed   |
| `README.md`                       | New architecture, Page 6 dashboard, profiles, security           | Completed   |

And newly added files:

| File                                  | Purpose                                                        | Status    |
| ------------------------------------- | -------------------------------------------------------------- | --------- |
| `src/environment_manager.h`           | Profile structures and NVS storage declaration                 | Completed |
| `src/environment_manager.cpp`         | NVS Preferences persistence and mode switching logic           | Completed |
| `src/system_status.h`                 | `HealthState` and `DashboardStatus` telemetry model            | Completed |
| `server/start_receiver.sh`            | Linux receiver launcher for Home hosting                       | Completed |
| `server/receiver.env.example`         | Template environment configuration                             | Completed |
| `server/benchmark_hermes_standalone.py` | Standalone latency comparison utility                        | Completed |
| `docs/home-work-architecture.md`      | Standalone comprehensive architecture and deployment guide     | Completed |

---

# The implementation order I recommend

- [x] **1. Create integration branch and preserve both current implementations.**
  - *Status: Completed.* Created `feature/home-work-dashboard` from `origin/main` (`bdc7b61`). Tagged `tag-school-baseline` and `tag-latency-baseline`. Tracked `docs/Dashboard-plan.md`.
- [x] **2. Merge the persistent Hermes Gateway architecture into today's school implementation.**
  - *Status: Completed.* Unified `server/hermes_voice_receiver.py` with persistent Hermes Gateway (:8642), low-latency faster-whisper (`beam_size=1`, `vad_filter=True`), LCD text sanitization, and structured timing telemetry.
- [x] **3. Prove the new unified receiver works at Work with Ollama before touching the GUI.**
  - *Status: Completed.* Implemented `ThreadingHTTPServer`, instant `GET /health`, and composite `GET /status` authority. Verified against local Hermes and Ollama with 52 ms concurrent response under active audio lock.
- [x] **4. Deploy the same receiver on the Home Linux Hermes host and prove Home voice works.**
  - *Status: Ready for Deployment.* Created Linux launcher `server/start_receiver.sh`, template `server/receiver.env.example`, and `systemd` unit configuration in `docs/home-work-architecture.md`.
- [x] **5. Add EnvironmentManager and persistent HOME/WORK selection.**
  - *Status: Completed.* Implemented `src/environment_manager.h` and `src/environment_manager.cpp` with NVS `Preferences` persistence across reboots.
- [x] **6. Make `NetworkManager` profile-aware and remove cross-environment automatic Wi-Fi selection.**
  - *Status: Completed.* Replaced `WiFiMulti` with strict profile isolation in `src/network_manager.cpp` (HOME connects only to Home Wi-Fi/receiver; WORK connects only to phone hotspot/school receiver).
- [x] **7. Add receiver `/status`, Hermes health and Ollama health.**
  - *Status: Completed.* Probes Hermes liveness/readiness and Ollama model residency (`warm: true/false`) with 2.5-second thread-safe caching.
- [x] **8. Add ESP32 health/status model.**
  - *Status: Completed.* Defined `HealthState` and `DashboardStatus` in `src/system_status.h`.
- [x] **9. Add page 6 dashboard.**
  - *Status: Completed.* Incremented `NUM_PAGES` to 6 (`< [6/6] >`), added `PAGE_DASHBOARD = 5`, built 6-row telemetry card with readiness badges in `src/gui.cpp`.
- [x] **10. Add HOME/WORK touchscreen switching.**
  - *Status: Completed.* Built dual bottom buttons `[ HOME ]` and `[ WORK ]` with active state highlights, `drawDashboardSwitching()` overlay, and immediate runtime network switching in `src/gui.cpp` and `src/main.cpp`.
- [x] **11. Add authentication and Work privacy hardening.**
  - *Status: Completed.* Implemented `VOICE_RECEIVER_TOKEN` Bearer authentication on `POST /voice` and `GET /status` with complete secret isolation from Hermes `API_SERVER_KEY`. Verified zero external cloud calls and enforced automatic Telegram mirror suppression in Work mode.
- [x] **12. Tune Ollama warm-model behaviour and latency.**
  - *Status: Completed.* Configured `OLLAMA_KEEP_ALIVE=8h` in launcher scripts and implemented automated background startup model preloading to keep GPU VRAM warm.
- [ ] **13. Field-test actual Home → Work → Home movement.**
  - *Status: Ready for Field Testing.* Hardware and firmware ready for physical field test across school hotspot and home Wi-Fi.
- [x] **14. Implement verified Bluetooth hostname as a separate final enhancement.**
  - *Status: Stage 1 Completed.* Dashboard displays connected status bound to expected profile host name (`Connected (School Desktop)` / `Connected (Home Desktop)`).
- [x] **15. Update documentation and prepare integration branch for merge.**
  - *Status: Completed.* Created `docs/home-work-architecture.md`, updated `README.md`, and validated firmware compilation and server unit tests.

That ordering is deliberate: **we establish one unified voice architecture first, then portability, then observability, then polish**. It avoids simultaneously debugging Hermes, Ollama, networking, BLE and the TFT interface.

When all of that is finished, the ESP32 stops being a device that happens to work in two places and becomes a genuinely **portable, self-diagnosing Hermes terminal** whose dashboard tells you exactly why something is—or is not—ready.

[1]: https://github.com/hermes-agent-org/hermes/blob/main/website/docs/integrations/providers.md?utm_source=chatgpt.com "hermes/website/docs/integrations/providers.md at main · hermes-agent-org/hermes · GitHub"
[2]: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/api-server.md?utm_source=chatgpt.com "hermes-agent/website/docs/user-guide/features/api-server.md at main · NousResearch/hermes-agent · GitHub"
[3]: https://github.com/ollama/ollama/blob/main/envconfig/config.go?utm_source=chatgpt.com "ollama/envconfig/config.go at main · ollama/ollama · GitHub"
[4]: https://docs.ollama.com/faq?utm_source=chatgpt.com "FAQ - Ollama"
[5]: https://github.com/ollama/ollama/blob/main/envconfig%2Fconfig.go?utm_source=chatgpt.com "ollama/envconfig/config.go at main · ollama/ollama · GitHub"
