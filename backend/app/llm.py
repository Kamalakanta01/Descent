"""OpenRouter client. Uses the live free model list, ranked by known-strong
reasoning/coding providers. Falls back to a curated hardcoded list if the
models endpoint is unreachable, and ultimately to None (caller can serve
static authored hints)."""

from __future__ import annotations

import json
import os
import time
from typing import Callable

MODELS_URL = "https://openrouter.ai/api/v1/models"
CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

# Provider hint ranking (substring match, lowercase). First match wins the
# best-of-position. These are the historically strong reasoning/coding
# families on OpenRouter's free tier; live models get ranked against this.
PREFERENCE = [
    "deepseek",          # DeepSeek V3.x / R1
    "qwen3-coder",       # Qwen3 Coder (coding specialist)
    "moonshot", "kimi",  # Moonshot Kimi K2
    "qwen",              # Qwen3 235B
    "z-ai", "glm",       # Z.ai GLM
    "minimax",           # MiniMax M-series (syllabus preference)
    "gpt-oss",           # OpenAI open weights
    "nemotron",          # NVIDIA reasoning models
    "north",             # Cohere North code models
    "poolside", "laguna",
    "gemma",
    "llama",
]

# Last-resort fallback if we can't reach the models endpoint at all.
# Ids have rotated on OpenRouter before — keep a small list of strong models.
FALLBACK_MODELS = [
    "minimax/minimax-m2.7:free",
    "minimax/minimax-m3:free",
    "z-ai/glm-5.2:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]

CACHE_TTL_S = 600  # refresh candidate list every 10 min


def _is_free(model: dict) -> bool:
    pricing = model.get("pricing") or {}
    try:
        return float(pricing.get("prompt", "1")) == 0.0 and float(pricing.get("completion", "1")) == 0.0
    except (TypeError, ValueError):
        return False


def _rank(model_id: str) -> int:
    mid = model_id.lower()
    for i, hint in enumerate(PREFERENCE):
        if hint in mid:
            return i
    return len(PREFERENCE) + 1


def _default_get(url: str, headers: dict, timeout: float) -> dict:
    import httpx

    with httpx.Client(timeout=timeout) as client:
        r = client.get(url, headers=headers)
        r.raise_for_status()
        return r.json()


def _default_post(url: str, headers: dict, payload: dict, timeout: float) -> tuple[int, dict]:
    import httpx

    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, headers=headers, json=payload)
        try:
            body = r.json()
        except json.JSONDecodeError:
            body = {"raw": r.text[:500]}
        return r.status_code, body


class LLMClient:
    def __init__(
        self,
        api_key: str | None,
        get_fn: Callable | None = None,
        post_fn: Callable | None = None,
        sleep_fn: Callable | None = None,
    ):
        self.api_key = api_key
        self._get = get_fn or _default_get
        self._post = post_fn or _default_post
        self._sleep = sleep_fn or time.sleep
        self._candidates: list[str] = []
        self._cached_at: float = 0.0

    def candidate_models(self, max_results: int = 6) -> list[str]:
        now = time.time()
        if self._candidates and now - self._cached_at < CACHE_TTL_S:
            return self._candidates
        found: list[str] = []
        if self.api_key:
            try:
                data = self._get(MODELS_URL, headers={}, timeout=15)
                free = [m for m in data.get("data", []) if _is_free(m)]
                free.sort(key=lambda m: _rank(m["id"]))
                found = [m["id"] for m in free[:max_results]]
            except Exception:
                found = []
        if not found:
            for m in FALLBACK_MODELS:
                if m not in found:
                    found.append(m)
        self._candidates = found
        self._cached_at = now
        return self._candidates

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        max_models: int = 4,
        timeout: float = 45.0,
    ) -> tuple[str | None, str | None]:
        """Try candidates in order. Returns (content, model_used) or (None, None)."""
        if not self.api_key:
            return None, None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Descent",
        }
        payload_base = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.4,
            "max_tokens": 600,
        }
        for model in self.candidate_models(max_models):
            payload = {**payload_base, "model": model}
            try:
                status, body = self._post(CHAT_URL, headers, payload, timeout)
            except Exception:
                self._sleep(0.5)
                continue
            if status == 200:
                try:
                    content = body["choices"][0]["message"]["content"].strip()
                except (KeyError, IndexError, TypeError):
                    self._sleep(0.5)
                    continue
                if content:
                    return content, model
            self._sleep(0.5)
        return None, None
