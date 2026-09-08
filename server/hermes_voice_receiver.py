"""
Hermes Voice Satellite Receiver Service
Listens for HTTP POST audio/wav from the ESP32-S3 MacroPad on port 8765,
transcribes audio via local faster-whisper, sends the transcribed prompt
to Hermes, mirrors both prompt and reply to Telegram, and returns JSON to the ESP32.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
import subprocess
import tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(line_buffering=True, encoding='utf-8', errors='replace')

# ── 1. Configuration & Paths ──────────────────────────────────────────
PORT = 8787
HOST = "0.0.0.0"

HERMES_HOME = os.path.expanduser(r"~\AppData\Local\hermes")
HERMES_ENV_PATH = os.path.join(HERMES_HOME, ".env")
HERMES_BIN = os.path.join(HERMES_HOME, "bin", "hermes.exe")

# Load Telegram Credentials from Hermes .env if available
TELEGRAM_BOT_TOKEN = None
TELEGRAM_CHAT_ID = None

if os.path.exists(HERMES_ENV_PATH):
    with open(HERMES_ENV_PATH, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                TELEGRAM_BOT_TOKEN = line.split("=", 1)[1].strip()
            elif line.startswith("TELEGRAM_ALLOWED_USERS="):
                val = line.split("=", 1)[1].strip()
                if val:
                    TELEGRAM_CHAT_ID = val.split(",")[0].strip()
            elif line.startswith("TELEGRAM_HOME_CHANNEL=") and not TELEGRAM_CHAT_ID:
                val = line.split("=", 1)[1].strip()
                if val:
                    TELEGRAM_CHAT_ID = val

print(f"[Config] Telegram Token: {'Configured (' + TELEGRAM_BOT_TOKEN[:10] + '...)' if TELEGRAM_BOT_TOKEN else 'Not found'}")
print(f"[Config] Telegram Chat ID: {TELEGRAM_CHAT_ID or 'Not found'}")
print(f"[Config] Hermes Binary: {HERMES_BIN} ({'Found' if os.path.exists(HERMES_BIN) else 'Not found'})")

# ── 2. Whisper Model Loading ──────────────────────────────────────────
whisper_model = None

def get_whisper_model():
    global whisper_model
    if whisper_model is None:
        print("[Whisper] Initializing faster-whisper (model='base', device='cpu')...")
        try:
            from faster_whisper import WhisperModel
            whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
            print("[Whisper] Model loaded successfully!")
        except Exception as e:
            print(f"[Whisper] Failed to load faster-whisper: {e}")
    return whisper_model

# ── 3. Telegram Messenger Helper ──────────────────────────────────────
def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Telegram] Bot token or Chat ID not configured; skipping Telegram notification.")
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
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[Telegram] Error sending message: {e}")
        return False

# ── 4. Hermes Dispatcher & LLM Fallback ───────────────────────────────
def query_ollama(prompt):
    """Fallback to local Ollama if Hermes CLI is not present."""
    models_to_try = ["gemma3:latest", "llama3.1:latest", "qwen3.5:latest", "phi4:latest"]
    system_prompt = "You are a helpful voice assistant for an ESP32 desk device. Answer clearly in 1 or 2 concise sentences without markdown, bullets, or emojis."
    for model in models_to_try:
        try:
            req_data = json.dumps({
                "model": model,
                "prompt": f"{system_prompt}\n\nUser: {prompt}\nAssistant:",
                "stream": False
            }).encode("utf-8")
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=req_data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                reply = data.get("response", "").strip()
                if reply:
                    # Clean markdown and emojis for clean LCD display
                    clean = reply.replace("**", "").replace("*", "").replace("#", "").replace("`", "")
                    clean = "".join(c for c in clean if ord(c) < 128 or c.isalnum() or c in " .,!?'\"-")
                    return clean.strip()
        except Exception:
            continue
    return None

def run_hermes_prompt(prompt):
    if os.path.exists(HERMES_BIN):
        print(f"[Hermes] Executing prompt: '{prompt}'")
        cmd = [HERMES_BIN, "-z", prompt]
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
                encoding="utf-8",
                errors="replace"
            )
            reply = result.stdout.strip()
            if not reply and result.stderr:
                reply = f"Hermes note: {result.stderr.strip()[:200]}"
            if reply:
                return reply
        except subprocess.TimeoutExpired:
            return "Hermes processing timed out after 120s."
        except Exception as e:
            print(f"[Hermes] CLI error: {e}")

    # Fallback to local Ollama
    print(f"[LLM] Dispatching to local Ollama for: '{prompt}'")
    ollama_reply = query_ollama(prompt)
    if ollama_reply:
        return ollama_reply

    return "Received, but no AI model was available to reply."

# ── 5. HTTP Handler ───────────────────────────────────────────────────
class VoiceRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Health check endpoint
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        resp = {"status": "ok", "service": "hermes_voice_receiver", "port": PORT}
        self.wfile.write(json.dumps(resp).encode("utf-8"))

    def do_POST(self):
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

        print(f"\n[HTTP] Received {content_length} bytes of WAV audio from {self.client_address[0]}")
        audio_data = self.rfile.read(content_length)

        # Save to temporary WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            tmp_wav.write(audio_data)
            tmp_wav_path = tmp_wav.name

        try:
            # 1. Transcribe with Whisper
            model = get_whisper_model()
            transcript = ""
            if model:
                start_t = time.time()
                segments, info = model.transcribe(tmp_wav_path, beam_size=5, language="en")
                transcript = " ".join([seg.text for seg in segments]).strip()
                duration = time.time() - start_t
                print(f"[Whisper] Transcribed in {duration:.2f}s: \"{transcript}\"")

            if not transcript:
                transcript = "(unrecognized speech)"

            # 2. Mirror prompt to Telegram
            send_telegram_message(f"🎙️ *[ESP32 Voice Note]*\n🗣️ *You:* {transcript}")

            # 3. Execute Hermes
            reply = run_hermes_prompt(transcript)
            print(f"[Hermes] Reply: {reply[:120]}...")

            # 4. Mirror Hermes reply to Telegram
            send_telegram_message(f"🤖 *Hermes:*\n{reply}")

            # 5. Return JSON to ESP32
            response_payload = {
                "status": "ok",
                "transcript": transcript,
                "reply": reply[:100]  # First 100 chars for LCD display
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response_payload).encode("utf-8"))

        except Exception as e:
            print(f"[Error] Processing failed: {e}")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))

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
    print(f"  Local URL: http://localhost:{PORT}/voice")
    print(f"  LAN URL:   http://192.168.0.45:{PORT}/voice")
    print(f"=======================================================\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down receiver...")
        server.server_close()

if __name__ == "__main__":
    main()
