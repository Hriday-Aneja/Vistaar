"""In-memory sliding-window limiter. Stdlib only, so it is unit-tested without FastAPI.

Per process: with several API workers or servers each one counts on its own. Move it to Redis if you scale out.
"""
import threading
import time
from collections import deque
from math import ceil
from typing import Optional


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_s: float, max_keys: int = 10_000):
        self.limit, self.window_s, self.max_keys = limit, window_s, max_keys
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def _now(self, now: Optional[float]) -> float:
        return time.monotonic() if now is None else now

    def retry_after(self, key: str, now: Optional[float] = None) -> int:
        """Seconds until one more hit is allowed for this key; 0 means allowed now. Does not record a hit."""
        t = self._now(now)
        with self._lock:
            q = self._hits.get(key)
            if not q:
                return 0
            while q and q[0] <= t - self.window_s:
                q.popleft()
            if not q:
                del self._hits[key]
                return 0
            if len(q) < self.limit:
                return 0
            return max(1, ceil(q[0] + self.window_s - t))

    def add(self, key: str, now: Optional[float] = None) -> None:
        t = self._now(now)
        with self._lock:
            if len(self._hits) >= self.max_keys:  # keep memory bounded: drop keys whose hits have all expired
                for k in [k for k, q in self._hits.items() if not q or q[-1] <= t - self.window_s]:
                    del self._hits[k]
            self._hits.setdefault(key, deque()).append(t)

    def clear(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)