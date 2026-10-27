"""LLM router with a fallback chain: Gemini -> Groq -> offline rules.

If a provider errors or times out, the next one is tried, so a demo never dies on an API outage.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from functools import lru_cache
from typing import TYPE_CHECKING

from app import tuning

if TYPE_CHECKING:
    from app.config import Settings

log = logging.getLogger(__name__)
_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="llm")

Provider = Callable[[str], str]


class LLMRouter:
    def __init__(self, providers: list[tuple[str, Provider]], offline: Provider) -> None:
        self.providers = providers
        self.offline = offline

    def complete(self, prompt: str) -> tuple[str, str]:
        """Returns (provider_name, text). Logs which provider answered; failures log the error type only, because
        httpx error text can contain the request URL (and with it the Gemini API key)."""
        for name, fn in self.providers:
            try:
                text = fn(prompt)
            except Exception as exc:
                log.warning("LLM provider %s failed (%s)", name, type(exc).__name__)
                continue
            log.info("LLM answered via %s", name)
            return name, text
        log.info("LLM answered via offline")
        return "offline", self.offline(prompt)

    def complete_within(self, prompt: str, timeout_s: float | None = None) -> tuple[str, str]:
        """Like complete(), but gives up after timeout_s (default tuning.LLM_TIMEOUT_S, 5 s) in total and returns the
        offline answer. Callers treat provider "offline" as "no LLM answer" and use their own rules."""
        limit = tuning.LLM_TIMEOUT_S if timeout_s is None else timeout_s
        future = _pool.submit(self.complete, prompt)
        try:
            return future.result(timeout=limit)
        except FutureTimeout:
            log.warning("LLM router timed out after %ss, using the offline answer", limit)
            return "offline", self.offline(prompt)


def _gemini(api_key: str) -> Provider:
    def call(prompt: str) -> str:
        import httpx

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash:generateContent?key={api_key}"
        )
        r = httpx.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=tuning.LLM_TIMEOUT_S)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    return call


def _groq(api_key: str) -> Provider:
    def call(prompt: str) -> str:
        import httpx

        r = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=tuning.LLM_TIMEOUT_S,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    return call


def _offline(prompt: str) -> str:
    # TODO: template-based Hinglish replies so the demo works with zero network.
    return "Abhi AI service available nahi hai. Order plan ready hai, approve karke aage badhein."


def build_router(settings: Settings) -> LLMRouter:
    providers: list[tuple[str, Provider]] = []
    if settings.gemini_api_key:
        providers.append(("gemini", _gemini(settings.gemini_api_key)))
    if settings.groq_api_key:
        providers.append(("groq", _groq(settings.groq_api_key)))
    return LLMRouter(providers, _offline)


@lru_cache
def get_router() -> LLMRouter:
    from app.config import get_settings

    return build_router(get_settings())
