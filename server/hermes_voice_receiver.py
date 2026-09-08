"""
Hermes Voice Satellite Receiver Service (Persistent Gateway Architecture)
Listens for HTTP POST audio/wav from the ESP32-S3 MacroPad on port 8787,
transcribes audio via local faster-whisper (in-memory, beam_size=1, VAD filtered),
sends prompt to persistent Hermes Gateway on http://127.0.0.1:8642 via HTTP,
and returns JSON response with timing telemetry to the ESP32.
"""

import os
import sys
import json
import time
import urllib.request
import tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── 1. Configuration & Paths ──────────────────────────────────────────
PORT = 8787
HOST = "0.0.0.0"
GATEWAY_URL = "http://127.0.0.1:8642/v1/chat/completions"

HERMES_HOME = os.path.expanduser(r"~\AppData\Local\hermes")
HERMES_ENV_PATH = os.path.join(HERMES_HOME, ".env")

# Load API_SERVER_KEY from Hermes .env or environment
API_SERVER_KEY = os.environ.get("API_SERVER_KEY")

if not API_SERVER_KEY and os.path.exists(HERMES_ENV_PATH):
    with open(HERMES_ENV_PATH, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("API_SERVER_KEY="):
                API_SERVER_KEY = line.split("=", 1)[1].strip()
                break

print(f"[Config] Hermes Gateway: {GATEWAY_URL}")
print(f"[Config] API Server Key : {'Configured (' + API_SERVER_KEY[:8] + '...)' if API_SERVER_KEY else 'MISSING (Check ~/.hermes/.env)'}")

# Concise system prompt tailored for the ESP32 MacroPad LCD display
ESP32_SYSTEM_PROMPT = (
    "You are responding to a voice query from a small ESP32 assistant display. "
    "Answer directly and concisely. Prefer one short sentence. "
    "Keep ordinary factual answers under approximately 100 characters where practical. "
    "Do not explain unless explanation is needed."
)

# ── 2. Whisper Model Loading ──────────────────────────────────────────
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

# ── 3. Hermes Gateway Dispatcher ──────────────────────────────────────
def ask_hermes_gateway(prompt: str) -> str:
    """Dispatches prompt to persistent Hermes Gateway via HTTP."""
    if not API_SERVER_KEY:
        return "Error: API_SERVER_KEY not configured on host."

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
            return reply or "Command acknowledged."
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        return f"Hermes Gateway HTTP {e.code}: {err_body[:100]}"
    except urllib.error.URLError as e:
        return f"Hermes Gateway unreachable: {e.reason}"
    except Exception as e:
        return f"Hermes Gateway error: {str(e)}"

# ── 4. HTTP Handler ───────────────────────────────────────────────────
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
            "whisper_loaded": whisper_model is not None
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

        try:
            # 3. Transcribe with Whisper (beam_size=1, VAD filter enabled)
            t_whisper_start = time.perf_counter()
            model = get_whisper_model()
            transcript = ""
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

            # 4. Query Persistent Hermes Gateway
            t_hermes_start = time.perf_counter()
            reply = ask_hermes_gateway(transcript)
            t_hermes_end = time.perf_counter()
            hermes_s = t_hermes_end - t_hermes_start

            t_server_end = time.perf_counter()
            server_total_s = t_server_end - t_req_start

            # Structured console performance logging
            print("\n========== VOICE REQUEST ==========")
            print(f"WAV received  : {content_length} bytes from {self.client_address[0]}")
            print(f"[PERF] body_read   : {body_read_s:6.2f} s")
            print(f"[PERF] wav_write   : {wav_write_s:6.2f} s")
            print(f"[PERF] whisper     : {whisper_s:6.2f} s")
            print(f"[PERF] hermes      : {hermes_s:6.2f} s")
            print("-----------------------------------")
            print(f"[PERF] SERVER TOTAL: {server_total_s:6.2f} s")
            print(f"[STT ] {transcript}")
            print(f"[AI  ] {reply}")
            print("===================================\n")

            # 5. Return JSON to ESP32
            response_payload = {
                "status": "ok",
                "transcript": transcript,
                "reply": reply[:120],  # Keep formatted for LCD display
                "timing": {
                    "body_read_ms": int(body_read_s * 1000),
                    "wav_write_ms": int(wav_write_s * 1000),
                    "whisper_ms": int(whisper_s * 1000),
                    "hermes_ms": int(hermes_s * 1000),
                    "server_ms": int(server_total_s * 1000)
                }
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
    print(f"  Local URL:   http://localhost:{PORT}/voice")
    print(f"  LAN URL:     http://192.168.0.45:{PORT}/voice")
    print(f"  Gateway URL: {GATEWAY_URL}")
    print(f"=======================================================\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down receiver...")
        server.server_close()

if __name__ == "__main__":
    main()
