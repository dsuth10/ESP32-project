"""
Hermes Voice Satellite Receiver Service (Concurrent Health Authority Architecture)
Listens for HTTP requests on port 8787 using ThreadingHTTPServer:
- POST /voice  : Upload WAV audio, transcribe via faster-whisper, query Hermes Gateway (:8642)
                 with transparent Ollama (:11434) fallback. Concurrency protected by voice_lock.
- GET  /health : Lightweight instant liveness probe for fast ping/keep-alive.
- GET  /status : Composite health authority endpoint providing deep diagnostic state for Hermes,
                 Ollama model residency, Whisper, and last voice telemetry.
"""

import os
import sys
import json
import time
import threading
import urllib.request
import urllib.parse
import tempfile
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(line_buffering=True, encoding='utf-8', errors='replace')

# ── 1. Configuration & Cross-Platform Path Resolution ──────────────────
PORT = int(os.environ.get("RECEIVER_PORT", "8787"))
HOST = os.environ.get("RECEIVER_HOST", "0.0.0.0")
RECEIVER_ENV = os.environ.get("RECEIVER_ENV", "work" if sys.platform == "win32" else "home")
GATEWAY_URL = os.environ.get("HERMES_GATEWAY_URL", "http://127.0.0.1:8642/v1/chat/completions")
HERMES_BASE_URL = os.environ.get("HERMES_BASE_URL", "http://127.0.0.1:8642")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODELS = [
    os.environ.get("OLLAMA_MODEL", "qwen3.5:latest"),
    "llama3.2:latest",
    "gemma3:latest",
    "phi4-mini:3.8b",
    "ministral-3:latest"
]

API_SERVER_KEY = os.environ.get("API_SERVER_KEY")
VOICE_RECEIVER_TOKEN = os.environ.get("VOICE_RECEIVER_TOKEN")
OLLAMA_KEEP_ALIVE = os.environ.get("OLLAMA_KEEP_ALIVE", "8h" if RECEIVER_ENV == "work" else "5m")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DISABLE_TELEGRAM = os.environ.get("DISABLE_TELEGRAM", "").lower() in ("1", "true", "yes")

# Look for credentials across standard cross-platform Hermes locations
hermes_env_candidates = [
    os.path.expanduser("~/.hermes/.env"),
    os.path.expanduser(r"~\AppData\Local\hermes\.env"),
    os.path.join(os.path.dirname(__file__), ".env")
]

for env_path in hermes_env_candidates:
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if k == "API_SERVER_KEY" and not API_SERVER_KEY:
                        API_SERVER_KEY = v
                    elif k == "VOICE_RECEIVER_TOKEN" and not VOICE_RECEIVER_TOKEN:
                        VOICE_RECEIVER_TOKEN = v
                    elif k == "OLLAMA_KEEP_ALIVE" and "OLLAMA_KEEP_ALIVE" not in os.environ:
                        OLLAMA_KEEP_ALIVE = v
                    elif k == "TELEGRAM_BOT_TOKEN" and not TELEGRAM_BOT_TOKEN:
                        TELEGRAM_BOT_TOKEN = v
                    elif k == "TELEGRAM_ALLOWED_USERS" and not TELEGRAM_CHAT_ID and v:
                        TELEGRAM_CHAT_ID = v.split(",")[0].strip()
                    elif k == "TELEGRAM_HOME_CHANNEL" and not TELEGRAM_CHAT_ID and v:
                        TELEGRAM_CHAT_ID = v
        except Exception as e:
            print(f"[Config] Note: Could not parse {env_path}: {e}")

# Phase 18 & 19: Enforce strict Work privacy hardening
if RECEIVER_ENV.lower() == "work":
    DISABLE_TELEGRAM = True

print(f"[Config] Environment    : {RECEIVER_ENV.upper()}")
print(f"[Config] Receiver Port  : {PORT} (host: {HOST})")
print(f"[Config] Receiver Token : {'Enforced (Bearer auth enabled)' if VOICE_RECEIVER_TOKEN else 'None (Open access / unauthenticated)'}")
print(f"[Config] Hermes Gateway : {GATEWAY_URL}")
print(f"[Config] API Server Key : {'Configured (' + API_SERVER_KEY[:8] + '...)' if API_SERVER_KEY else 'MISSING (Set API_SERVER_KEY or ~/.hermes/.env)'}")
print(f"[Config] Ollama Host    : {OLLAMA_HOST} (keep_alive: {OLLAMA_KEEP_ALIVE})")
print(f"[Config] Telegram Mirror: {'Disabled (Work Mode / Privacy Hardened)' if RECEIVER_ENV.lower() == 'work' else ('Disabled' if DISABLE_TELEGRAM else ('Configured' if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID else 'Not configured'))}")

# Concise system prompt tailored for the ESP32 MacroPad LCD display
ESP32_SYSTEM_PROMPT = (
    "You are responding to a voice query from a small ESP32 assistant display. "
    "Answer directly and concisely in 1 or 2 short sentences without markdown, bullets, or emojis. "
    "Keep ordinary factual answers under approximately 100-120 characters where practical."
)

# ── 2. Synchronization & Global State ─────────────────────────────────
voice_lock = threading.Lock()

last_voice_record = {
    "transcript": "",
    "reply": "",
    "backend": "none",
    "success": False,
    "timestamp": 0.0,
    "timing": {}
}
last_voice_lock = threading.Lock()

_status_cache = None
_status_cache_time = 0.0
_status_cache_lock = threading.Lock()
STATUS_CACHE_TTL = 2.5  # Cache status probe results for 2.5 seconds

# ── 3. Display Text Sanitizer ──────────────────────────────────────────
def sanitize_for_display(text: str) -> str:
    """Strips markdown and unsupported characters for clean display on ST7789 TFT screen."""
    if not text:
        return ""
    for ch in ["**", "*", "#", "`", "~~", "•", "■", "```"]:
        text = text.replace(ch, "")
    text = " ".join(text.split())
    clean = "".join(c for c in text if ord(c) < 128 or c.isalnum() or c in " .,!?'\"-")
    return clean.strip()

# ── 4. Whisper Model Loading (beam_size=1, VAD filtered, int8) ────────
whisper_model = None

def get_whisper_model():
    global whisper_model
    if whisper_model is None:
        print("[Whisper] Initializing faster-whisper (model='base', device='cpu', int8)...")
        try:
            from faster_whisper import WhisperModel
            whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
            print("[Whisper] Model loaded successfully!")
        except Exception as e:
            print(f"[Whisper] Failed to load faster-whisper: {e}")
    return whisper_model

# ── 5. Telegram Messenger Helper ──────────────────────────────────────
def send_telegram_message(text: str) -> bool:
    if DISABLE_TELEGRAM or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[Telegram] Error sending message: {e}")
        return False

# ── 6. Hermes Gateway Dispatcher (Primary Architectural Path) ──────────
def ask_hermes_gateway(prompt: str) -> tuple[str, bool]:
    """Dispatches prompt to persistent Hermes Gateway via HTTP."""
    if not API_SERVER_KEY:
        return ("Error: API_SERVER_KEY not configured on host.", False)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_SERVER_KEY}"
    }

    payload = json.dumps({
        "model": "hermes-agent",
        "messages": [
            {"role": "system", "content": ESP32_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 150
    }).encode("utf-8")

    req = urllib.request.Request(GATEWAY_URL, data=payload, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            reply = data["choices"][0]["message"]["content"].strip()
            return (reply or "Command acknowledged.", True)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        return (f"Hermes Gateway HTTP {e.code}: {err_body[:100]}", False)
    except urllib.error.URLError as e:
        return (f"Hermes Gateway unreachable: {e.reason}", False)
    except Exception as e:
        return (f"Hermes Gateway error: {str(e)}", False)

# ── 7. Local Ollama Fallback (Transparent Diagnostic Fallback) ─────────
def query_ollama_fallback(prompt: str) -> tuple[str, bool]:
    """Diagnostic fallback querying local Ollama directly if Hermes Gateway is offline."""
    for model in OLLAMA_MODELS:
        try:
            req_data = json.dumps({
                "model": model,
                "prompt": f"{ESP32_SYSTEM_PROMPT}\n\nUser: {prompt}\nAssistant:",
                "stream": False
            }).encode("utf-8")
            url = f"{OLLAMA_HOST.rstrip('/')}/api/generate"
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                reply = data.get("response", "").strip()
                if reply:
                    return (reply, True)
        except Exception:
            continue
    return ("Ollama unreachable or model not found", False)

# ── 8. Health Authority Deep Probe Logic ───────────────────────────────
def probe_hermes_health() -> dict:
    """Probes Hermes Gateway for liveness and detailed readiness."""
    t0 = time.perf_counter()
    live = False
    ready = False
    version = None
    gateway_state = None
    err = None

    try:
        health_url = f"{HERMES_BASE_URL.rstrip('/')}/health"
        with urllib.request.urlopen(health_url, timeout=1.5) as resp:
            if resp.status == 200:
                live = True
                try:
                    data = json.loads(resp.read().decode("utf-8"))
                    version = data.get("version")
                except Exception:
                    pass
    except Exception as e:
        err = f"Liveness probe failed: {e}"

    if live and API_SERVER_KEY:
        try:
            detailed_url = f"{HERMES_BASE_URL.rstrip('/')}/health/detailed"
            req = urllib.request.Request(
                detailed_url,
                headers={"Authorization": f"Bearer {API_SERVER_KEY}"}
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    ready = (data.get("status") == "ok")
                    gateway_state = data.get("gateway_state")
                    if not version:
                        version = data.get("version")
        except Exception as e:
            # Liveness ok but detailed check failed or not ready
            err = f"Readiness probe note: {e}"
    elif live:
        # Liveness is good, but API_SERVER_KEY missing on host
        ready = False
        err = "API_SERVER_KEY not configured"

    latency_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "live": live,
        "ready": ready,
        "latency_ms": latency_ms,
        "version": version,
        "gateway_state": gateway_state,
        "error": err
    }

def warmup_ollama_model():
    """Phase 17: Preload the active Ollama model into GPU VRAM to prevent first-query cold load delays."""
    if not OLLAMA_MODELS:
        return
    model = OLLAMA_MODELS[0]
    try:
        req_data = json.dumps({
            "model": model,
            "keep_alive": OLLAMA_KEEP_ALIVE
        }).encode("utf-8")
        url = f"{OLLAMA_HOST.rstrip('/')}/api/generate"
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"[Ollama] Preloading model '{model}' (keep_alive: {OLLAMA_KEEP_ALIVE})...")
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                print(f"[Ollama] Model '{model}' successfully warmed up in VRAM!")
    except Exception as e:
        print(f"[Ollama] Note: Model preload note / deferred: {e}")

def probe_ollama_health() -> dict:
    """Probes local Ollama for service reachability and model VRAM residency."""
    ready = False
    warm = False
    running_models = []
    installed_models = []
    err = None

    try:
        tags_url = f"{OLLAMA_HOST.rstrip('/')}/api/tags"
        with urllib.request.urlopen(tags_url, timeout=1.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                installed_models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                ready = True
    except Exception as e:
        err = f"Ollama tags probe failed: {e}"

    if ready:
        try:
            ps_url = f"{OLLAMA_HOST.rstrip('/')}/api/ps"
            with urllib.request.urlopen(ps_url, timeout=1.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    running_models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                    warm = len(running_models) > 0
        except Exception:
            pass

    return {
        "type": "ollama",
        "host": OLLAMA_HOST,
        "ready": ready,
        "warm": warm,
        "model": OLLAMA_MODELS[0] if OLLAMA_MODELS else "unknown",
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "warm_models": running_models,
        "available_models": installed_models[:6],
        "error": err
    }

def get_composite_status() -> dict:
    """Returns composite health authority state, cached for 2.5 seconds to minimize overhead."""
    global _status_cache, _status_cache_time

    now = time.time()
    with _status_cache_lock:
        if _status_cache and (now - _status_cache_time) < STATUS_CACHE_TTL:
            # Update dynamic receiver flags in cached object
            _status_cache["receiver"]["voice_in_progress"] = voice_lock.locked()
            with last_voice_lock:
                _status_cache["last_voice"] = dict(last_voice_record)
            return _status_cache

    hermes_info = probe_hermes_health()
    ollama_info = probe_ollama_health()

    # Determine overall status
    if hermes_info["ready"]:
        overall_status = "ok"
    elif hermes_info["live"]:
        overall_status = "degraded"
    elif ollama_info["ready"]:
        overall_status = "degraded"  # Hermes offline, but local Ollama fallback ready
    else:
        overall_status = "offline"

    with last_voice_lock:
        lv = dict(last_voice_record)

    status_data = {
        "status": overall_status,
        "environment": RECEIVER_ENV,
        "receiver": {
            "ready": True,
            "whisper": whisper_model is not None,
            "voice_in_progress": voice_lock.locked(),
            "port": PORT
        },
        "hermes": hermes_info,
        "backend": ollama_info,
        "last_voice": lv
    }

    with _status_cache_lock:
        _status_cache = status_data
        _status_cache_time = now

    return status_data

# ── 9. HTTP Request Handler (Concurrent) ──────────────────────────────
class VoiceRequestHandler(BaseHTTPRequestHandler):
    def check_auth(self) -> bool:
        """Phase 20: Validate Authorization: Bearer <VOICE_RECEIVER_TOKEN> if configured."""
        if not VOICE_RECEIVER_TOKEN:
            return True
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False
        token = auth_header[7:].strip()
        return token == VOICE_RECEIVER_TOKEN

    def send_unauthorized(self):
        self.send_response(401)
        self.send_header("Content-Type", "application/json")
        self.send_header("WWW-Authenticate", 'Bearer realm="HermesVoiceReceiver"')
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "error",
            "message": "Unauthorized: Invalid or missing bearer token"
        }).encode("utf-8"))

    def do_GET(self):
        url_parts = urllib.parse.urlparse(self.path)
        path = url_parts.path.rstrip('/')

        # 1. Lightweight health check (Phase 3) - unauthenticated for fast liveness probing
        if path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
            return

        # 2. Composite Health Authority status (Phase 3 & 4) - protected by Bearer token
        if path == "/status":
            if not self.check_auth():
                self.send_unauthorized()
                return
            composite = get_composite_status()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(composite, indent=2).encode("utf-8"))
            return

        # 3. Root index / summary
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        resp = {
            "status": "ok",
            "service": "hermes_voice_receiver",
            "environment": RECEIVER_ENV,
            "port": PORT,
            "endpoints": [
                "GET /health",
                "GET /status",
                "POST /voice"
            ],
            "whisper_loaded": whisper_model is not None,
            "voice_busy": voice_lock.locked()
        }
        self.wfile.write(json.dumps(resp, indent=2).encode("utf-8"))

    def do_POST(self):
        t_req_start = time.perf_counter()

        if self.path not in ["/voice", "/voice/", "/"]:
            self.send_response(404)
            self.end_headers()
            return

        # Check Bearer Authentication (Phase 20)
        if not self.check_auth():
            self.send_unauthorized()
            return

        # Enforce audio lock: allow only one active voice inference at a time
        if not voice_lock.acquire(blocking=False):
            print(f"[HTTP] 429 Busy: Voice processing already active for another request")
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "busy",
                "message": "Voice processing currently in progress"
            }).encode("utf-8"))
            return

        tmp_wav_path = None
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 44:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Audio payload too short"}).encode("utf-8"))
                return

            # 1. Read Audio Data
            t_read_start = time.perf_counter()
            audio_data = self.rfile.read(content_length)
            t_read_end = time.perf_counter()
            body_read_s = t_read_end - t_read_start

            # 2. Write Temporary WAV File
            t_write_start = time.perf_counter()
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
                tmp_wav.write(audio_data)
                tmp_wav_path = tmp_wav.name
            t_write_end = time.perf_counter()
            wav_write_s = t_write_end - t_write_start

            whisper_s = 0.0
            hermes_s = 0.0
            transcript = ""
            reply = ""
            backend_used = "none"

            # 3. Transcribe with Whisper (beam_size=1, VAD filter enabled)
            t_whisper_start = time.perf_counter()
            model = get_whisper_model()
            if model:
                segments, info = model.transcribe(
                    tmp_wav_path,
                    beam_size=1,
                    vad_filter=True,
                    language="en"
                )
                transcript = " ".join([seg.text for seg in segments]).strip()

            t_whisper_end = time.perf_counter()
            whisper_s = t_whisper_end - t_whisper_start

            if not transcript:
                transcript = "(unrecognized speech)"

            # 4. Query Persistent Hermes Gateway (Primary Path)
            t_hermes_start = time.perf_counter()
            reply, hermes_ok = ask_hermes_gateway(transcript)
            backend_used = "hermes-gateway"

            if not hermes_ok:
                print(f"[WARN] Hermes Gateway unavailable ({reply}). Attempting Ollama fallback...")
                ollama_reply, ollama_ok = query_ollama_fallback(transcript)
                if ollama_ok:
                    reply = ollama_reply
                    backend_used = "ollama-direct-fallback"
                    print(f"[WARN] Used local Ollama fallback for prompt.")
                else:
                    print(f"[WARN] Both Hermes Gateway and Ollama failed.")

            t_hermes_end = time.perf_counter()
            hermes_s = t_hermes_end - t_hermes_start

            t_server_end = time.perf_counter()
            server_total_s = t_server_end - t_req_start

            # 5. Mirror to Telegram if enabled
            if not DISABLE_TELEGRAM:
                send_telegram_message(f"🎙️ *[ESP32 Voice Note]*\n🗣️ *You:* {transcript}")
                send_telegram_message(f"🤖 *Hermes ({backend_used}):*\n{reply}")

            # Structured console performance logging
            print("\n========== VOICE REQUEST ==========")
            print(f"WAV received  : {content_length} bytes from {self.client_address[0]}")
            print(f"Backend used  : {backend_used}")
            print(f"[PERF] body_read   : {body_read_s:6.2f} s")
            print(f"[PERF] wav_write   : {wav_write_s:6.2f} s")
            print(f"[PERF] whisper     : {whisper_s:6.2f} s")
            print(f"[PERF] hermes/llm  : {hermes_s:6.2f} s")
            print("-----------------------------------")
            print(f"[PERF] SERVER TOTAL: {server_total_s:6.2f} s")
            print(f"[STT ] {transcript}")
            print(f"[AI  ] {reply}")
            print("===================================\n")

            # 6. Sanitize and update last_voice_record
            clean_reply = sanitize_for_display(reply)

            timing_dict = {
                "body_read_ms": int(body_read_s * 1000),
                "wav_write_ms": int(wav_write_s * 1000),
                "whisper_ms": int(whisper_s * 1000),
                "hermes_ms": int(hermes_s * 1000),
                "server_ms": int(server_total_s * 1000)
            }

            with last_voice_lock:
                last_voice_record["transcript"] = transcript
                last_voice_record["reply"] = clean_reply[:120]
                last_voice_record["backend"] = backend_used
                last_voice_record["success"] = True
                last_voice_record["timestamp"] = time.time()
                last_voice_record["timing"] = timing_dict

            response_payload = {
                "status": "ok",
                "transcript": transcript,
                "reply": clean_reply[:120],
                "backend": backend_used,
                "timing": timing_dict,
                "server_ms": int(server_total_s * 1000),
                "whisper_ms": int(whisper_s * 1000),
                "hermes_ms": int(hermes_s * 1000)
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response_payload).encode("utf-8"))

        except Exception as e:
            t_err_end = time.perf_counter()
            print(f"[Error] Processing failed: {e}")

            with last_voice_lock:
                last_voice_record["success"] = False
                last_voice_record["reply"] = str(e)[:100]
                last_voice_record["timestamp"] = time.time()

            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "error",
                "message": str(e),
                "server_ms": int((t_err_end - t_req_start) * 1000)
            }).encode("utf-8"))

        finally:
            if tmp_wav_path and os.path.exists(tmp_wav_path):
                try:
                    os.remove(tmp_wav_path)
                except Exception:
                    pass
            voice_lock.release()

def main():
    # Warm up Whisper model in background
    get_whisper_model()

    # Phase 17: Pre-warm Ollama model in background thread to prevent cold start latency
    threading.Thread(target=warmup_ollama_model, daemon=True).start()

    server = ThreadingHTTPServer((HOST, PORT), VoiceRequestHandler)
    server.daemon_threads = True

    print(f"\n=======================================================")
    print(f"  Hermes Voice Satellite Receiver Running on port {PORT}")
    print(f"  Architecture : ThreadingHTTPServer (Concurrent Health)")
    print(f"  Endpoints    : GET /health | GET /status | POST /voice")
    print(f"  Gateway URL  : {GATEWAY_URL}")
    print(f"  Ollama URL   : {OLLAMA_HOST}")
    print(f"=======================================================")
    print(f"  Primary LLM  : Persistent Hermes Gateway (:8642)")
    print(f"  Fallback LLM : Local Ollama (:11434)")
    print(f"=======================================================\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down receiver...")
        server.server_close()

if __name__ == "__main__":
    main()
