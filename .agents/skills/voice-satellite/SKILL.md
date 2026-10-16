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

## Hybrid Fast Lane
Chat questions go to Groq (or local Ollama). Tool, live-data, and device-action requests go to the Hermes agent.

Set these in `%LOCALAPPDATA%\hermes\.env` or `server/.env` (already git-ignored):

```
FAST_LLM_PROVIDER=groq
FAST_LLM_MODEL=qwen/qwen3.8-27b
GROQ_API_KEY=gsk_...
HERMES_VOICE_PROVIDER=custom:groq-voice
HERMES_VOICE_MODEL=openai/gpt-oss-20b
HERMES_REASONING_EFFORT=low
HERMES_AGENT_TIMEOUT_S=25
STT_PROVIDER=local
```

Get a Groq key at https://console.groq.com/keys. Until `GROQ_API_KEY` is set, the fast lane falls back to the warm local Ollama model. `FAST_LLM_PROVIDER=off` restores the legacy order (work: Ollama then Hermes, home: Hermes then Ollama).

Restart the receiver after changing these values. Hermes also needs a restart after `custom_providers` changes in `%LOCALAPPDATA%\hermes\config.yaml`.

## LLM Path Benchmark
Times every inference path (local Ollama, Ollama Cloud, Hermes session/OpenAI/CLI, Groq) and scores replies from `server/bench_prompts.json`.

```powershell
# List paths
C:\Python312\python.exe server\bench_llm_paths.py --list

# Full run (direct paths 3 rounds, Hermes paths 1 round)
C:\Python312\python.exe server\bench_llm_paths.py

# Also compare STT engines and POST spoken fixtures to the running receiver
C:\Python312\python.exe server\bench_llm_paths.py --stt --e2e

# Re-benchmark only the Hermes agent after pointing it at Groq
C:\Python312\python.exe server\bench_llm_paths.py --only hermes-session,hermes-session-low,hermes-session+groq
```

Results land in `server/bench_results/` (git-ignored). Ranking uses warm p50 total time among paths with accuracy >= 0.8.

## Mobile Hotspot Connection Troubleshooting (Reason 15)
If ESP32 fails to connect to phone hotspot with `Reason: 15` (`WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT`):
1. Open Hotspot settings on phone (Samsung/Android/iOS).
2. Ensure Security is set to **WPA2-Personal** (not WPA2/WPA3 Personal / Transition mode).
3. Ensure Wi-Fi band is set to **2.4 GHz**.
4. In ESP32 code, verify `WiFi.disconnect(false, true)` runs before `WiFi.begin()`.
5. Ensure Wi-Fi modem sleep is NOT disabled (`WIFI_PS_MIN_MODEM`).
