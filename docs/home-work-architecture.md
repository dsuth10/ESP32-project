# Portable Home/Work Architecture & System Dashboard Guide

This document describes the unified architecture for the **ESP32-S3 Touch MacroPad & Hermes Voice Satellite**, enabling zero-reflash portability between **Home** (Linux server) and **Work/School** (Windows PC + mobile phone hotspot) environments.

---

## 1. System Topology

The ESP32 communicates solely with a local **Voice Satellite Receiver** service running on port `:8787`, which in turn orchestrates with Hermes on localhost `:8642`.

```text
                           ESP32-S3 (ES3C28P)
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
               HOME Profile                  WORK Profile
                    │                             │
              Home Wi-Fi LAN                Phone Hotspot
                    │                             │
          Home Linux Server :8787         School Windows PC :8787
                    │                             │
            localhost:8642                localhost:8642
                    │                             │
             Hermes Gateway                Hermes Gateway
                    │                             │
           Configured Provider                  Ollama
                                                  │
                                            Local GPU Model
```

### Architectural Principles

1. **Strict Environment Binding**:
   - Each environment is an atomic composite profile:
     $$\text{Environment} = \{\text{SSID}, \text{Password}, \text{Receiver URL}, \text{Status URL}, \text{Timeout}, \text{Auth Token}, \text{Expected BLE Host}\}$$
   - Switching environments reconfigures the network stack simultaneously, preventing cross-subnet hangs.

2. **The Contract Principle**:
   - The ESP32 only ever talks to `:8787`.
   - The Receiver service on `:8787` is the authoritative health and AI proxy.
   - The ESP32 never bypasses the receiver or interrogates Ollama/Hermes directly.

3. **Zero-Reflash Portability**:
   - Mode selection (`HOME` vs `WORK`) is stored in ESP32 Non-Volatile Storage (NVS via Arduino `Preferences`) and survives power cycles and reboots.

---

## 2. Component Directory

| Component | Port / Interface | Role |
|---|---|---|
| **ESP32 MacroPad** | BLE HID + Wi-Fi | Key macro injection + 16kHz audio capture + 2.8" LCD GUI |
| **Voice Receiver** | HTTP `:8787` | Speech transcription (faster-whisper) + Health authority + Hermes dispatch |
| **Hermes Gateway** | HTTP `:8642` | Persistent agent session server (`/v1/chat/completions`, `/health`, `/health/detailed`) |
| **Local Ollama** | HTTP `:11434` | Local GPU LLM provider (Work mode offline intelligence) |

---

## 3. Security Model: Secret Separation

The architecture strictly separates peripheral credentials from backend API keys:

```text
ESP32 MacroPad
      │
      │  Authorization: Bearer <VOICE_RECEIVER_TOKEN>
      ▼
Voice Receiver (:8787)
      │
      │  Authorization: Bearer <API_SERVER_KEY>
      ▼
Hermes Gateway (:8642)
```

- **`VOICE_RECEIVER_TOKEN`**: Configured in `src/wifi_config.h` on the ESP32 and in the receiver's `.env`. Used to authenticate requests across the local Wi-Fi / hotspot network.
- **`API_SERVER_KEY`**: Kept exclusively on the host PC in `~/.hermes/.env`. Never exposed to the ESP32 or the Wi-Fi subnet.
- **Unauthenticated Probe**: `GET /health` remains open for lightweight pinging without credentials.

---

## 4. Work Privacy Hardening & Ollama Performance

To ensure school and enterprise privacy:
1. **Local-Only Inference**: All speech processing (Whisper) and LLM inference (Ollama) run on the workstation GPU.
2. **Automatic Telegram Mirroring Suppression**:
   - In `WORK` mode (`RECEIVER_ENV=work`), Telegram mirroring is automatically forced off to prevent voice audio or prompts from leaving the machine.
3. **Model Warmup & Keep-Alive**:
   - Work scripts launch Ollama with `OLLAMA_KEEP_ALIVE=8h` and `OLLAMA_NO_CLOUD=1`.
   - On receiver startup, a background thread issues a keep-alive preload request to ensure the model resides in GPU VRAM, eliminating first-query cold-start latency.

---

## 5. Page 6 System Dashboard

The firmware provides a dedicated telemetry card on Page 6 (`< [6/6] >`):

```text
┌──────────────────────────────────────────────┐
│ SYSTEM TELEMETRY         ALL SYSTEMS READY   │
├──────────────────────────────────────────────┤
│ ● Wi-Fi       Galaxy A55 5G (-48 dBm)        │
│ ● Internet    Online                         │
│ ● Bluetooth   Connected (School Desktop)     │
│ ● Voice Host  Online (:8787)                 │
│ ● Hermes      Ready (:8642)                  │
│ ● AI Model    Ollama • Warm                  │
├──────────────────────────────────────────────┤
│    [ SWITCH TO HOME ]      [ WORK ACTIVE ]   │
└──────────────────────────────────────────────┘
```

### Telemetry Status Semantics

- **Green (`HEALTH_READY`)**: Service is fully verified, reachable, and ready to respond.
- **Amber (`HEALTH_DEGRADED`)**:
  - `Internet`: Wi-Fi connected to local LAN / hotspot, but no WAN route (valid at school).
  - `Hermes`: Process is live (`/health` ok), but backend model is still loading.
- **Red (`HEALTH_FAILED`)**: Component is unreachable or returned an error code.
- **Grey (`HEALTH_UNKNOWN`)**: State has not yet been polled or is not required.

### Subsystem Decoupling

The dashboard evaluates two independent subsystems:
- **MacroPad Subsystem**: Requires Bluetooth connection to host (`bleKeyboard.isConnected()`).
- **Voice Subsystem**: Requires Wi-Fi + Voice Host + Hermes or Ollama.
- *Internet is never required for voice operation in Work mode.*

---

## 6. Host Setup Instructions

### Work Setup (Windows)

1. **Prerequisites**:
   - Install [Ollama for Windows](https://ollama.com/) and pull the desired model:
     ```cmd
     ollama pull qwen3.5:latest
     ```
   - Start Hermes Gateway on `:8642`:
     ```cmd
     hermes gateway
     ```

2. **Configure Environment**:
   - Copy `server/receiver.env.example` to `server/.env`:
     ```ini
     RECEIVER_PORT=8787
     RECEIVER_ENV=work
     VOICE_RECEIVER_TOKEN=your_token_here
     OLLAMA_HOST=http://127.0.0.1:11434
     OLLAMA_MODEL=qwen3.5:latest
     OLLAMA_KEEP_ALIVE=8h
     ```

3. **Start Receiver**:
   - Double-click `server/start_receiver.bat`.

---

### Home Setup (Linux Server)

1. **Configure Environment**:
   - Copy `server/receiver.env.example` to `/opt/hermes-voice/.env` or `~/.hermes/.env`:
     ```ini
     RECEIVER_PORT=8787
     RECEIVER_ENV=home
     VOICE_RECEIVER_TOKEN=c945e29742f53b370c07894f41e5251cd54738132de43f39
     HERMES_GATEWAY_URL=http://127.0.0.1:8642/v1/chat/completions
     API_SERVER_KEY=your_hermes_api_server_key
     ```

2. **Install as a Systemd Service**:
   Create `/etc/systemd/system/hermes-voice-receiver.service`:
   ```ini
   [Unit]
   Description=Hermes Voice Satellite Receiver
   After=network.target

   [Service]
   Type=simple
   User=hermes
   WorkingDirectory=/opt/hermes-voice
   ExecStart=/usr/bin/python3 hermes_voice_receiver.py
   Restart=on-failure
   RestartSec=5
   EnvironmentFile=/opt/hermes-voice/.env

   [Install]
   WantedBy=multi-user.target
   ```
   Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now hermes-voice-receiver
   ```
