"""
Hermes Standalone Benchmark Tool
Compares execution time of one-shot 'hermes.exe -z' CLI subprocess
vs. persistent HTTP Gateway endpoint (http://127.0.0.1:8642/v1/chat/completions).
"""

import os
import sys
import time
import json
import urllib.request
import subprocess

HERMES_HOME = os.path.expanduser(r"~\AppData\Local\hermes")
HERMES_ENV_PATH = os.path.join(HERMES_HOME, ".env")
HERMES_BIN = os.path.join(HERMES_HOME, "bin", "hermes.exe")
GATEWAY_URL = os.environ.get("HERMES_GATEWAY_URL", "http://127.0.0.1:8642/v1/chat/completions")

# 1. Load API_SERVER_KEY from .env or environment
api_key = os.environ.get("API_SERVER_KEY")
if not api_key:
    candidates = [
        os.path.expanduser("~/.hermes/.env"),
        HERMES_ENV_PATH,
        os.path.join(os.path.dirname(__file__), ".env")
    ]
    for env_path in candidates:
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("API_SERVER_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
        if api_key:
            break

if not api_key:
    print("[Error] Could not find API_SERVER_KEY in ~/.hermes/.env or environment")
    sys.exit(1)

TEST_PROMPT = "What is the capital of France?"

def query_gateway(prompt: str) -> tuple[float, str]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = json.dumps({
        "model": "hermes-agent",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }).encode("utf-8")

    req = urllib.request.Request(GATEWAY_URL, data=payload, headers=headers)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    t1 = time.perf_counter()
    reply = body["choices"][0]["message"]["content"].strip()
    return (t1 - t0), reply

def query_cli(prompt: str) -> tuple[float, str]:
    cmd = [HERMES_BIN, "-z", prompt]
    t0 = time.perf_counter()
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
        encoding="utf-8",
        errors="replace"
    )
    t1 = time.perf_counter()
    reply = result.stdout.strip()
    return (t1 - t0), reply

def main():
    num_runs = 5
    print("================================================================")
    print("   Hermes Latency Benchmark: One-Shot CLI vs Persistent Gateway ")
    print(f"   Prompt: '{TEST_PROMPT}'")
    print(f"   Runs per test: {num_runs}")
    print("================================================================\n")

    # Benchmark Gateway
    print("--- Testing Persistent Hermes Gateway (HTTP :8642) ---")
    gateway_times = []
    gateway_replies = []
    for i in range(1, num_runs + 1):
        try:
            dur, reply = query_gateway(TEST_PROMPT)
            gateway_times.append(dur)
            gateway_replies.append(reply)
            print(f"  Gateway Run {i}: {dur:6.2f}s | Reply: {reply[:60]}...")
        except Exception as e:
            print(f"  Gateway Run {i}: FAILED ({e})")

    print("\n--- Testing One-Shot CLI (hermes.exe -z) ---")
    cli_times = []
    cli_replies = []
    for i in range(1, num_runs + 1):
        try:
            dur, reply = query_cli(TEST_PROMPT)
            cli_times.append(dur)
            cli_replies.append(reply)
            print(f"  CLI Run {i}:     {dur:6.2f}s | Reply: {reply[:60]}...")
        except Exception as e:
            print(f"  CLI Run {i}: FAILED ({e})")

    print("\n================================================================")
    print("                      BENCHMARK RESULTS                         ")
    print("================================================================")
    if gateway_times:
        avg_gw = sum(gateway_times) / len(gateway_times)
        min_gw = min(gateway_times)
        max_gw = max(gateway_times)
        print(f"Gateway : Avg: {avg_gw:5.2f}s | Min: {min_gw:5.2f}s | Max: {max_gw:5.2f}s | Runs: {[round(t, 2) for t in gateway_times]}")
    if cli_times:
        avg_cli = sum(cli_times) / len(cli_times)
        min_cli = min(cli_times)
        max_cli = max(cli_times)
        print(f"CLI -z  : Avg: {avg_cli:5.2f}s | Min: {min_cli:5.2f}s | Max: {max_cli:5.2f}s | Runs: {[round(t, 2) for t in cli_times]}")

    if gateway_times and cli_times:
        speedup = avg_cli - avg_gw
        pct = ((avg_cli - avg_gw) / avg_cli) * 100
        print(f"\nLatency Saved: {speedup:5.2f}s per request ({pct:4.1f}% reduction)")
    print("================================================================\n")

if __name__ == "__main__":
    main()
