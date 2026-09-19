---
name: voice-satellite
description: Operational runbook and troubleshooting toolkit for the Hermes Voice Satellite receiver, Ollama local inference, Windows audio output, and ESP32 connectivity.
---

# Voice Satellite Operations Runbook

Use this skill when managing the host-side Voice Satellite receiver (`:8787`), Hermes gateway (`:8642`), or Ollama (`:11434`).

## Quick Health Check
```powershell
# Check listening ports
netstat -ano | findstr /R "8787 8642 11434"

# Check receiver status
curl http://127.0.0.1:8787/status
```

## Starting the Voice Receiver Daemon
```powershell
C:\Python312\python.exe -u server\hermes_voice_receiver.py
```

## Pre-Warming Ollama in GPU VRAM
```powershell
curl http://127.0.0.1:11434/api/generate -d '{"model":"gemma3:latest","prompt":"hi","stream":false,"keep_alive":"8h"}'
```

## Verifying Host Speakers & Audio Pipeline
To test Whisper transcription, Ollama LLM response, Host Speaker playback, and ESP32 16kHz stereo WAV generation:
```powershell
C:\Python312\python.exe -c "
import urllib.request, json, win32com.client
# 1. Generate test WAV
stream = win32com.client.Dispatch('SAPI.SpFileStream')
stream.Format.Type = 22 # 16kHz Stereo
stream.Open('test.wav', 3)
voice = win32com.client.Dispatch('SAPI.SpVoice')
voice.AudioOutputStream = stream
voice.Speak('Test audio pipeline')
stream.Close()
# 2. POST to receiver
with open('test.wav', 'rb') as f:
    data = f.read()
req = urllib.request.Request('http://127.0.0.1:8787/voice?audio=1', data=data, headers={'Content-Type': 'audio/wav'})
with urllib.request.urlopen(req) as resp:
    print(json.loads(resp.read().decode()))
"
```

## Mobile Hotspot Connection Troubleshooting (Reason 15)
If ESP32 fails to connect to phone hotspot with `Reason: 15` (`WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT`):
1. Open Hotspot settings on phone (Samsung/Android/iOS).
2. Ensure Security is set to **WPA2-Personal** (not WPA2/WPA3 Personal / Transition mode).
3. Ensure Wi-Fi band is set to **2.4 GHz**.
4. In ESP32 code, verify `WiFi.disconnect(false, true)` runs before `WiFi.begin()`.
5. Ensure Wi-Fi modem sleep is NOT disabled (`WIFI_PS_MIN_MODEM`).
