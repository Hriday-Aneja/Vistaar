"""LLM router with a fallback chain: Gemini -> Groq -> offline rules.

If a provider errors or times out, the next one is tried, so a demo never dies on an API outage.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings

Provider = Callable[[str], str]


class LLMRouter:
    def __init__(self, providers: list[tuple[str, Provider]], offline: Provider) -> None:
        self.providers = providers
        self.offline = offline

    def complete(self, prompt: str) -> tuple[str, str]:
        """Returns (provider_name, text)."""
        for name, fn in self.providers:
            try:
                return name, fn(prompt)
            except Exception:
                continue
        return "offline", self.offline(prompt)


def _gemini(api_key: str) -> Provider:
    def call(prompt: str) -> str:
        import httpx

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash:generateContent?key={api_key}"
        )
        r = httpx.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
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
            timeout=15,
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
