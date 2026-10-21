"""Shared companion settings. Cloud keys may live in compose.env, server/.env, or Hermes."""

from __future__ import annotations

import os
from pathlib import Path

ENV_KEYS = (
    "GROQ_API_KEY",
    "GROQ_BASE_URL",
    "GROQ_STT_MODEL",
    "GROQ_LLM_MODEL",
    "LOCAL_WHISPER_MODEL",
    "LOCAL_WHISPER_DEVICE",
    "OLLAMA_HOST",
    "OLLAMA_MODEL",
    "LOCAL_ONLY",
    "AUDIO_INPUT_DEVICE",
    "AUDIO_SAMPLE_RATE",
    "CLIPBOARD_RESTORE_DELAY",
    "CONTINUATION_MAX_ROUNDS",
    "WEB_SEARCH_ENABLED",
    "BRAVE_API_KEY",
    "BRAVE_COUNTRY",
    "BRAVE_RESULT_COUNT",
    "INTENT_ROUTER",
    "OPENROUTER_API_KEY",
    "OPENROUTER_BASE_URL",
    "JEV_MODEL",
    "ROUTER_GROQ_MODEL",
)


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def _merge_nonempty(dst: dict[str, str], src: dict[str, str]) -> None:
    for key, value in src.items():
        if value:
            dst[key] = value


def fallback_env_paths(compose_dir: Path | None = None) -> list[Path]:
    compose_dir = compose_dir or Path(__file__).resolve().parent
    local_app = os.environ.get("LOCALAPPDATA", "")
    return [
        Path(local_app) / "hermes" / ".env" if local_app else Path(),
        compose_dir.parents[1] / "server" / ".env",
        compose_dir / "compose.env",
    ]


def load_env_config(compose_dir: Path | None = None) -> dict[str, str]:
    """Load settings with this override order: Hermes, server/.env, compose.env, process env.

    Empty values do not wipe a key already found. That lets work Compose reuse the
    Groq key already configured for the home-speed voice fast lane.
    """
    env_vars: dict[str, str] = {}
    for path in fallback_env_paths(compose_dir):
        if path and path.exists():
            _merge_nonempty(env_vars, _parse_env_file(path))
    for key in ENV_KEYS:
        value = os.environ.get(key)
        if value:
            env_vars[key] = value
    return env_vars
