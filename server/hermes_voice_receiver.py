"""
Hermes Voice Satellite Receiver Service (Concurrent Health Authority Architecture)
Listens for HTTP requests on port 8787 using ThreadingHTTPServer:
- POST /voice  : Upload WAV audio, transcribe via faster-whisper, then answer through either the
                 hybrid fast lane (FAST_LLM_PROVIDER=groq|ollama: chat -> fast LLM, tool/action
                 requests -> Hermes agent) or the legacy Hermes/Ollama order. Protected by voice_lock.
- GET  /health : Lightweight instant liveness probe for fast ping/keep-alive.
- GET  /status : Composite health authority endpoint providing deep diagnostic state for Hermes,
                 Ollama model residency, fast lane, Whisper, and last voice telemetry.
"""

import os
import sys
import json
import time
import io
import wave
import math
import re
import uuid
import pathlib
import threading
import http.client
import urllib.error
import urllib.request
import urllib.parse
import tempfile
import socket
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

try:
    import numpy as np
    import scipy.signal
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(line_buffering=True, encoding='utf-8', errors='replace')

# ── 1. Configuration & Cross-Platform Path Resolution ──────────────────
PORT = int(os.environ.get("RECEIVER_PORT", "8787"))
HOST = os.environ.get("RECEIVER_HOST", "0.0.0.0")
DISCOVERY_UDP_PORT = int(os.environ.get("DISCOVERY_UDP_PORT", "8788"))
RECEIVER_ENV = os.environ.get("RECEIVER_ENV", "work" if sys.platform == "win32" else "home")
GATEWAY_URL = os.environ.get("HERMES_GATEWAY_URL", "http://127.0.0.1:8642/v1/chat/completions")
HERMES_BASE_URL = os.environ.get("HERMES_BASE_URL", "http://127.0.0.1:8642")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODELS = [
    os.environ.get("OLLAMA_MODEL", "llama3.2:latest" if RECEIVER_ENV == "work" else "qwen3.5:latest"),
    "llama3.2:latest",
    "phi4-mini:3.8b",
    "qwen3.5:latest",
    "mistral:latest"
]

API_SERVER_KEY = os.environ.get("API_SERVER_KEY")
VOICE_RECEIVER_TOKEN = os.environ.get("VOICE_RECEIVER_TOKEN")
OLLAMA_KEEP_ALIVE = os.environ.get("OLLAMA_KEEP_ALIVE", "8h" if RECEIVER_ENV == "work" else "5m")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DISABLE_TELEGRAM = os.environ.get("DISABLE_TELEGRAM", "").lower() in ("1", "true", "yes")

# Local TTS (Voicebox) Configuration
ENABLE_TTS = os.environ.get("ENABLE_TTS", "1").lower() in ("1", "true", "yes")
VOICEBOX_URL = os.environ.get("VOICEBOX_URL", "http://127.0.0.1:17493").rstrip("/")
VOICEBOX_PROFILE_NAME = os.environ.get("VOICEBOX_PROFILE_NAME", "Kokoro Heart")
VOICEBOX_PROFILE_ID = os.environ.get("VOICEBOX_PROFILE_ID", "")
VOICEBOX_ENGINE = os.environ.get("VOICEBOX_ENGINE", "kokoro")
VOICEBOX_MODEL_SIZE = os.environ.get("VOICEBOX_MODEL_SIZE", "1.7B")
SPEAK_ON_HOST = os.environ.get("SPEAK_ON_HOST", "1").lower() in ("1", "true", "yes")

# Look for credentials across standard cross-platform Hermes locations
hermes_env_candidates = [
    os.path.expanduser("~/.hermes/.env"),
    os.path.expanduser(r"~\AppData\Local\hermes\.env"),
    os.path.join(os.path.dirname(__file__), ".env")
]

_FILE_ENV: dict[str, str] = {}

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
                    _FILE_ENV.setdefault(k, v)
                    if k == "API_SERVER_KEY" and not API_SERVER_KEY:
                        API_SERVER_KEY = v
                    elif k == "VOICE_RECEIVER_TOKEN" and not VOICE_RECEIVER_TOKEN:
                        VOICE_RECEIVER_TOKEN = v
                    elif k == "OLLAMA_KEEP_ALIVE" and "OLLAMA_KEEP_ALIVE" not in os.environ:
                        OLLAMA_KEEP_ALIVE = v
                    elif k == "OLLAMA_MODEL" and "OLLAMA_MODEL" not in os.environ:
                        if v in OLLAMA_MODELS:
                            OLLAMA_MODELS.remove(v)
                        OLLAMA_MODELS.insert(0, v)
                    elif k == "TELEGRAM_BOT_TOKEN" and not TELEGRAM_BOT_TOKEN:
                        TELEGRAM_BOT_TOKEN = v
                    elif k == "TELEGRAM_ALLOWED_USERS" and not TELEGRAM_CHAT_ID and v:
                        TELEGRAM_CHAT_ID = v.split(",")[0].strip()
                    elif k == "TELEGRAM_HOME_CHANNEL" and not TELEGRAM_CHAT_ID and v:
                        TELEGRAM_CHAT_ID = v
                    elif k == "ENABLE_TTS":
                        ENABLE_TTS = v.lower() in ("1", "true", "yes")
                    elif k == "VOICEBOX_URL":
                        VOICEBOX_URL = v.rstrip("/")
                    elif k == "VOICEBOX_PROFILE_NAME":
                        VOICEBOX_PROFILE_NAME = v
                    elif k == "VOICEBOX_PROFILE_ID":
                        VOICEBOX_PROFILE_ID = v
                    elif k == "VOICEBOX_ENGINE":
                        VOICEBOX_ENGINE = v
                    elif k == "VOICEBOX_MODEL_SIZE":
                        VOICEBOX_MODEL_SIZE = v
                    elif k == "SPEAK_ON_HOST":
                        SPEAK_ON_HOST = v.strip().lower() in ("1", "true", "yes")
        except Exception as e:
            print(f"[Config] Note: Could not parse {env_path}: {e}")


def _env(key: str, default: str = "") -> str:
    """Process environment first, then the first .env file that defines the key."""
    return os.environ.get(key) or _FILE_ENV.get(key) or default


# Hybrid fast lane. 'off' keeps the legacy order (work: Ollama -> Hermes, home: Hermes -> Ollama),
# so sending transcripts to a cloud provider is always an explicit opt-in.
FAST_LLM_PROVIDER = _env("FAST_LLM_PROVIDER", "off").strip().lower()
if FAST_LLM_PROVIDER not in ("groq", "ollama", "off"):
    print(f"[Config] Unknown FAST_LLM_PROVIDER '{FAST_LLM_PROVIDER}', using 'off'")
    FAST_LLM_PROVIDER = "off"
GROQ_API_KEY = _env("GROQ_API_KEY")
GROQ_BASE_URL = _env("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
FAST_LLM_MODEL = _env("FAST_LLM_MODEL", "qwen/qwen3.8-27b")
FAST_LLM_MAX_TOKENS = int(_env("FAST_LLM_MAX_TOKENS", "120"))
FAST_LLM_TIMEOUT_S = float(_env("FAST_LLM_TIMEOUT_S", "8"))
OLLAMA_NUM_PREDICT = int(_env("OLLAMA_NUM_PREDICT", str(FAST_LLM_MAX_TOKENS)))
HERMES_AGENT_TIMEOUT_S = float(_env("HERMES_AGENT_TIMEOUT_S", "25"))
HERMES_REASONING_EFFORT = _env("HERMES_REASONING_EFFORT", "low").strip().lower()
HERMES_VOICE_PROVIDER = _env("HERMES_VOICE_PROVIDER").strip()
HERMES_VOICE_MODEL = _env("HERMES_VOICE_MODEL").strip()
STT_PROVIDER = _env("STT_PROVIDER", "local").strip().lower()
GROQ_STT_MODEL = _env("GROQ_STT_MODEL", "whisper-large-v3-turbo")

# Phase 18 & 19: Enforce strict Work privacy hardening
if RECEIVER_ENV.lower() == "work":
    DISABLE_TELEGRAM = True

print(f"[Config] Environment    : {RECEIVER_ENV.upper()}")
print(f"[Config] Receiver Port  : {PORT} (host: {HOST})")
print(f"[Config] Receiver Token : {'Enforced (Bearer auth enabled)' if VOICE_RECEIVER_TOKEN else 'None (Open access / unauthenticated)'}")
print(f"[Config] Hermes Gateway : {GATEWAY_URL}")
print(f"[Config] API Server Key : {'Configured (' + API_SERVER_KEY[:8] + '...)' if API_SERVER_KEY else 'MISSING (Set API_SERVER_KEY or ~/.hermes/.env)'}")
print(f"[Config] Ollama Host    : {OLLAMA_HOST} (keep_alive: {OLLAMA_KEEP_ALIVE}, num_predict: {OLLAMA_NUM_PREDICT})")
if FAST_LLM_PROVIDER == "off":
    print("[Config] Fast Lane      : Off (legacy backend order)")
else:
    fast_desc = f"groq/{FAST_LLM_MODEL}" + ("" if GROQ_API_KEY else " (GROQ_API_KEY MISSING -> Ollama)") \
        if FAST_LLM_PROVIDER == "groq" else "local Ollama"
    print(f"[Config] Fast Lane      : {fast_desc} | agent lane: Hermes (timeout {HERMES_AGENT_TIMEOUT_S:.0f}s, "
          f"reasoning {HERMES_REASONING_EFFORT or 'default'}"
          f"{', ' + HERMES_VOICE_PROVIDER + '/' + (HERMES_VOICE_MODEL or 'default') if HERMES_VOICE_PROVIDER else ''})")
print(f"[Config] Speech-to-Text : {'Groq ' + GROQ_STT_MODEL + ' (local fallback)' if STT_PROVIDER == 'groq' else 'local faster-whisper base'}")
tts_status_str = f"Enabled ({VOICEBOX_URL} | Engine: '{VOICEBOX_ENGINE or 'default'}' | Profile: '{VOICEBOX_PROFILE_NAME}')" if ENABLE_TTS else "Disabled"
print(f"[Config] Local TTS      : {tts_status_str}")
print(f"[Config] Telegram Mirror: {'Disabled (Work Mode / Privacy Hardened)' if RECEIVER_ENV.lower() == 'work' else ('Disabled' if DISABLE_TELEGRAM else ('Configured' if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID else 'Not configured'))}")

# System prompt tailored for ESP32 voice assistant: conversational, concise, but complete
ESP32_SYSTEM_PROMPT = (
    "You are an AI voice assistant communicating via an ESP32 speaker and compact display. "
    "Be direct, conversational, and complete. Keep responses concise (1 to 3 sentences, or a single standard 5-line limerick if asked for a poem or limerick). "
    "Never use conversational filler or preambles (do not say 'Here is a witty one for you:' or 'Certainly!'). Dive straight into the answer or limerick. "
    "Do not use markdown formatting, asterisks, bullet points, quotes, or emojis."
)

# ── 2. Synchronization & Global State ─────────────────────────────────
voice_lock = threading.Lock()

_last_tts_wav = None
_pending_tts_text = None
_tts_lock = threading.Lock()
_tts_ready = threading.Event()
_tts_ready.set()

last_voice_record = {
    "transcript": "",
    "reply": "",
    "backend": "none",
    "route": "none",
    "stt": "none",
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

# ── 3b. Local Voicebox Speech Synthesis (TTS) ──────────────────────────
_voicebox_online_cache = False
_voicebox_online_time = 0.0

def check_voicebox_online(force_probe: bool = False) -> bool:
    global _voicebox_online_cache, _voicebox_online_time
    if not ENABLE_TTS or not VOICEBOX_URL:
        return False
    now = time.time()
    # Negative cache is long: Voicebox is usually off, and a 0.5s probe on every
    # turn would sit in front of the SAPI fallback. Positive cache stays short.
    ttl = 3.0 if _voicebox_online_cache else 60.0
    if not force_probe and (now - _voicebox_online_time < ttl):
        return _voicebox_online_cache
    try:
        req = urllib.request.Request(f"{VOICEBOX_URL}/health", headers={"User-Agent": "HermesReceiver/1.0"})
        with urllib.request.urlopen(req, timeout=0.5) as resp:
            _voicebox_online_cache = (resp.getcode() == 200)
    except Exception:
        _voicebox_online_cache = False
    _voicebox_online_time = now
    return _voicebox_online_cache

def resolve_voicebox_profile_id() -> str:
    global VOICEBOX_PROFILE_ID
    if VOICEBOX_PROFILE_ID:
        return VOICEBOX_PROFILE_ID
    try:
        req = urllib.request.Request(f"{VOICEBOX_URL}/profiles", headers={"User-Agent": "HermesReceiver/1.0"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list):
                for p in data:
                    if p.get("name", "").strip().lower() == VOICEBOX_PROFILE_NAME.strip().lower():
                        VOICEBOX_PROFILE_ID = p.get("id")
                        print(f"[TTS] Resolved Voicebox profile '{VOICEBOX_PROFILE_NAME}' -> {VOICEBOX_PROFILE_ID}")
                        return VOICEBOX_PROFILE_ID
                if data:
                    VOICEBOX_PROFILE_ID = data[0].get("id")
                    print(f"[TTS] Defaulted to first Voicebox profile -> {VOICEBOX_PROFILE_ID}")
                    return VOICEBOX_PROFILE_ID
    except Exception as e:
        print(f"[TTS] Could not resolve Voicebox profile: {e}")
    return ""

def convert_24k_mono_to_16k_stereo_wav(raw_wav_bytes: bytes) -> bytes:
    """Converts 24kHz mono 16-bit PCM WAV to 16kHz stereo 16-bit PCM WAV for ESP32 I2S."""
    try:
        with wave.open(io.BytesIO(raw_wav_bytes), 'rb') as w_in:
            in_rate = w_in.getframerate()
            in_channels = w_in.getnchannels()
            in_frames = w_in.readframes(w_in.getnframes())

        samples = np.frombuffer(in_frames, dtype=np.int16)
        if in_channels == 2:
            samples = samples[::2]

        if HAS_SCIPY:
            if in_rate == 24000:
                resampled = scipy.signal.resample_poly(samples.astype(np.float32), 2, 3).astype(np.int16)
            elif in_rate != 16000:
                gcd = math.gcd(16000, in_rate)
                resampled = scipy.signal.resample_poly(samples.astype(np.float32), 16000 // gcd, in_rate // gcd).astype(np.int16)
            else:
                resampled = samples
        elif in_rate != 16000:
            # Fallback using numpy linear interpolation if scipy is not installed
            num_out = int(len(samples) * 16000 / in_rate)
            x_old = np.linspace(0, 1, len(samples), endpoint=False)
            x_new = np.linspace(0, 1, num_out, endpoint=False)
            resampled = np.interp(x_new, x_old, samples).astype(np.int16)
        else:
            resampled = samples

        # Duplicate into stereo (L and R channels)
        stereo_samples = np.column_stack((resampled, resampled)).flatten()

        out_buf = io.BytesIO()
        with wave.open(out_buf, 'wb') as w_out:
            w_out.setnchannels(2)
            w_out.setsampwidth(2)
            w_out.setframerate(16000)
            w_out.writeframes(stereo_samples.tobytes())

        return out_buf.getvalue()
    except Exception as e:
        print(f"[TTS] Resampling failed: {e}")
        return raw_wav_bytes

def sanitize_for_tts(text: str) -> str:
    """Prepare text for TTS pronunciation and ensure optimal generation length."""
    if not text:
        return ""
    # Strip dangerous punctuation for Qwen-TTS (colons & semicolons cause phonemizer loops)
    text = text.replace(":", ", ").replace(";", ", ")
    text = text.replace("ESP32", "ESP 32").replace("esp32", "ESP 32")
    # Clean up non-pronounceable markdown / technical symbols
    for ch in ['*', '#', '`', '[', ']', '(', ')', '{', '}', '<', '>', '|', '\\', '/', '"', '_', '~']:
        text = text.replace(ch, " ")
    # Normalize multiple whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Bound text to configurable max (default 260 chars, enough for a 5-line limerick or 2-3 sentences)
    max_chars = int(os.environ.get("TTS_MAX_CHARS", "260"))
    if len(text) > max_chars:
        best_cut = -1
        for sep in [". ", "! ", "? "]:
            pos = 0
            while True:
                idx = text.find(sep, pos)
                if idx == -1:
                    break
                cut_idx = idx + 1
                if 100 <= cut_idx <= max_chars:
                    if cut_idx > best_cut:
                        best_cut = cut_idx
                pos = idx + 1
        if best_cut != -1:
            text = text[:best_cut]
        else:
            parts = text[:max_chars].rsplit(" ", 1)
            text = (parts[0] if len(parts) > 1 else text[:max_chars]) + "."
    return text.strip()

def synthesize_speech_voicebox(text: str) -> bytes:
    """Generate audio via Voicebox and format for ESP32 playback."""
    if not ENABLE_TTS or not text:
        return b""
    profile_id = resolve_voicebox_profile_id()
    if not profile_id:
        return b""

    tts_text = sanitize_for_tts(text)
    if not tts_text:
        return b""

    t0 = time.perf_counter()
    try:
        payload = {
            "profile_id": profile_id,
            "text": tts_text
        }
        if VOICEBOX_ENGINE:
            payload["engine"] = VOICEBOX_ENGINE
        else:
            payload["model_size"] = VOICEBOX_MODEL_SIZE
        req_body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{VOICEBOX_URL}/generate/stream",
            data=req_body,
            headers={"Content-Type": "application/json", "User-Agent": "HermesReceiver/1.0"}
        )
        with urllib.request.urlopen(req, timeout=80) as resp:
            raw_wav = resp.read()

        t_gen = time.perf_counter() - t0
        print(f"[TTS] Voicebox generated {len(raw_wav)} bytes in {t_gen:.2f}s using '{VOICEBOX_PROFILE_NAME}'")

        return convert_24k_mono_to_16k_stereo_wav(raw_wav)
    except Exception as e:
        print(f"[TTS] Voicebox generation failed: {e}")
        return b""

def speak_on_host_speaker(text: str):
    """Asynchronously speaks text out loud on the host computer's speakers."""
    if not text:
        return
    def _run():
        try:
            if sys.platform == "win32":
                import pythoncom
                import win32com.client
                pythoncom.CoInitialize()
                try:
                    voice = win32com.client.Dispatch("SAPI.SpVoice")
                    voice.Speak(text)
                finally:
                    pythoncom.CoUninitialize()
        except Exception as e:
            print(f"[Host Speaker] Speech playback error: {e}")
    threading.Thread(target=_run, daemon=True).start()

def synthesize_speech_sapi(text: str) -> bytes:
    """Generates 16kHz stereo WAV using Windows SAPI (instant offline fallback)."""
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        tmp_wav = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_wav = f.name
            stream = win32com.client.Dispatch("SAPI.SpFileStream")
            stream.Format.Type = 22 # SAFT16kHz16BitStereo
            stream.Open(tmp_wav, 3) # SSFMCreateForWrite
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            voice.AudioOutputStream = stream
            voice.Speak(text)
            stream.Close()
            with open(tmp_wav, "rb") as f:
                raw_bytes = f.read()
            return convert_24k_mono_to_16k_stereo_wav(raw_bytes)
        finally:
            if tmp_wav and os.path.exists(tmp_wav):
                try:
                    os.remove(tmp_wav)
                except Exception:
                    pass
            pythoncom.CoUninitialize()
    except Exception as e:
        print(f"[TTS] Windows SAPI generation failed: {e}")
        return b""

def synthesize_speech(text: str) -> tuple[bytes, str]:
    """Generates 16kHz stereo WAV using Voicebox (primary) or Windows SAPI (instant fallback). Returns (wav_bytes, provider)."""
    if not ENABLE_TTS or not text:
        return (b"", "none")
    tts_text = sanitize_for_tts(text)
    if not tts_text:
        return (b"", "none")

    # 1. Try Voicebox if online and responsive
    if check_voicebox_online():
        try:
            wav = synthesize_speech_voicebox(tts_text)
            if wav:
                return (wav, "voicebox")
        except Exception as e:
            print(f"[TTS] Voicebox attempt note: {e}")

    # 2. Fast Windows SAPI fallback (instant ~100ms)
    if sys.platform == "win32":
        try:
            wav = synthesize_speech_sapi(tts_text)
            if wav:
                print(f"[TTS] Synthesized {len(wav)} bytes via Windows SAPI")
                return (wav, "windows-sapi")
        except Exception as e:
            print(f"[TTS] SAPI fallback note: {e}")

    return (b"", "none")


def queue_lazy_tts(text: str):
    """Start TTS in the background so the JSON reply can leave before audio is ready."""
    global _pending_tts_text, _last_tts_wav
    with _tts_lock:
        _pending_tts_text = text
        _last_tts_wav = None
        _tts_ready.clear()

    def _run():
        global _pending_tts_text, _last_tts_wav
        wav, provider = synthesize_speech(text)
        with _tts_lock:
            _last_tts_wav = wav if wav else None
            _pending_tts_text = None
        print(f"[TTS] Lazy generation via {provider}: {len(wav) if wav else 0} bytes")
        _tts_ready.set()

    threading.Thread(target=_run, daemon=True, name="lazy-tts").start()


def wait_for_tts_wav(timeout: float = 20.0) -> bytes:
    if not _tts_ready.wait(timeout):
        print("[TTS] Lazy generation timed out")
        return b""
    with _tts_lock:
        return _last_tts_wav or b""


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

def dispatch_telegram_mirror(transcript: str, reply: str, backend: str):
    """Phase 19: Asynchronously mirrors voice conversation to Telegram without blocking ESP32 response."""
    if DISABLE_TELEGRAM or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    def _async_send():
        t_start = time.perf_counter()
        ok1 = send_telegram_message(f"🎙️ *[ESP32 Voice Note]*\n🗣️ *You:* {transcript}")
        ok2 = send_telegram_message(f"🤖 *Hermes ({backend}):*\n{reply}")
        dur = time.perf_counter() - t_start
        print(f"[Telegram] Async mirror completed in {dur:.2f}s (user: {ok1}, reply: {ok2})")

    threading.Thread(target=_async_send, daemon=True).start()

# ── 6. Hermes Gateway Dispatcher (Primary Architectural Path) ──────────
# ── 6b. Persistent Sessions API (ESP32 Voice Satellite = one durable chat) ──
VOICE_SESSION_FILE = os.environ.get("VOICE_SESSION_FILE",
                                    os.path.expanduser("~/.hermes-voice/voice_session.json"))
VOICE_SESSION_TITLE = "ESP32 Voice Satellite"
HERMES_SESSIONS_BASE = HERMES_BASE_URL.rstrip("/") + "/api/sessions"


def _hermes_sessions_headers():
    return {"Authorization": f"Bearer {API_SERVER_KEY}",
            "Content-Type": "application/json"}


def load_voice_session() -> str:
    """Return the durable voice session ID, creating the session if needed."""
    p = pathlib.Path(VOICE_SESSION_FILE)
    if p.exists():
        try:
            sid = json.loads(p.read_text()).get("session_id", "")
            if sid:
                req = urllib.request.Request(f"{HERMES_SESSIONS_BASE}/{sid}",
                                             headers=_hermes_sessions_headers())
                with urllib.request.urlopen(req, timeout=8) as resp:
                    if resp.status == 200:
                        return sid
        except urllib.error.HTTPError as e:
            print(f"[Session] stored session unusable (HTTP {e.code}); creating new")
        except Exception as e:
            print(f"[Session] failed reading {p}: {e}")
    body = json.dumps({"title": VOICE_SESSION_TITLE}).encode("utf-8")
    req = urllib.request.Request(HERMES_SESSIONS_BASE, data=body,
                                 headers=_hermes_sessions_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            sid = json.loads(resp.read().decode("utf-8"))["session"]["id"]
    except urllib.error.HTTPError as e:
        # Title collision: the session already exists — find it by listing.
        if e.code == 400:
            req = urllib.request.Request(
                f"{HERMES_SESSIONS_BASE}?limit=1&title={urllib.parse.quote(VOICE_SESSION_TITLE)}",
                headers=_hermes_sessions_headers())
            with urllib.request.urlopen(req, timeout=10) as resp:
                rows = json.loads(resp.read().decode("utf-8")).get("data", [])
            if rows:
                sid = rows[0]["id"]
            else:
                raise
        else:
            raise
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"session_id": sid, "title": VOICE_SESSION_TITLE}))
    print(f"[Session] created persistent Hermes session {sid}")
    return sid


HERMES_TIMEOUT = int(os.environ.get("HERMES_TIMEOUT_S", "4" if RECEIVER_ENV == "work" else "25"))

_voice_session_id = ""
_voice_session_lock = threading.Lock()


def get_voice_session_id(refresh: bool = False) -> str:
    """Cached durable session ID, so each voice turn skips the session lookup round trip."""
    global _voice_session_id
    with _voice_session_lock:
        if refresh or not _voice_session_id:
            _voice_session_id = load_voice_session()
        return _voice_session_id


def _hermes_voice_overrides() -> dict:
    overrides = {}
    if HERMES_REASONING_EFFORT and HERMES_REASONING_EFFORT != "default":
        overrides["model_options"] = {"reasoning_effort": HERMES_REASONING_EFFORT}
    if HERMES_VOICE_PROVIDER:
        overrides["provider"] = HERMES_VOICE_PROVIDER
        if HERMES_VOICE_MODEL:
            overrides["model"] = HERMES_VOICE_MODEL
    return overrides


def ask_hermes_gateway(prompt: str, timeout: float | None = None) -> tuple[str, bool]:
    """Dispatches prompt to persistent Hermes Gateway via HTTP."""
    if not API_SERVER_KEY:
        return ("Error: API_SERVER_KEY not configured on host.", False)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_SERVER_KEY}"
    }

    payload = json.dumps({
        "input": prompt,
        "instructions": ESP32_SYSTEM_PROMPT,
        **_hermes_voice_overrides()
    }).encode("utf-8")

    for attempt in range(2):
        try:
            session_id = get_voice_session_id(refresh=attempt > 0)
        except Exception as e:
            return (f"Hermes session setup failed: {e}", False)
        url = f"{HERMES_SESSIONS_BASE}/{session_id}/chat"
        req = urllib.request.Request(url, data=payload, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout or HERMES_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                reply = (data.get("message") or {}).get("content", "").strip()
                # Detect provider billing/credit exhaustion errors returned by the agent
                lower_reply = reply.lower()
                if any(err_phrase in lower_reply for err_phrase in [
                    "billing or credits exhausted", "credits exhausted",
                    "requires a subscription or usage credits",
                    "rate limit exceeded", "account entitlement is exhausted",
                    "no available provider", "payment / credit error"
                ]):
                    print(f"[Hermes] Gateway reported provider credit/billing error: {reply[:100]}...")
                    return (reply, False)
                return (reply or "Command acknowledged.", True)
        except urllib.error.HTTPError as e:
            if e.code == 404 and attempt == 0:
                print("[Session] cached voice session vanished; re-resolving")
                continue
            err_body = e.read().decode("utf-8", errors="ignore")
            return (f"Hermes Gateway HTTP {e.code}: {err_body[:100]}", False)
        except (urllib.error.URLError, TimeoutError, Exception) as e:
            return (f"Hermes Gateway error: {str(e)}", False)
    return ("Hermes Gateway error: voice session unavailable", False)


# ── 6c. Hybrid Fast Lane (Groq direct) + Intent Router ─────────────────
# Shared by the Groq fast lane, the local Ollama path and agent replies, so a
# fallback mid-conversation still sees the previous turns.
_chat_history: list[tuple[str, str]] = []
_chat_history_lock = threading.Lock()
CHAT_HISTORY_TURNS = 4


def remember_turn(prompt: str, reply: str):
    global _chat_history
    with _chat_history_lock:
        _chat_history.append((prompt, reply))
        _chat_history = _chat_history[-10:]


def history_messages(system_prompt: str, prompt: str) -> list[dict]:
    messages = [{"role": "system", "content": system_prompt}]
    with _chat_history_lock:
        for user, assistant in _chat_history[-CHAT_HISTORY_TURNS:]:
            messages.append({"role": "user", "content": user})
            messages.append({"role": "assistant", "content": assistant})
    messages.append({"role": "user", "content": prompt})
    return messages


# Groq reasoning models must have thinking disabled/hidden or it consumes the token budget.
GROQ_MODEL_EXTRAS = {
    "openai/gpt-oss-20b": {"reasoning_effort": "low", "include_reasoning": False},
    "openai/gpt-oss-120b": {"reasoning_effort": "low", "include_reasoning": False},
    "qwen/qwen3-32b": {"reasoning_effort": "none", "reasoning_format": "hidden"},
}

_groq_url = urllib.parse.urlsplit(GROQ_BASE_URL)
_groq_conn: http.client.HTTPSConnection | None = None
_groq_conn_lock = threading.Lock()
fast_llm_state = {"ready": False, "error": None, "last_ms": None}


def _groq_request(method: str, endpoint: str, body: bytes | None, headers: dict, timeout: float) -> tuple[int, bytes]:
    """One request over a persistent TLS connection (reconnects once if Groq dropped it while idle)."""
    global _groq_conn
    path = _groq_url.path.rstrip("/") + endpoint
    with _groq_conn_lock:
        for attempt in range(2):
            if _groq_conn is None:
                _groq_conn = http.client.HTTPSConnection(_groq_url.hostname, _groq_url.port, timeout=timeout)
            _groq_conn.timeout = timeout
            if _groq_conn.sock is not None:
                _groq_conn.sock.settimeout(timeout)
            try:
                _groq_conn.request(method, path, body=body, headers=headers)
                resp = _groq_conn.getresponse()
                return resp.status, resp.read()
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, http.client.CannotSendRequest):
                _groq_conn.close()
                _groq_conn = None
                if attempt:
                    raise
            except Exception:
                _groq_conn.close()
                _groq_conn = None
                raise
    raise RuntimeError("unreachable")


def _groq_headers(content_type: str = "application/json") -> dict:
    return {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": content_type,
            "User-Agent": "HermesReceiver/1.0"}


def ask_fast_llm(prompt: str, extra_system: str = "") -> tuple[str, bool]:
    """Answers directly via Groq's OpenAI-compatible API (no agent, no tools)."""
    if not GROQ_API_KEY:
        return ("GROQ_API_KEY not configured", False)
    system_prompt = ESP32_SYSTEM_PROMPT + (f" {extra_system}" if extra_system else "")
    body = {
        "model": FAST_LLM_MODEL,
        "messages": history_messages(system_prompt, prompt),
        "temperature": 0.5,
        "max_completion_tokens": FAST_LLM_MAX_TOKENS,
        **GROQ_MODEL_EXTRAS.get(FAST_LLM_MODEL, {}),
    }
    t0 = time.perf_counter()
    try:
        status, raw = _groq_request("POST", "/chat/completions", json.dumps(body).encode("utf-8"),
                                    _groq_headers(), FAST_LLM_TIMEOUT_S)
    except Exception as e:
        fast_llm_state.update(ready=False, error=f"{type(e).__name__}: {e}")
        return (f"Groq error: {e}", False)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    if status != 200:
        detail = raw.decode("utf-8", errors="replace")[:160]
        fast_llm_state.update(ready=False, error=f"HTTP {status}: {detail}")
        return (f"Groq HTTP {status}: {detail}", False)
    try:
        reply = json.loads(raw)["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return (f"Groq response unparseable: {e}", False)
    if not reply:
        return ("Groq returned an empty reply", False)
    fast_llm_state.update(ready=True, error=None, last_ms=elapsed_ms)
    print(f"[Groq] {FAST_LLM_MODEL} responded in {elapsed_ms} ms: {reply[:60]}...")
    remember_turn(prompt, reply)
    return (reply, True)


def warmup_fast_llm():
    """Validates the Groq key and opens the TLS connection before the first voice turn."""
    if FAST_LLM_PROVIDER != "groq":
        return
    if not GROQ_API_KEY:
        fast_llm_state.update(ready=False, error="GROQ_API_KEY not configured")
        print("[Groq] GROQ_API_KEY missing; fast lane will use local Ollama")
        return
    try:
        # Probe /models (not /models/{id}): slashes in names like qwen/qwen3.8-27b 404 if encoded.
        status, raw = _groq_request("GET", "/models", None, _groq_headers(), 5.0)
        if status == 200:
            ids = {m.get("id") for m in (json.loads(raw).get("data") or [])}
            if FAST_LLM_MODEL in ids:
                fast_llm_state.update(ready=True, error=None)
                print(f"[Groq] Fast lane ready ({FAST_LLM_MODEL})")
            else:
                fast_llm_state.update(ready=False, error=f"model '{FAST_LLM_MODEL}' not in Groq catalog")
                print(f"[Groq] Fast lane check failed: {fast_llm_state['error']}")
        else:
            fast_llm_state.update(ready=False, error=f"HTTP {status}: {raw.decode('utf-8', 'replace')[:120]}")
            print(f"[Groq] Fast lane check failed: {fast_llm_state['error']}")
    except Exception as e:
        fast_llm_state.update(ready=False, error=str(e))
        print(f"[Groq] Fast lane check failed: {e}")


def transcribe_with_groq(wav_path: str) -> str:
    """Groq Whisper STT over the same persistent TLS connection as the fast lane."""
    if not GROQ_API_KEY:
        return ""
    boundary = uuid.uuid4().hex
    buf = io.BytesIO()
    for name, value in (("model", GROQ_STT_MODEL), ("language", "en"), ("response_format", "json")):
        buf.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    wav_name = os.path.basename(wav_path)
    buf.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{wav_name}\"\r\n"
              f"Content-Type: audio/wav\r\n\r\n".encode())
    with open(wav_path, "rb") as f:
        buf.write(f.read())
    buf.write(f"\r\n--{boundary}--\r\n".encode())
    status, raw = _groq_request(
        "POST", "/audio/transcriptions", buf.getvalue(),
        _groq_headers(f"multipart/form-data; boundary={boundary}"), 20.0)
    if status != 200:
        raise RuntimeError(f"HTTP {status}: {raw.decode('utf-8', 'replace')[:160]}")
    return (json.loads(raw).get("text") or "").strip()


def transcribe_local(wav_path: str) -> str:
    model = get_whisper_model()
    if not model:
        return ""
    segments, _info = model.transcribe(wav_path, beam_size=1, vad_filter=True, language="en")
    return " ".join(seg.text for seg in segments).strip()


def transcribe_audio(wav_path: str) -> tuple[str, str]:
    """Returns (transcript, stt_provider). Groq first when enabled, then local Whisper."""
    if STT_PROVIDER == "groq" and GROQ_API_KEY:
        try:
            text = transcribe_with_groq(wav_path)
            if text:
                return text, "groq-whisper"
        except Exception as e:
            print(f"[STT] Groq failed ({e}); falling back to local Whisper")
    text = transcribe_local(wav_path)
    return text, ("faster-whisper" if text else "none")


# Requests that need live data, tools or device actions go to the Hermes agent. The
# list errs towards the agent: a false positive costs seconds, a false negative
# gets a confidently made-up forecast or a lamp that never turns on.
AGENT_INTENT_RE = re.compile(
    r"\b("
    r"weather|forecast|news|headlines?|today|tonight|tomorrow|"
    r"what(?:'s| is) the (?:date|time)|what day is it|what time is it|"
    r"search|look (?:it |that )?up|google|browse|website|"
    r"remind(?:er)?s?|schedule|calendar|appointments?|meetings?|timers?|alarms?|"
    r"e-?mails?|inbox|send (?:a |an )?(?:message|text|email)|"
    r"turn (?:on|off)|switch (?:on|off)|lights?|lamps?|thermostat|home assistant|"
    r"onenote|my (?:files?|notes?|documents?)|"
    r"ask hermes|use hermes|hermes agent"
    r")\b",
    re.IGNORECASE,
)


def route_intent(transcript: str) -> str:
    """Returns 'agent' for tool/action/live-data requests, otherwise 'fast'."""
    return "agent" if AGENT_INTENT_RE.search(transcript or "") else "fast"


def answer_fast_lane(transcript: str) -> tuple[str, bool, str]:
    """Fast lane: Groq (if enabled), then warm local Ollama, then the Hermes agent."""
    if FAST_LLM_PROVIDER == "groq":
        reply, ok = ask_fast_llm(transcript)
        if ok:
            return (reply, True, "groq-fast")
        print(f"[WARN] Fast lane Groq failed ({reply}); trying local Ollama")
    reply, ok = query_ollama_fallback(transcript)
    if ok:
        return (reply, True, "ollama-local" if FAST_LLM_PROVIDER == "ollama" else "ollama-fallback")
    reply, ok = ask_hermes_gateway(transcript, timeout=HERMES_AGENT_TIMEOUT_S)
    if ok:
        remember_turn(transcript, reply)
        return (reply, True, "hermes-agent-fallback")
    return (reply, False, "none")


def answer_agent_lane(transcript: str) -> tuple[str, bool, str]:
    """Agent lane: Hermes with tools; if it fails, a fast model answers and says tools are offline."""
    reply, ok = ask_hermes_gateway(transcript, timeout=HERMES_AGENT_TIMEOUT_S)
    if ok:
        remember_turn(transcript, reply)
        return (reply, True, "hermes-agent")
    print(f"[WARN] Hermes agent unavailable ({reply}); answering without tools")
    tools_down = ("Your tools, live data and device controls are unavailable right now. If the request "
                  "needs them, say so briefly instead of guessing.")
    if FAST_LLM_PROVIDER == "groq":
        fast_reply, fast_ok = ask_fast_llm(transcript, extra_system=tools_down)
        if fast_ok:
            return (fast_reply, True, "groq-no-tools")
    fast_reply, fast_ok = query_ollama_fallback(transcript, extra_system=tools_down)
    if fast_ok:
        return (fast_reply, True, "ollama-no-tools")
    return (reply, False, "none")

# ── 7. Local Ollama Fallback (Transparent Diagnostic Fallback) ─────────
OLLAMA_THINKING_PREFIXES = ("qwen3", "deepseek-r1", "gpt-oss")


def query_ollama_fallback(prompt: str, extra_system: str = "") -> tuple[str, bool]:
    """Queries local Ollama directly (work-mode primary, fast-lane and agent fallback)."""
    models_to_try = list(OLLAMA_MODELS)
    try:
        ps_resp = urllib.request.urlopen(f"{OLLAMA_HOST.rstrip('/')}/api/ps", timeout=1.0)
        if ps_resp.status == 200:
            ps_data = json.loads(ps_resp.read().decode("utf-8"))
            for m in reversed(ps_data.get("models", [])):
                m_name = m.get("name")
                if m_name:
                    if m_name in models_to_try:
                        models_to_try.remove(m_name)
                    models_to_try.insert(0, m_name)
    except Exception:
        pass

    system_prompt = ESP32_SYSTEM_PROMPT + (f" {extra_system}" if extra_system else "")
    messages = history_messages(system_prompt, prompt)

    for model in models_to_try:
        try:
            print(f"[Ollama] Querying model '{model}'...")
            t_start = time.perf_counter()
            body = {
                "model": model,
                "messages": messages,
                "stream": False,
                "keep_alive": OLLAMA_KEEP_ALIVE,
                "options": {
                    "num_ctx": 2048,
                    "num_predict": OLLAMA_NUM_PREDICT,
                    "temperature": 0.5
                }
            }
            if model.startswith(OLLAMA_THINKING_PREFIXES):
                body["think"] = False
            url = f"{OLLAMA_HOST.rstrip('/')}/api/chat"
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                reply = ((data.get("message") or {}).get("content") or "").strip()
                t_dur = time.perf_counter() - t_start
                if reply:
                    print(f"[Ollama] Model '{model}' responded in {t_dur:.2f}s: {reply[:60]}...")
                    remember_turn(prompt, reply)
                    return (reply, True)
        except Exception as e:
            print(f"[Ollama] Model '{model}' query error: {e}")
            if isinstance(e, (TimeoutError, urllib.error.URLError)) and "timed out" in str(e).lower():
                print(f"[Ollama] Skipping cold model cascade due to timeout.")
                break
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
        # Check if model is already loaded with oversized context length (>2048)
        ps_url = f"{OLLAMA_HOST.rstrip('/')}/api/ps"
        try:
            with urllib.request.urlopen(ps_url, timeout=1.5) as ps_resp:
                if ps_resp.status == 200:
                    ps_data = json.loads(ps_resp.read().decode("utf-8"))
                    for m in ps_data.get("models", []):
                        if m.get("name") == model and m.get("context_length", 0) > 2048:
                            print(f"[Ollama] Unloading oversized model instance (ctx={m.get('context_length')})...")
                            unload_req = urllib.request.Request(
                                f"{OLLAMA_HOST.rstrip('/')}/api/generate",
                                data=json.dumps({"model": model, "keep_alive": 0}).encode("utf-8"),
                                headers={"Content-Type": "application/json"}
                            )
                            urllib.request.urlopen(unload_req, timeout=5)
                            break
        except Exception:
            pass

        req_data = json.dumps({
            "model": model,
            "prompt": "Hello",
            "stream": False,
            "keep_alive": OLLAMA_KEEP_ALIVE,
            "options": {"num_ctx": 2048, "num_predict": 5}
        }).encode("utf-8")
        url = f"{OLLAMA_HOST.rstrip('/')}/api/generate"
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"[Ollama] Preloading model '{model}' (keep_alive: {OLLAMA_KEEP_ALIVE})...")
        with urllib.request.urlopen(req, timeout=30) as resp:
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

    tts_online = check_voicebox_online()
    if FAST_LLM_PROVIDER == "groq":
        fast_ready = bool(GROQ_API_KEY) and bool(fast_llm_state.get("ready") or not fast_llm_state.get("error"))
        fast_error = None if GROQ_API_KEY else "GROQ_API_KEY not configured"
        if GROQ_API_KEY:
            fast_error = fast_llm_state.get("error")
    elif FAST_LLM_PROVIDER == "ollama":
        fast_ready = bool(ollama_info.get("warm") or ollama_info.get("ready"))
        fast_error = ollama_info.get("error")
    else:
        fast_ready = False
        fast_error = None

    status_data = {
        "status": overall_status,
        "environment": RECEIVER_ENV,
        "receiver": {
            "ready": True,
            "whisper": whisper_model is not None,
            "voice_in_progress": voice_lock.locked(),
            "port": PORT
        },
        "tts": {
            "enabled": ENABLE_TTS,
            "provider": "voicebox",
            "ready": tts_online,
            "profile": VOICEBOX_PROFILE_NAME
        },
        "stt": {
            "provider": STT_PROVIDER,
            "model": GROQ_STT_MODEL if STT_PROVIDER == "groq" else "faster-whisper-base",
            "ready": bool(GROQ_API_KEY) if STT_PROVIDER == "groq" else whisper_model is not None
        },
        "fast_llm": {
            "provider": FAST_LLM_PROVIDER,
            "model": FAST_LLM_MODEL if FAST_LLM_PROVIDER != "off" else None,
            "ready": fast_ready,
            "error": fast_error,
            "last_ms": fast_llm_state.get("last_ms")
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

        # 3. Audio Stream Endpoint for ESP32 Speaker Playback
        if path == "/voice/audio":
            if not self.check_auth():
                self.send_unauthorized()
                return
            audio_bytes = wait_for_tts_wav()
            if not audio_bytes:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "not_found", "message": "No audio available"}).encode("utf-8"))
                return
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(audio_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(audio_bytes)
            return

        # 4. Root index / summary
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
                "GET /voice/audio",
                "POST /voice"
            ],
            "whisper_loaded": whisper_model is not None,
            "voice_busy": voice_lock.locked()
        }
        self.wfile.write(json.dumps(resp, indent=2).encode("utf-8"))

    def do_POST(self):
        t_req_start = time.perf_counter()
        global _last_tts_wav
        url_parts = urllib.parse.urlparse(self.path)
        req_path = url_parts.path.rstrip('/')

        if req_path not in ["/voice", ""]:
            self.send_response(404)
            self.end_headers()
            return

        # Check if client requested audio output or text-only mode
        audio_requested = True
        if self.headers.get("X-Audio-Output", "1").strip().lower() in ("0", "false", "no"):
            audio_requested = False
        parsed_query = urllib.parse.parse_qs(url_parts.query)
        if parsed_query.get("audio", ["1"])[0].lower() in ("0", "false", "no") or \
           parsed_query.get("tts", ["1"])[0].lower() in ("0", "false", "no"):
            audio_requested = False

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

            # 3. Transcribe (Groq Whisper when STT_PROVIDER=groq, else local faster-whisper)
            t_whisper_start = time.perf_counter()
            transcript, stt_used = transcribe_audio(tmp_wav_path)
            t_whisper_end = time.perf_counter()
            whisper_s = t_whisper_end - t_whisper_start

            if not transcript:
                transcript = "(unrecognized speech)"

            # 4. Query LLM Backend (hybrid router when the fast lane is enabled, otherwise
            #    legacy order: Work = local Ollama primary, Home = Hermes Gateway primary)
            t_hermes_start = time.perf_counter()
            route = "legacy"
            if FAST_LLM_PROVIDER != "off":
                route = route_intent(transcript)
                if route == "agent":
                    reply, _, backend_used = answer_agent_lane(transcript)
                else:
                    reply, _, backend_used = answer_fast_lane(transcript)
            elif RECEIVER_ENV.lower() == "work":
                ollama_reply, ollama_ok = query_ollama_fallback(transcript)
                if ollama_ok:
                    reply = ollama_reply
                    backend_used = "ollama-local"
                else:
                    reply, hermes_ok = ask_hermes_gateway(transcript)
                    backend_used = "hermes-gateway" if hermes_ok else "none"
            else:
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

            # 5. Sanitize reply for embedded TFT display
            clean_reply = sanitize_for_display(reply)

            # 6. Generate Local Voice audio and optionally speak out loud on host
            tts_s = 0.0
            audio_available = False
            tts_provider = "none"
            llm_succeeded = backend_used not in ("none", "")

            # Speak out loud on host computer speaker if enabled
            if SPEAK_ON_HOST and llm_succeeded:
                speak_on_host_speaker(clean_reply)

            if audio_requested and ENABLE_TTS and llm_succeeded:
                # Generate audio after the JSON leaves so the TFT can show text first.
                # GET /voice/audio waits on the same Event (ESP32 already delays 300ms).
                queue_lazy_tts(clean_reply)
                audio_available = True
                tts_provider = "lazy"
            else:
                if not audio_requested:
                    print(f"[TTS] Audio output disabled by client (Text-only mode) -> skipping TTS")
                with _tts_lock:
                    _last_tts_wav = None
                    _tts_ready.set()

            t_server_end = time.perf_counter()
            server_total_s = t_server_end - t_req_start

            timing_dict = {
                "body_read_ms": int(body_read_s * 1000),
                "wav_write_ms": int(wav_write_s * 1000),
                "whisper_ms": int(whisper_s * 1000),
                "hermes_ms": int(hermes_s * 1000),
                "tts_ms": int(tts_s * 1000),
                "server_ms": int(server_total_s * 1000)
            }

            with last_voice_lock:
                last_voice_record["transcript"] = transcript
                last_voice_record["reply"] = clean_reply[:800]
                last_voice_record["backend"] = backend_used
                last_voice_record["route"] = route
                last_voice_record["stt"] = stt_used
                last_voice_record["success"] = True
                last_voice_record["timestamp"] = time.time()
                last_voice_record["timing"] = timing_dict

            response_payload = {
                "status": "ok",
                "transcript": transcript,
                "reply": clean_reply[:800],
                "backend": backend_used,
                "route": route,
                "stt": stt_used,
                "audio_available": audio_available,
                "audio_url": "/voice/audio" if audio_available else "",
                "timing": timing_dict,
                "server_ms": int(server_total_s * 1000),
                "whisper_ms": int(whisper_s * 1000),
                "hermes_ms": int(hermes_s * 1000),
                "tts_ms": int(tts_s * 1000)
            }

            # 7. Return JSON response to ESP32 IMMEDIATELY (flush socket)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response_payload).encode("utf-8"))
            try:
                self.wfile.flush()
            except Exception:
                pass

            # 8. Asynchronously mirror to Telegram (Phase 19: never blocks ESP32 or affects server_ms)
            dispatch_telegram_mirror(transcript, reply, backend_used)

            # Structured console performance logging
            print("\n========== VOICE REQUEST ==========")
            print(f"WAV received  : {content_length} bytes from {self.client_address[0]}")
            print(f"Backend used  : {backend_used} (route: {route}, stt: {stt_used})")
            print(f"TTS audio     : {'Queued (lazy 16kHz stereo WAV)' if audio_available else 'None / Offline'}")
            print(f"[PERF] body_read   : {body_read_s:6.2f} s")
            print(f"[PERF] wav_write   : {wav_write_s:6.2f} s")
            print(f"[PERF] whisper     : {whisper_s:6.2f} s")
            print(f"[PERF] hermes/llm  : {hermes_s:6.2f} s")
            print(f"[PERF] voicebox/tts: {tts_s:6.2f} s")
            print("-----------------------------------")
            print(f"[PERF] SERVER TOTAL: {server_total_s:6.2f} s")
            print(f"[STT ] {transcript}")
            print(f"[AI  ] {clean_reply}")
            print("===================================\n")

        except Exception as e:
            t_err_end = time.perf_counter()
            print(f"[Error] Processing failed: {e}")

            with last_voice_lock:
                last_voice_record["success"] = False
                last_voice_record["reply"] = str(e)[:100]
                last_voice_record["timestamp"] = time.time()

            try:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "error",
                    "message": str(e),
                    "server_ms": int((t_err_end - t_req_start) * 1000)
                }).encode("utf-8"))
            except Exception:
                pass

        finally:
            if tmp_wav_path and os.path.exists(tmp_wav_path):
                try:
                    os.remove(tmp_wav_path)
                except Exception:
                    pass
            voice_lock.release()

def get_local_ip_for_target(target_ip="8.8.8.8"):
    """Returns the primary outbound IP address of this machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((target_ip, 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

def run_discovery_beacon():
    """Broadcasts discovery packets and answers queries from ESP32."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("", DISCOVERY_UDP_PORT))
    except Exception as e:
        print(f"[Discovery] Warning: could not bind UDP port {DISCOVERY_UDP_PORT}: {e}")
        return

    sock.settimeout(1.0)
    last_broadcast = 0.0

    print(f"[Discovery] UDP Beacon listening & broadcasting on port {DISCOVERY_UDP_PORT}")

    while True:
        now = time.time()
        # Broadcast periodic beacon every 3 seconds
        if now - last_broadcast >= 3.0:
            last_broadcast = now
            local_ip = get_local_ip_for_target()
            payload = json.dumps({
                "service": "hermes-receiver",
                "port": PORT,
                "hostname": socket.gethostname(),
                "env": RECEIVER_ENV,
                "ip": local_ip,
                "version": 1
            }).encode("utf-8")
            try:
                sock.sendto(payload, ("255.255.255.255", DISCOVERY_UDP_PORT))
            except Exception:
                pass

        # Check for inbound queries from ESP32
        try:
            data, addr = sock.recvfrom(1024)
            if data:
                try:
                    msg = json.loads(data.decode("utf-8"))
                    if msg.get("query") == "hermes-receiver":
                        local_ip = get_local_ip_for_target(addr[0])
                        reply = json.dumps({
                            "service": "hermes-receiver",
                            "port": PORT,
                            "hostname": socket.gethostname(),
                            "env": RECEIVER_ENV,
                            "ip": local_ip,
                            "version": 1
                        }).encode("utf-8")
                        sock.sendto(reply, addr)
                except Exception:
                    pass
        except socket.timeout:
            pass
        except Exception:
            time.sleep(0.5)

def main():
    # Warm up Whisper model in background
    get_whisper_model()

    # Phase 17: Pre-warm Ollama model in background thread to prevent cold start latency
    threading.Thread(target=warmup_ollama_model, daemon=True).start()
    threading.Thread(target=warmup_fast_llm, daemon=True).start()

    # Launch UDP discovery beacon & query responder
    threading.Thread(target=run_discovery_beacon, daemon=True).start()

    server = ThreadingHTTPServer((HOST, PORT), VoiceRequestHandler)
    server.daemon_threads = True

    print(f"\n=======================================================")
    print(f"  Hermes Voice Satellite Receiver Running on port {PORT}")
    print(f"  Architecture : ThreadingHTTPServer (Concurrent Health)")
    print(f"  Endpoints    : GET /health | GET /status | POST /voice")
    print(f"  Gateway URL  : {GATEWAY_URL}")
    print(f"  Ollama URL   : {OLLAMA_HOST}")
    print(f"=======================================================")
    if FAST_LLM_PROVIDER == "off":
        print(f"  Primary LLM  : Persistent Hermes Gateway (:8642)")
        print(f"  Fallback LLM : Local Ollama (:11434)")
    else:
        print(f"  Fast lane    : {FAST_LLM_PROVIDER}/{FAST_LLM_MODEL if FAST_LLM_PROVIDER == 'groq' else (OLLAMA_MODELS[0] if OLLAMA_MODELS else 'ollama')}")
        print(f"  Agent lane   : Hermes Gateway (:8642) timeout {HERMES_AGENT_TIMEOUT_S:.0f}s")
    print(f"=======================================================\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down receiver...")
        server.server_close()

if __name__ == "__main__":
    main()
