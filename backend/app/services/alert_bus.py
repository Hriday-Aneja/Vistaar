"""Redis Pub/Sub for live Pulse and sales-drop alerts. One channel per shop: alerts:{shop_id}.

Publishing never raises: if Redis is down (or switched off) nothing is pushed and the Pulse page falls back to
polling the alerts API. After a failed publish further attempts are skipped for RETRY_AFTER_S so a dead Redis
cannot slow a Celery run down. The negotiation/auction stream does not use this module.

Tests plug in InMemoryBus with set_bus(); nothing in the test suite talks to a real Redis.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, Protocol

from app import tuning
from app.config import get_settings

log = logging.getLogger(__name__)

RETRY_AFTER_S = 30.0


def channel_for(shop_id: int) -> str:
    return f"alerts:{shop_id}"


class BusUnavailable(Exception):
    """There is no bus to talk to (live alerts switched off)."""


class AlertBus(Protocol):
    def publish(self, channel: str, message: str) -> None: ...

    def subscribe(self, channel: str) -> Any:
        """Async context manager that yields an async iterator of message strings."""


class NullBus:
    def publish(self, channel: str, message: str) -> None:
        raise BusUnavailable

    def subscribe(self, channel: str) -> Any:
        raise BusUnavailable


class RedisBus:
    def __init__(self, url: str) -> None:
        self.url = url
        self._client: Any = None

    def _sync_client(self) -> Any:
        if self._client is None:
            import redis

            self._client = redis.Redis.from_url(self.url, socket_connect_timeout=0.5, socket_timeout=0.5)
        return self._client

    def publish(self, channel: str, message: str) -> None:
        self._sync_client().publish(channel, message)

    @asynccontextmanager
    async def subscribe(self, channel: str):
        import redis.asyncio as aioredis

        client = aioredis.Redis.from_url(self.url, socket_connect_timeout=2)
        pubsub = client.pubsub()
        try:
            await pubsub.subscribe(channel)

            async def messages():
                while True:
                    msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if msg is None:
                        continue
                    data = msg["data"]
                    yield data.decode() if isinstance(data, bytes) else str(data)

            yield messages()
        finally:
            for closer in (lambda: pubsub.unsubscribe(channel), pubsub.aclose, client.aclose):
                try:
                    await closer()
                except Exception:  # noqa: BLE001, S110 - best-effort cleanup
                    pass


class InMemoryBus:
    """Single-process stand-in with the same interface. Thread-safe publish, async subscribe."""

    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []
        self._subs: dict[str, list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]]] = {}
        self._lock = threading.Lock()

    def publish(self, channel: str, message: str) -> None:
        with self._lock:
            self.published.append((channel, message))
            targets = list(self._subs.get(channel, []))
        for loop, queue in targets:
            loop.call_soon_threadsafe(queue.put_nowait, message)

    @asynccontextmanager
    async def subscribe(self, channel: str):
        entry = (asyncio.get_running_loop(), asyncio.Queue())
        with self._lock:
            self._subs.setdefault(channel, []).append(entry)

        async def messages():
            while True:
                yield await entry[1].get()

        try:
            yield messages()
        finally:
            with self._lock:
                self._subs[channel].remove(entry)


_bus: AlertBus | None = None
_down_until = 0.0


def get_bus() -> AlertBus:
    global _bus
    if _bus is None:
        _bus = RedisBus(get_settings().redis_url) if tuning.ALERTS_REDIS_ENABLED else NullBus()
    return _bus


def set_bus(bus: AlertBus | None) -> None:
    """Swap the bus (tests). None resets to the configured default."""
    global _bus, _down_until
    _bus, _down_until = bus, 0.0


def publish_alert(shop_id: int, event: dict) -> bool:
    """Publish one alert event to the shop's channel. True if it was handed to the bus, False otherwise. Never raises."""
    global _down_until
    if time.monotonic() < _down_until:
        return False
    try:
        get_bus().publish(channel_for(shop_id), json.dumps(event, default=str))
        return True
    except BusUnavailable:
        return False
    except Exception as exc:  # noqa: BLE001 - a dead Redis must not break the task or the API
        _down_until = time.monotonic() + RETRY_AFTER_S
        log.warning("Live alert not published (%s); skipping Redis for %ss", exc, RETRY_AFTER_S)
        return False
