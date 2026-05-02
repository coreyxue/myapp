"""Pluggable LLM client.

Three backends:
  * ollama  — POST to a local Ollama server (default)
  * openai  — OpenAI-compatible Chat Completions endpoint
  * mock    — deterministic heuristic, used when no server is reachable

The mock backend is also what the test suite exercises so the pipeline is
always runnable without external infrastructure.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional

import httpx


@dataclass
class LLMConfig:
    backend: str = "ollama"
    model: str = "qwen2.5:7b-instruct"
    base_url: str = "http://localhost:11434"
    api_key: Optional[str] = None
    temperature: float = 0.4
    timeout_s: float = 120.0

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            backend=os.getenv("COMICFORGE_LLM", "ollama"),
            model=os.getenv("COMICFORGE_MODEL", "qwen2.5:7b-instruct"),
            base_url=os.getenv("COMICFORGE_LLM_URL", "http://localhost:11434"),
            api_key=os.getenv("COMICFORGE_LLM_KEY") or None,
        )


class LLMUnavailable(RuntimeError):
    pass


class LLMClient:
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig.from_env()

    def complete_json(self, system: str, user: str, *, schema_hint: str = "") -> Any:
        """Return a parsed JSON object. Raises LLMUnavailable on transport failure."""
        prompt_user = user
        if schema_hint:
            prompt_user += f"\n\nReturn ONLY valid JSON matching this shape:\n{schema_hint}"

        if self.config.backend == "mock":
            raise LLMUnavailable("mock backend selected")

        try:
            if self.config.backend == "ollama":
                return self._ollama(system, prompt_user)
            if self.config.backend == "openai":
                return self._openai(system, prompt_user)
        except (httpx.HTTPError, OSError) as e:
            raise LLMUnavailable(str(e)) from e

        raise LLMUnavailable(f"unknown backend {self.config.backend}")

    # ---- backends ----

    def _ollama(self, system: str, user: str) -> Any:
        url = f"{self.config.base_url.rstrip('/')}/api/chat"
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": self.config.temperature},
        }
        with httpx.Client(timeout=self.config.timeout_s) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
        return _parse_json(data["message"]["content"])

    def _openai(self, system: str, user: str) -> Any:
        url = f"{self.config.base_url.rstrip('/')}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.config.temperature,
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=self.config.timeout_s) as client:
            r = client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        return _parse_json(data["choices"][0]["message"]["content"])


def _parse_json(text: str) -> Any:
    text = text.strip()
    # tolerate ```json ... ``` fences
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text)
