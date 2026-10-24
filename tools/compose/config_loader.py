"""Shared companion settings. Cloud keys may live in compose.env, server/.env, or Hermes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

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
    "GROQ_ASSISTANT_MODEL", "HISTORY_ENABLED",
    "MEDIA_SERVER_URL", "MEDIA_SERVER_TOKEN", "MEDIA_SYNC_ENABLED",
    "IMAGE_MODEL", "OPENAI_API_KEY", "IMAGE_GENERATION_ENABLED", "IMAGE_ESTIMATE_AUD_CENTS",
    "IMAGE_PROVIDER", "GOOGLE_IMAGE_MODEL",
    "GOOGLE_IMAGE_SIZE", "GOOGLE_IMAGE_ASPECT_RATIO", "GOOGLE_IMAGE_THINKING",
    "GOOGLE_IMAGE_ESTIMATE_1K_AUD_CENTS", "GOOGLE_IMAGE_ESTIMATE_2K_AUD_CENTS", "GOOGLE_IMAGE_ESTIMATE_4K_AUD_CENTS",
    "ESP32_START_RECEIVER", "ESP32_ENABLE_HOTKEYS", "HERMES_ENABLED", "HERMES_URL",
    "DEVICE_FEEDBACK_PORT", "DEVICE_FEEDBACK_ID",
)

GROQ_FALLBACK_KEYS = {key for key in ENV_KEYS if key.startswith("GROQ_")}


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


def load_env_config(
    compose_dir: Path | None = None,
    *,
    settings_loader: Callable[[], dict] | None = None,
    defaults: dict[str, str] | None = None,
) -> dict[str, str]:
    """Load Groq fallbacks, Compose, protected feature settings, then process overrides.

    Other services' files supply Groq settings only. They cannot turn on feature
    listeners or redirect Hermes/media. The Hermes token comes only from the
    protected settings loader, never an environment file or process variable.
    """
    env_vars: dict[str, str] = dict(defaults or {})
    paths = fallback_env_paths(compose_dir)
    for path in paths[:-1]:
        if path.is_file():
            _merge_nonempty(env_vars, {
                key: value for key, value in _parse_env_file(path).items()
                if key in GROQ_FALLBACK_KEYS
            })
    _merge_nonempty(env_vars, {
        key: value for key, value in _parse_env_file(paths[-1]).items()
        if key not in {"HERMES_TOKEN", "GOOGLE_IMAGE_API_KEY"}
    })
    if settings_loader is not None:
        try:
            env_vars.update(settings_loader())
        except Exception:
            # Unavailable protected storage must not disable offline writing.
            pass
    for key in ENV_KEYS:
        value = os.environ.get(key)
        if value:
            env_vars[key] = value
    return env_vars
