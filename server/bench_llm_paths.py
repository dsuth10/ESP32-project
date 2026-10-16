"""
Hermes Voice Satellite - LLM path latency and accuracy benchmark.

Times every route the page-6 voice flow can use to reach an LLM and scores each
reply with deterministic rule checks from bench_prompts.json.

Paths:
  ollama-local          Local Ollama /api/chat (streaming) per installed small model
  ollama-cloud-direct   Ollama Cloud model through local Ollama, bypassing the agent
  hermes-session        Hermes gateway /api/sessions/{id}/chat (the receiver's agent path)
  hermes-session-low    Same, with per-request reasoning_effort=low
  hermes-session+groq   Same, routed to the 'groq-voice' Hermes provider
  hermes-openai         Hermes gateway /v1/chat/completions (stateless, streaming)
  hermes-cli            hermes -z one-shot subprocess (2 calls only)
  groq-direct           Groq OpenAI-compatible API (streaming) per candidate model

Usage:
  python server/bench_llm_paths.py --list
  python server/bench_llm_paths.py
  python server/bench_llm_paths.py --only groq-direct,ollama-local --runs 3
  python server/bench_llm_paths.py --stt --e2e
"""

import argparse
import csv
import datetime
import http.client
import io
import json
import os
import pathlib
import re
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field, asdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")

SERVER_DIR = pathlib.Path(__file__).resolve().parent
HERMES_HOME = pathlib.Path(os.environ.get("HERMES_HOME", os.path.expanduser(r"~\AppData\Local\hermes")))
ENV_FILES = [
    pathlib.Path(os.path.expanduser("~/.hermes/.env")),
    HERMES_HOME / ".env",
    SERVER_DIR / ".env",
]


def _load_env_files() -> dict:
    values = {}
    for path in ENV_FILES:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            values.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return values


_FILE_ENV = _load_env_files()


def cfg(key: str, default: str = "") -> str:
    return os.environ.get(key) or _FILE_ENV.get(key) or default


OLLAMA_HOST = cfg("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
HERMES_BASE_URL = cfg("HERMES_BASE_URL", "http://127.0.0.1:8642").rstrip("/")
RECEIVER_URL = cfg("BENCH_RECEIVER_URL", "http://127.0.0.1:8787").rstrip("/")
GROQ_BASE_URL = cfg("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
API_SERVER_KEY = cfg("API_SERVER_KEY")
VOICE_RECEIVER_TOKEN = cfg("VOICE_RECEIVER_TOKEN")
GROQ_API_KEY = cfg("GROQ_API_KEY")
HERMES_GROQ_PROVIDER = cfg("HERMES_GROQ_PROVIDER", "custom:groq-voice")
HERMES_GROQ_MODEL = cfg("HERMES_GROQ_MODEL", "openai/gpt-oss-20b")

HERMES_CLI_CANDIDATES = [
    HERMES_HOME / "hermes-agent" / "venv" / "Scripts" / "hermes.exe",
    HERMES_HOME / "bin" / "hermes.exe",
    HERMES_HOME / "bin" / "hermes.cmd",
]

# Kept identical to ESP32_SYSTEM_PROMPT in hermes_voice_receiver.py so every path is judged on the same brief.
SYSTEM_PROMPT = (
    "You are an AI voice assistant communicating via an ESP32 speaker and compact display. "
    "Be direct, conversational, and complete. Keep responses concise (1 to 3 sentences, or a single standard 5-line limerick if asked for a poem or limerick). "
    "Never use conversational filler or preambles (do not say 'Here is a witty one for you:' or 'Certainly!'). Dive straight into the answer or limerick. "
    "Do not use markdown formatting, asterisks, bullet points, quotes, or emojis."
)

TEMPERATURE = 0.5
MAX_TOKENS = 120
HISTORY_TURNS = 4
ACCURACY_THRESHOLD = 0.8
DEFAULT_OLLAMA_MODELS = ["gemma3:latest", "qwen3.5:latest", "gemma3:12b", "phi4:14b"]
OLLAMA_CLOUD_MODEL = "gemma4:31b-cloud"
OLLAMA_THINKING_PREFIXES = ("qwen3", "deepseek-r1", "gpt-oss")
BENCH_KEEP_ALIVE = "2m"

# Per-model request extras. Groq reasoning models need their thinking disabled or
# hidden, otherwise the reasoning tokens eat the completion budget.
GROQ_MODELS = {
    "qwen/qwen3.8-27b": {},
    "openai/gpt-oss-20b": {"reasoning_effort": "low", "include_reasoning": False, "_max_tokens": 400},
    "openai/gpt-oss-120b": {"reasoning_effort": "low", "include_reasoning": False, "_max_tokens": 400},
}
GROQ_STT_MODEL = "whisper-large-v3-turbo"

BILLING_PHRASES = [
    "billing or credits exhausted", "credits exhausted", "requires a subscription or usage credits",
    "rate limit exceeded", "account entitlement is exhausted", "no available provider", "payment / credit error",
]

AGENT_PATHS = {"hermes-session", "hermes-session-low", "hermes-session+groq", "hermes-openai", "hermes-cli"}
ALL_PATHS = ["ollama-local", "ollama-cloud-direct", "hermes-session", "hermes-session-low",
             "hermes-session+groq", "hermes-openai", "hermes-cli", "groq-direct"]


# ── Data types ─────────────────────────────────────────────────────────
@dataclass
class Reply:
    text: str
    ttft_s: float | None = None
    out_tokens: int | None = None


@dataclass
class Result:
    path: str
    model: str
    prompt_id: str
    category: str
    round: int
    cold: bool
    ok: bool
    total_s: float
    ttft_s: float | None
    out_tokens: int | None
    text: str
    error: str
    score: float
    checks: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        return f"{self.path}:{self.model}"


def build_messages(prompt: str, history: list[tuple[str, str]]) -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for user, assistant in history[-HISTORY_TURNS:]:
        messages.append({"role": "user", "content": user})
        messages.append({"role": "assistant", "content": assistant})
    messages.append({"role": "user", "content": prompt})
    return messages


def http_json(url: str, *, method: str = "GET", body: dict | None = None, headers: dict | None = None,
              timeout: float = 10.0) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw) if raw.strip() else {}


def http_error_text(e: urllib.error.HTTPError) -> str:
    try:
        body = e.read().decode("utf-8", errors="replace")
    except Exception:
        body = ""
    return f"HTTP {e.code}: {body[:200]}"


# ── Adapters ───────────────────────────────────────────────────────────
class Adapter:
    path = ""
    uses_own_history = False
    max_calls: int | None = None

    def __init__(self, model: str):
        self.model = model

    def unavailable_reason(self) -> str | None:
        return None

    def setup(self):
        pass

    def ask(self, prompt: str, history: list[tuple[str, str]]) -> Reply:
        raise NotImplementedError

    def teardown(self):
        pass


class OllamaAdapter(Adapter):
    def __init__(self, path: str, model: str, installed: set[str] | None):
        super().__init__(model)
        self.path = path
        self._installed = installed

    def unavailable_reason(self):
        if self._installed is None:
            return f"Ollama not reachable at {OLLAMA_HOST}"
        if not self.model.endswith("-cloud") and self.model not in self._installed:
            return f"model '{self.model}' not installed"
        return None

    def ask(self, prompt, history):
        body = {
            "model": self.model,
            "messages": build_messages(prompt, history),
            "stream": True,
            "keep_alive": BENCH_KEEP_ALIVE,
            "options": {"num_ctx": 2048, "num_predict": MAX_TOKENS, "temperature": TEMPERATURE},
        }
        if self.model.startswith(OLLAMA_THINKING_PREFIXES):
            body["think"] = False
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/chat", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        t0 = time.perf_counter()
        parts, ttft, tokens = [], None, None
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                for raw in resp:
                    if not raw.strip():
                        continue
                    chunk = json.loads(raw)
                    if chunk.get("error"):
                        raise RuntimeError(chunk["error"])
                    piece = (chunk.get("message") or {}).get("content") or ""
                    if piece:
                        if ttft is None:
                            ttft = time.perf_counter() - t0
                        parts.append(piece)
                    if chunk.get("done"):
                        tokens = chunk.get("eval_count")
        except urllib.error.HTTPError as e:
            raise RuntimeError(http_error_text(e)) from None
        return Reply("".join(parts).strip(), ttft, tokens)


def read_openai_sse(resp: http.client.HTTPResponse, t0: float) -> Reply:
    parts, ttft, tokens = [], None, None
    while True:
        raw = resp.readline()
        if not raw:
            break
        line = raw.decode("utf-8", errors="replace").strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        chunk = json.loads(data)
        if chunk.get("error"):
            raise RuntimeError(str(chunk["error"])[:200])
        for choice in chunk.get("choices") or []:
            piece = (choice.get("delta") or {}).get("content") or ""
            if piece:
                if ttft is None:
                    ttft = time.perf_counter() - t0
                parts.append(piece)
        usage = chunk.get("usage") or (chunk.get("x_groq") or {}).get("usage")
        if usage:
            tokens = usage.get("completion_tokens", tokens)
    resp.read()  # drain so the keep-alive connection can be reused
    return Reply("".join(parts).strip(), ttft, tokens)


class OpenAIStreamAdapter(Adapter):
    """Streaming /chat/completions client over one persistent HTTP(S) connection."""

    def __init__(self, path: str, model: str, base_url: str, api_key: str, *, request_model: str | None = None,
                 sampling: bool = True, timeout: float = 60.0, missing_reason: str | None = None):
        super().__init__(model)
        self.path = path
        extra = dict(GROQ_MODELS.get(model, {})) if sampling else {}
        self._max_tokens = extra.pop("_max_tokens", MAX_TOKENS)
        self._extra = extra
        self._request_model = request_model or model
        self._api_key = api_key
        self._sampling = sampling
        self._timeout = timeout
        self._missing_reason = missing_reason
        parts = urllib.parse.urlsplit(base_url)
        self._https = parts.scheme == "https"
        self._host, self._port = parts.hostname, parts.port
        self._endpoint = parts.path.rstrip("/") + "/chat/completions"
        self._conn = None

    def unavailable_reason(self):
        return self._missing_reason

    def _connection(self):
        if self._conn is None:
            cls = http.client.HTTPSConnection if self._https else http.client.HTTPConnection
            self._conn = cls(self._host, self._port, timeout=self._timeout)
        return self._conn

    def _reset(self):
        if self._conn is not None:
            self._conn.close()
        self._conn = None

    def _send(self, payload: bytes) -> http.client.HTTPResponse:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self._api_key}",
                   "Accept": "text/event-stream"}
        for attempt in range(2):
            try:
                conn = self._connection()
                conn.request("POST", self._endpoint, body=payload, headers=headers)
                return conn.getresponse()
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, http.client.CannotSendRequest):
                self._reset()
                if attempt:
                    raise
        raise RuntimeError("unreachable")

    def ask(self, prompt, history):
        body = {"model": self._request_model, "messages": build_messages(prompt, history), "stream": True}
        if self._sampling:
            body.update(temperature=TEMPERATURE, max_completion_tokens=self._max_tokens,
                        stream_options={"include_usage": True})
        body.update(self._extra)
        payload = json.dumps(body).encode("utf-8")
        t0 = time.perf_counter()
        resp = self._send(payload)
        if resp.status == 429:
            wait = min(float(resp.getheader("retry-after") or 5), 15.0)
            resp.read()
            time.sleep(wait)
            t0 = time.perf_counter()
            resp = self._send(payload)
        if resp.status != 200:
            err = resp.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {resp.status}: {err[:200]}")
        try:
            return read_openai_sse(resp, t0)
        except Exception:
            self._reset()
            raise

    def teardown(self):
        self._reset()


class HermesSessionAdapter(Adapter):
    uses_own_history = True

    def __init__(self, path: str, *, model_options: dict | None = None, provider: str | None = None,
                 request_model: str | None = None, missing_reason: str | None = None):
        super().__init__(request_model or "hermes-agent")
        self.path = path
        self._overrides = {}
        if model_options:
            self._overrides["model_options"] = model_options
        if provider:
            self._overrides["provider"] = provider
        if request_model:
            self._overrides["model"] = request_model
        self._missing_reason = missing_reason
        self._session_id = None

    def _headers(self):
        return {"Authorization": f"Bearer {API_SERVER_KEY}"}

    def unavailable_reason(self):
        if self._missing_reason:
            return self._missing_reason
        if not API_SERVER_KEY:
            return "API_SERVER_KEY not configured"
        try:
            http_json(f"{HERMES_BASE_URL}/health", timeout=3)
        except Exception as e:
            return f"Hermes gateway not reachable: {e}"
        return None

    def setup(self):
        title = f"ESP32 Voice Bench {self.path} {uuid.uuid4().hex[:6]}"
        data = http_json(f"{HERMES_BASE_URL}/api/sessions", method="POST", body={"title": title},
                         headers=self._headers(), timeout=15)
        self._session_id = data["session"]["id"]

    def ask(self, prompt, history):
        body = {"input": prompt, "instructions": SYSTEM_PROMPT, **self._overrides}
        try:
            data = http_json(f"{HERMES_BASE_URL}/api/sessions/{self._session_id}/chat", method="POST", body=body,
                             headers=self._headers(), timeout=180)
        except urllib.error.HTTPError as e:
            raise RuntimeError(http_error_text(e)) from None
        text = ((data.get("message") or {}).get("content") or "").strip()
        if any(p in text.lower() for p in BILLING_PHRASES):
            raise RuntimeError(f"provider error reply: {text[:160]}")
        usage = data.get("usage") or {}
        tokens = usage.get("output_tokens") or usage.get("completion_tokens")
        return Reply(text, None, tokens)

    def teardown(self):
        if not self._session_id:
            return
        try:
            http_json(f"{HERMES_BASE_URL}/api/sessions/{self._session_id}", method="DELETE",
                      headers=self._headers(), timeout=10)
        except Exception as e:
            print(f"    (could not delete bench session {self._session_id}: {e})")


class HermesCliAdapter(Adapter):
    path = "hermes-cli"
    uses_own_history = True
    max_calls = 2

    def __init__(self):
        super().__init__("hermes-agent")
        self._exe = next((p for p in HERMES_CLI_CANDIDATES if p.exists()), None)

    def unavailable_reason(self):
        return None if self._exe else "hermes CLI executable not found"

    def ask(self, prompt, history):
        result = subprocess.run([str(self._exe), "-z", f"{SYSTEM_PROMPT}\n\n{prompt}"], capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=240)
        if result.returncode != 0:
            raise RuntimeError(f"exit {result.returncode}: {(result.stderr or result.stdout)[-200:]}")
        return Reply(result.stdout.strip())


# ── Scoring ────────────────────────────────────────────────────────────
MARKDOWN_RE = re.compile(r"(\*\*|__|`|^#{1,6}\s|^\s*[-*•]\s)", re.MULTILINE)


def count_sentences(text: str) -> int:
    return len([s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()])


def count_lines(text: str) -> int:
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) == 1 and " / " in text:
        lines = [l for l in text.split(" / ") if l.strip()]
    return len(lines)


def expand_placeholders(values: list[str]) -> list[str]:
    weekday = datetime.datetime.now().strftime("%A").lower()
    return [v.replace("{today_weekday}", weekday) for v in values]


def score_reply(spec: dict, defaults: dict, text: str) -> tuple[float, dict]:
    rules = {**defaults, **spec}
    lower = text.lower()
    checks = {}
    if rules.get("expect_any"):
        checks["keyword"] = any(k.lower() in lower for k in expand_placeholders(rules["expect_any"]))
    if rules.get("expect_regex"):
        checks["pattern"] = re.search(rules["expect_regex"], lower) is not None
    if rules.get("reject_any"):
        checks["no_refusal"] = not any(k.lower() in lower for k in rules["reject_any"])
    if rules.get("max_sentences") is not None:
        checks["sentences"] = count_sentences(text) <= rules["max_sentences"]
    if rules.get("lines") is not None:
        checks["lines"] = count_lines(text) == rules["lines"]
    if rules.get("max_chars") is not None:
        checks["length"] = len(text) <= rules["max_chars"]
    if rules.get("no_markdown"):
        checks["no_markdown"] = MARKDOWN_RE.search(text) is None
    score = sum(checks.values()) / len(checks) if checks else 1.0
    return round(score, 3), checks


# ── Runner ─────────────────────────────────────────────────────────────
def run_adapter(adapter: Adapter, prompts: list[dict], defaults: dict, rounds: int) -> tuple[list[Result], str | None]:
    reason = adapter.unavailable_reason()
    if reason:
        return [], reason
    try:
        adapter.setup()
    except Exception as e:
        return [], f"setup failed: {e}"

    results, calls = [], 0
    try:
        for rnd in range(rounds):
            history: list[tuple[str, str]] = []
            for spec in prompts:
                if adapter.max_calls is not None and calls >= adapter.max_calls:
                    break
                t0 = time.perf_counter()
                reply, error = None, ""
                try:
                    reply = adapter.ask(spec["prompt"], [] if adapter.uses_own_history else history)
                    if not reply.text:
                        error = "empty reply"
                except Exception as e:
                    error = str(e)[:300] or e.__class__.__name__
                total = time.perf_counter() - t0
                ok = not error
                score, checks = score_reply(spec, defaults, reply.text) if ok else (0.0, {})
                results.append(Result(
                    path=adapter.path, model=adapter.model, prompt_id=spec["id"], category=spec.get("category", ""),
                    round=rnd, cold=(calls == 0), ok=ok, total_s=round(total, 3),
                    ttft_s=round(reply.ttft_s, 3) if reply and reply.ttft_s is not None else None,
                    out_tokens=reply.out_tokens if reply else None, text=reply.text if reply else "",
                    error=error, score=score, checks=checks))
                calls += 1
                status = f"{total:6.2f}s score={score:.2f}" if ok else f"{total:6.2f}s ERROR {error[:90]}"
                print(f"    r{rnd} {spec['id']:<15} {status}")
                if ok:
                    history.append((spec["prompt"], reply.text))
    finally:
        adapter.teardown()
    return results, None


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int(round(pct / 100.0 * len(ordered) + 0.5)) - 1))
    return ordered[rank]


def summarize(results: list[Result]) -> list[dict]:
    groups: dict[str, list[Result]] = {}
    for r in results:
        groups.setdefault(r.label, []).append(r)
    rows = []
    for label, group in groups.items():
        ok = [r for r in group if r.ok]
        warm = [r.total_s for r in ok if not r.cold] or [r.total_s for r in ok]
        cold = next((r.total_s for r in group if r.cold and r.ok), None)
        ttfts = [r.ttft_s for r in ok if r.ttft_s is not None and not r.cold]
        rates = []
        for r in ok:
            if r.out_tokens:
                gen_time = r.total_s - (r.ttft_s or 0.0)
                if gen_time > 0:
                    rates.append(r.out_tokens / gen_time)
        chat = [r for r in group if r.category != "tool"]
        tool = [r for r in group if r.category == "tool"]
        accuracy = statistics.mean(r.score for r in chat) if chat else None
        error_rate = 1 - len(ok) / len(group)
        rows.append({
            "label": label, "path": group[0].path, "model": group[0].model,
            "calls": len(group), "errors": len(group) - len(ok), "error_rate": round(error_rate, 3),
            "cold_s": cold, "p50_s": percentile(warm, 50), "p95_s": percentile(warm, 95),
            "p50_ttft_s": percentile(ttfts, 50),
            "tok_per_s": round(statistics.median(rates), 1) if rates else None,
            "accuracy": round(accuracy, 3) if accuracy is not None else None,
            "tool_score": round(statistics.mean(r.score for r in tool), 3) if tool else None,
            "eligible": bool(accuracy is not None and accuracy >= ACCURACY_THRESHOLD and error_rate < 0.2),
        })
    rows.sort(key=lambda r: (not r["eligible"], r["p50_s"] if r["p50_s"] is not None else 1e9))
    return rows


def fmt(value, spec: str = "6.2f") -> str:
    return format(value, spec) if isinstance(value, (int, float)) else "-".rjust(len(format(0.0, spec)))


def print_summary(rows: list[dict], skipped: dict):
    print("\n" + "=" * 112)
    print("  RESULTS (ranked: accuracy >= %.1f and <20%% errors first, then warm p50 total)" % ACCURACY_THRESHOLD)
    print("=" * 112)
    print(f"  {'path:model':<44} {'calls':>5} {'err':>4} {'cold':>7} {'p50':>7} {'p95':>7} {'ttft':>7} "
          f"{'tok/s':>7} {'acc':>5} {'tool':>5}")
    for r in rows:
        mark = "*" if r["eligible"] else " "
        print(f"{mark} {r['label'][:44]:<44} {r['calls']:>5} {r['errors']:>4} {fmt(r['cold_s'], '7.2f')} "
              f"{fmt(r['p50_s'], '7.2f')} {fmt(r['p95_s'], '7.2f')} {fmt(r['p50_ttft_s'], '7.2f')} "
              f"{fmt(r['tok_per_s'], '7.1f')} {fmt(r['accuracy'], '5.2f')} {fmt(r['tool_score'], '5.2f')}")
    if skipped:
        print("\n  Skipped:")
        for label, reason in skipped.items():
            print(f"    {label:<44} {reason}")
    print("=" * 112)


# ── Path construction ──────────────────────────────────────────────────
def ollama_installed() -> set[str] | None:
    try:
        data = http_json(f"{OLLAMA_HOST}/api/tags", timeout=3)
        return {m["name"] for m in data.get("models", []) if m.get("name")}
    except Exception:
        return None


def ollama_running() -> list[dict]:
    try:
        return http_json(f"{OLLAMA_HOST}/api/ps", timeout=3).get("models", [])
    except Exception:
        return []


def groq_available_models() -> tuple[set[str] | None, str | None]:
    if not GROQ_API_KEY:
        return None, "GROQ_API_KEY not configured"
    try:
        data = http_json(f"{GROQ_BASE_URL}/models", headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, timeout=10)
        return {m["id"] for m in data.get("data", [])}, None
    except urllib.error.HTTPError as e:
        return None, f"Groq /models failed: {http_error_text(e)}"
    except Exception as e:
        return None, f"Groq /models failed: {e}"


def hermes_has_provider(name: str) -> bool:
    config = HERMES_HOME / "config.yaml"
    if not config.exists():
        return False
    text = config.read_text(encoding="utf-8", errors="ignore")
    bare = name.split(":", 1)[-1]
    if re.search(rf"^\s+{re.escape(bare)}:\s*$", text, re.MULTILINE):
        return True
    return re.search(rf"^\s*-\s*name:\s*{re.escape(bare)}\s*$", text, re.MULTILINE) is not None


def build_adapters(selected: list[str], ollama_models: list[str], groq_models: list[str]) -> tuple[list[Adapter], dict]:
    adapters: list[Adapter] = []
    skipped: dict[str, str] = {}
    installed = ollama_installed() if {"ollama-local", "ollama-cloud-direct"} & set(selected) else None

    for path in selected:
        if path == "ollama-local":
            adapters += [OllamaAdapter(path, m, installed) for m in ollama_models]
        elif path == "ollama-cloud-direct":
            adapters.append(OllamaAdapter(path, OLLAMA_CLOUD_MODEL, installed))
        elif path == "hermes-session":
            adapters.append(HermesSessionAdapter(path))
        elif path == "hermes-session-low":
            adapters.append(HermesSessionAdapter(path, model_options={"reasoning_effort": "low"}))
        elif path == "hermes-session+groq":
            reason = None
            if not GROQ_API_KEY:
                reason = "GROQ_API_KEY not configured"
            elif not hermes_has_provider(HERMES_GROQ_PROVIDER):
                reason = f"Hermes provider '{HERMES_GROQ_PROVIDER}' not in config.yaml"
            adapters.append(HermesSessionAdapter(path, model_options={"reasoning_effort": "low"},
                                                 provider=HERMES_GROQ_PROVIDER, request_model=HERMES_GROQ_MODEL,
                                                 missing_reason=reason))
        elif path == "hermes-openai":
            adapters.append(OpenAIStreamAdapter(path, "hermes-agent", HERMES_BASE_URL + "/v1", API_SERVER_KEY,
                                                sampling=False, timeout=180,
                                                missing_reason=None if API_SERVER_KEY else "API_SERVER_KEY not configured"))
        elif path == "hermes-cli":
            adapters.append(HermesCliAdapter())
        elif path == "groq-direct":
            available, reason = groq_available_models()
            for model in groq_models:
                missing = reason or (None if model in available else f"model '{model}' not offered by Groq")
                adapters.append(OpenAIStreamAdapter(path, model, GROQ_BASE_URL, GROQ_API_KEY, missing_reason=missing))
        else:
            skipped[path] = "unknown path"
    return adapters, skipped


# ── Speech-to-text and end-to-end ──────────────────────────────────────
FIXTURE_TEXTS = {
    "capital": "What is the capital of Australia?",
    "black-hole": "Explain what a black hole is in two sentences.",
    "classroom-tip": "Give me one quick tip for keeping a Year 5 class focused after lunch.",
}


def make_wav_fixtures(out_dir: pathlib.Path) -> dict[str, pathlib.Path]:
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    try:
        paths = {}
        for key, text in FIXTURE_TEXTS.items():
            path = out_dir / f"{key}.wav"
            stream = win32com.client.Dispatch("SAPI.SpFileStream")
            stream.Format.Type = 18  # SAFT16kHz16BitMono, same shape the ESP32 uploads
            stream.Open(str(path), 3)
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            voice.AudioOutputStream = stream
            voice.Speak(text)
            stream.Close()
            paths[key] = path
        return paths
    finally:
        pythoncom.CoUninitialize()


def word_accuracy(expected: str, heard: str) -> float:
    want = re.findall(r"[a-z0-9]+", expected.lower())
    got = set(re.findall(r"[a-z0-9]+", heard.lower()))
    return round(sum(w in got for w in want) / len(want), 3) if want else 1.0


def groq_transcribe(wav_path: pathlib.Path) -> str:
    boundary = uuid.uuid4().hex
    buf = io.BytesIO()
    for name, value in (("model", GROQ_STT_MODEL), ("language", "en"), ("response_format", "json")):
        buf.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    buf.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{wav_path.name}\"\r\n"
              f"Content-Type: audio/wav\r\n\r\n".encode())
    buf.write(wav_path.read_bytes())
    buf.write(f"\r\n--{boundary}--\r\n".encode())
    req = urllib.request.Request(f"{GROQ_BASE_URL}/audio/transcriptions", data=buf.getvalue(), headers={
        "Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8")).get("text", "").strip()


def run_stt(fixtures: dict[str, pathlib.Path], rounds: int) -> list[dict]:
    rows = []
    engines = []
    try:
        from faster_whisper import WhisperModel
        t0 = time.perf_counter()
        model = WhisperModel("base", device="cpu", compute_type="int8")
        print(f"    faster-whisper base loaded in {time.perf_counter() - t0:.2f}s (excluded from timings)")

        def local(path):
            segments, _ = model.transcribe(str(path), beam_size=1, vad_filter=True, language="en")
            return " ".join(s.text for s in segments).strip()
        engines.append(("stt-local", "faster-whisper-base", local))
    except Exception as e:
        print(f"    stt-local skipped: {e}")
    if GROQ_API_KEY:
        engines.append(("stt-groq", GROQ_STT_MODEL, groq_transcribe))
    else:
        print("    stt-groq skipped: GROQ_API_KEY not configured")

    for path_name, model_name, fn in engines:
        for rnd in range(rounds):
            for key, wav in fixtures.items():
                t0 = time.perf_counter()
                try:
                    text, error = fn(wav), ""
                except Exception as e:
                    text, error = "", str(e)[:200]
                dur = time.perf_counter() - t0
                acc = word_accuracy(FIXTURE_TEXTS[key], text) if not error else 0.0
                rows.append({"path": path_name, "model": model_name, "fixture": key, "round": rnd,
                             "total_s": round(dur, 3), "word_accuracy": acc, "text": text, "error": error})
                print(f"    {path_name:<10} r{rnd} {key:<14} {dur:5.2f}s acc={acc:.2f} {error[:80]}")
    return rows


def run_e2e(fixtures: dict[str, pathlib.Path]) -> list[dict]:
    rows = []
    headers = {"Content-Type": "audio/wav"}
    if VOICE_RECEIVER_TOKEN:
        headers["Authorization"] = f"Bearer {VOICE_RECEIVER_TOKEN}"
    for audio in (False, True):
        for key, wav in fixtures.items():
            url = f"{RECEIVER_URL}/voice?audio={'1' if audio else '0'}"
            data = wav.read_bytes()
            for attempt in range(4):
                t0 = time.perf_counter()
                try:
                    req = urllib.request.Request(url, data=data, headers=headers)
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        body = json.loads(resp.read().decode("utf-8"))
                    error = ""
                except urllib.error.HTTPError as e:
                    if e.code == 429 and attempt < 3:
                        time.sleep(3)
                        continue
                    body, error = {}, http_error_text(e)
                except Exception as e:
                    body, error = {}, str(e)[:200]
                break
            dur = time.perf_counter() - t0
            timing = body.get("timing") or {}
            rows.append({"fixture": key, "audio": audio, "roundtrip_s": round(dur, 3), "backend": body.get("backend"),
                         "timing_ms": timing, "transcript": body.get("transcript"), "reply": body.get("reply"),
                         "error": error})
            print(f"    audio={'on ' if audio else 'off'} {key:<14} {dur:5.2f}s backend={body.get('backend')} "
                  f"timing={timing} {error[:80]}")
    return rows


# ── Main ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="comma-separated paths (default: all)")
    parser.add_argument("--skip", help="comma-separated paths to exclude")
    parser.add_argument("--runs", type=int, default=3, help="rounds of the prompt set for direct paths")
    parser.add_argument("--agent-runs", type=int, default=1, help="rounds for hermes-* paths (slow, stateful)")
    parser.add_argument("--prompts", default=str(SERVER_DIR / "bench_prompts.json"))
    parser.add_argument("--limit", type=int, help="use only the first N prompts")
    parser.add_argument("--ollama-models", help="comma-separated local Ollama models")
    parser.add_argument("--groq-models", help="comma-separated Groq models")
    parser.add_argument("--stt", action="store_true", help="also compare local Whisper vs Groq Whisper")
    parser.add_argument("--e2e", action="store_true",
                        help="also POST spoken fixtures to the running receiver (may speak on host speakers)")
    parser.add_argument("--out", default=str(SERVER_DIR / "bench_results"))
    parser.add_argument("--list", action="store_true", help="list paths and exit")
    args = parser.parse_args()

    if args.list:
        print("\n".join(ALL_PATHS))
        return

    selected = [p.strip() for p in (args.only.split(",") if args.only else ALL_PATHS) if p.strip()]
    if args.skip:
        excluded = {p.strip() for p in args.skip.split(",")}
        selected = [p for p in selected if p not in excluded]
    spec = json.loads(pathlib.Path(args.prompts).read_text(encoding="utf-8"))
    prompts = spec["prompts"][: args.limit] if args.limit else spec["prompts"]
    defaults = spec.get("defaults", {})
    ollama_models = args.ollama_models.split(",") if args.ollama_models else DEFAULT_OLLAMA_MODELS
    groq_models = args.groq_models.split(",") if args.groq_models else list(GROQ_MODELS)

    print("=" * 112)
    print("  Hermes Voice Satellite - LLM path benchmark")
    print(f"  Paths: {', '.join(selected)}")
    print(f"  Prompts: {len(prompts)} | rounds: direct={args.runs}, agent={args.agent_runs} | max_tokens={MAX_TOKENS}")
    print("=" * 112)

    warm_before = [m.get("name") for m in ollama_running()]
    adapters, skipped = build_adapters(selected, ollama_models, groq_models)
    results: list[Result] = []
    for adapter in adapters:
        label = f"{adapter.path}:{adapter.model}"
        rounds = args.agent_runs if adapter.path in AGENT_PATHS else args.runs
        print(f"\n>>> {label} ({rounds} round{'s' if rounds != 1 else ''})")
        rows, reason = run_adapter(adapter, prompts, defaults, rounds)
        if reason:
            print(f"    skipped: {reason}")
            skipped[label] = reason
        results += rows

    if warm_before and any(a.path.startswith("ollama") for a in adapters):
        restore = warm_before[0]
        print(f"\n>>> Re-warming production Ollama model '{restore}' (keep_alive 8h)")
        try:
            http_json(f"{OLLAMA_HOST}/api/generate", method="POST", timeout=120, body={
                "model": restore, "prompt": "", "keep_alive": "8h", "options": {"num_ctx": 2048}})
        except Exception as e:
            print(f"    re-warm failed: {e}")

    stt_rows, e2e_rows = [], []
    if args.stt or args.e2e:
        fixture_dir = pathlib.Path(tempfile.mkdtemp(prefix="hermes_bench_"))
        fixtures = make_wav_fixtures(fixture_dir)
        if args.stt:
            print("\n>>> Speech-to-text comparison")
            stt_rows = run_stt(fixtures, args.runs)
        if args.e2e:
            print(f"\n>>> End-to-end via receiver {RECEIVER_URL}/voice")
            e2e_rows = run_e2e(fixtures)

    rows = summarize(results)
    print_summary(rows, skipped)
    if stt_rows:
        print("\n  Speech-to-text (median seconds, mean word accuracy):")
        for name in sorted({r["path"] for r in stt_rows}):
            group = [r for r in stt_rows if r["path"] == name and not r["error"]]
            if group:
                print(f"    {name:<10} {statistics.median(r['total_s'] for r in group):5.2f}s  "
                      f"acc={statistics.mean(r['word_accuracy'] for r in group):.2f}")

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    report = {
        "meta": {"timestamp": stamp, "paths": selected, "runs": args.runs, "agent_runs": args.agent_runs,
                 "max_tokens": MAX_TOKENS, "temperature": TEMPERATURE, "prompts": len(prompts)},
        "summary": rows, "skipped": skipped, "results": [asdict(r) for r in results],
        "stt": stt_rows, "e2e": e2e_rows,
    }
    json_path = out_dir / f"{stamp}.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    csv_path = out_dir / f"{stamp}.csv"
    if rows:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    print(f"\n  Saved: {json_path}" + (f"\n         {csv_path}" if rows else ""))


if __name__ == "__main__":
    main()
