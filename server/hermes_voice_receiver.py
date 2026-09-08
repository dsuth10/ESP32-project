"""
Hermes Voice Satellite Receiver Service (Unified Persistent Architecture)
Listens for HTTP POST audio/wav from the ESP32-S3 MacroPad on port 8787.
- STT: Local in-memory faster-whisper (beam_size=1, VAD filtered, int8 CPU).
- LLM Primary: Persistent Hermes Gateway (:8642/v1/chat/completions) via HTTP.
- LLM Fallback: Local Ollama (:11434) if Hermes Gateway is unreachable.
- Outputs: Telegram mirroring (optional) and structured JSON telemetry to ESP32.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
import tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(line_buffering=True, encoding='utf-8', errors='replace')

# ── 1. Configuration & Cross-Platform Path Resolution ──────────────────
PORT = int(os.environ.get("RECEIVER_PORT", "8787"))
HOST = os.environ.get("RECEIVER_HOST", "0.0.0.0")
GATEWAY_URL = os.environ.get("HERMES_GATEWAY_URL", "http://127.0.0.1:8642/v1/chat/completions")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODELS = [
    os.environ.get("OLLAMA_MODEL", "gemma3:latest"),
    "llama3.1:latest",
    "qwen3.5:latest",
    "phi4:latest"
]

API_SERVER_KEY = os.environ.get("API_SERVER_KEY")
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
                    elif k == "TELEGRAM_BOT_TOKEN" and not TELEGRAM_BOT_TOKEN:
                        TELEGRAM_BOT_TOKEN = v
                    elif k == "TELEGRAM_ALLOWED_USERS" and not TELEGRAM_CHAT_ID and v:
                        TELEGRAM_CHAT_ID = v.split(",")[0].strip()
                    elif k == "TELEGRAM_HOME_CHANNEL" and not TELEGRAM_CHAT_ID and v:
                        TELEGRAM_CHAT_ID = v
        except Exception as e:
            print(f"[Config] Note: Could not parse {env_path}: {e}")

print(f"[Config] Receiver Port  : {PORT} (host: {HOST})")
print(f"[Config] Hermes Gateway : {GATEWAY_URL}")
print(f"[Config] API Server Key : {'Configured (' + API_SERVER_KEY[:8] + '...)' if API_SERVER_KEY else 'MISSING (Set API_SERVER_KEY or ~/.hermes/.env)'}")
print(f"[Config] Ollama Host    : {OLLAMA_HOST}")
print(f"[Config] Telegram Mirror: {'Disabled' if DISABLE_TELEGRAM else ('Configured' if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID else 'Not configured')}")

# Concise system prompt tailored for the ESP32 MacroPad LCD display
ESP32_SYSTEM_PROMPT = (
    "You are responding to a voice query from a small ESP32 assistant display. "
    "Answer directly and concisely in 1 or 2 short sentences without markdown, bullets, or emojis. "
    "Keep ordinary factual answers under approximately 100-120 characters where practical."
)

# ── 2. Display Text Sanitizer ──────────────────────────────────────────
def sanitize_for_display(text: str) -> str:
    """Strips markdown and unsupported characters for clean display on ST7789 TFT screen."""
    if not text:
        return ""
    # Strip markdown syntax
    for ch in ["**", "*", "#", "`", "~~", "•", "■", "```"]:
        text = text.replace(ch, "")
    # Normalize whitespace and newlines
    text = " ".join(text.split())
    # Keep printable ASCII and basic punctuation
    clean = "".join(c for c in text if ord(c) < 128 or c.isalnum() or c in " .,!?'\"-")
    return clean.strip()

# ── 3. Whisper Model Loading (beam_size=1, VAD filtered, int8) ────────
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

# ── 4. Telegram Messenger Helper ──────────────────────────────────────
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

# ── 5. Hermes Gateway Dispatcher (Primary Architectural Path) ──────────
def ask_hermes_gateway(prompt: str) -> tuple[str, bool]:
    """
    Dispatches prompt to persistent Hermes Gateway via HTTP.
    Returns (reply_text, success_bool).
    """
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

# ── 6. Local Ollama Fallback (Transparent Diagnostic Fallback) ─────────
def query_ollama_fallback(prompt: str) -> tuple[str, bool]:
    """
    Diagnostic fallback querying local Ollama directly if Hermes Gateway is offline.
    Returns (reply_text, success_bool).
    """
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

# ── 7. HTTP Request Handler ───────────────────────────────────────────
class VoiceRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Health check endpoint
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        resp = {
            "status": "ok",
            "service": "hermes_voice_receiver",
            "port": PORT,
            "gateway_url": GATEWAY_URL,
            "whisper_loaded": whisper_model is not None,
            "ollama_host": OLLAMA_HOST
        }
        self.wfile.write(json.dumps(resp).encode("utf-8"))

    def do_POST(self):
        t_req_start = time.perf_counter()

        if self.path not in ["/voice", "/"]:
            self.send_response(404)
            self.end_headers()
            return

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

        try:
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

            # 6. Sanitize and return JSON response
            clean_reply = sanitize_for_display(reply)

            response_payload = {
                "status": "ok",
                "transcript": transcript,
                "reply": clean_reply[:120],
                "backend": backend_used,
                "timing": {
                    "body_read_ms": int(body_read_s * 1000),
                    "wav_write_ms": int(wav_write_s * 1000),
                    "whisper_ms": int(whisper_s * 1000),
                    "hermes_ms": int(hermes_s * 1000),
                    "server_ms": int(server_total_s * 1000)
                },
                # Flat telemetry keys for ESP32 lightweight JSON parser
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
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "error",
                "message": str(e),
                "server_ms": int((t_err_end - t_req_start) * 1000)
            }).encode("utf-8"))

        finally:
            if os.path.exists(tmp_wav_path):
                try:
                    os.remove(tmp_wav_path)
                except Exception:
                    pass

def main():
    # Warm up Whisper model in background
    get_whisper_model()

    server = HTTPServer((HOST, PORT), VoiceRequestHandler)
    print(f"\n=======================================================")
    print(f"  Hermes Voice Satellite Receiver Running on port {PORT}")
    print(f"  Local URL   : http://localhost:{PORT}/voice")
    print(f"  Gateway URL : {GATEWAY_URL}")
    print(f"  Ollama URL  : {OLLAMA_HOST}")
    print(f"=======================================================")
    print(f"  Primary LLM : Persistent Hermes Gateway (:8642)")
    print(f"  Fallback LLM: Local Ollama (:11434)")
    print(f"=======================================================\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down receiver...")
        server.server_close()

if __name__ == "__main__":
    main()
