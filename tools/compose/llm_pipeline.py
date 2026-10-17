"""
LLM generation pipeline with Groq high-speed cloud generation,
local Ollama fallback, and automatic multi-round continuation.
"""

import time
import logging
import requests
from prompt_engine import sanitize_plain_text, CONTINUATION_PROMPT


class LlmPipeline:
    def __init__(
        self,
        groq_api_key: str | None = None,
        groq_base_url: str = "https://api.groq.com/openai/v1",
        groq_model: str = "llama-3.3-70b-versatile",
        ollama_host: str = "http://127.0.0.1:11434",
        ollama_model: str = "llama3.2:latest",
        local_only: bool = False,
        max_continuation_rounds: int = 4,
    ):
        self.groq_api_key = groq_api_key.strip() if groq_api_key else None
        self.groq_base_url = groq_base_url.rstrip("/")
        self.groq_model = groq_model
        self.ollama_host = ollama_host.rstrip("/")
        self.ollama_model = ollama_model
        self.local_only = local_only
        self.max_continuation_rounds = max_continuation_rounds

    def _call_groq(self, messages: list[dict], temperature: float = 0.3) -> tuple[str, str]:
        """Calls Groq chat completions endpoint. Returns (content, finish_reason)."""
        url = f"{self.groq_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.groq_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2048,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=20.0)
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]
        content = choice["message"]["content"]
        finish_reason = choice.get("finish_reason", "stop")
        return content, finish_reason

    def _call_ollama(self, messages: list[dict], temperature: float = 0.3) -> tuple[str, str]:
        """Calls local Ollama chat completions endpoint. Returns (content, finish_reason)."""
        url = f"{self.ollama_host}/v1/chat/completions"
        payload = {
            "model": self.ollama_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2048,
        }
        resp = requests.post(url, json=payload, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]
        content = choice["message"]["content"]
        finish_reason = choice.get("finish_reason", "stop")
        return content, finish_reason

    def generate(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        on_status_update=None,
    ) -> tuple[str, str, float, int]:
        """
        Executes LLM generation with automatic multi-round continuation if length exceeded.
        Returns: (final_text, provider_used, latency_seconds, num_parts)
        """
        t0 = time.time()
        active_provider = "ollama"
        call_fn = self._call_ollama

        if self.groq_api_key and not self.local_only:
            try:
                # Test connectivity with first call
                active_provider = "groq"
                call_fn = self._call_groq
            except Exception:
                active_provider = "ollama"
                call_fn = self._call_ollama

        accumulated_parts = []
        current_messages = list(messages)
        rounds = 0

        while rounds < self.max_continuation_rounds:
            rounds += 1
            if rounds > 1 and on_status_update:
                on_status_update(f"Writing... (Part {rounds})")

            try:
                content, finish_reason = call_fn(current_messages, temperature)
            except Exception as e:
                if active_provider == "groq":
                    logging.warning("Groq call failed (%s). Falling back to local Ollama...", e)
                    active_provider = "ollama"
                    call_fn = self._call_ollama
                    content, finish_reason = call_fn(current_messages, temperature)
                else:
                    logging.error("Ollama generation failed: %s", e)
                    raise e

            accumulated_parts.append(content)

            # Check if generation was truncated due to token limit
            if finish_reason == "length" and rounds < self.max_continuation_rounds:
                current_messages.append({"role": "assistant", "content": content})
                current_messages.append({"role": "user", "content": CONTINUATION_PROMPT})
                continue
            else:
                break

        full_text = "\n".join(accumulated_parts).strip()
        cleaned_text = sanitize_plain_text(full_text)
        latency = time.time() - t0

        return cleaned_text, active_provider, latency, rounds


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pipeline = LlmPipeline(local_only=True)
    msgs = [{"role": "user", "content": "Reply with 'Pipeline Test Successful' and nothing else."}]
    print("[LlmPipeline] Testing Ollama generation...")
    text, provider, lat, parts = pipeline.generate(msgs)
    print(f"[LlmPipeline] Result from {provider} in {lat:.2f}s ({parts} parts): '{text}'")
    assert "successful" in text.lower(), "Expected success message"
    print("[LlmPipeline] Test Passed!")
