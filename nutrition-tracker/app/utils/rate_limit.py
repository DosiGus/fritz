"""Simple in-memory fixed-window rate limiter (thread-safe, no extra dependencies)."""

from __future__ import annotations

import threading
import time


class SimpleRateLimiter:
    """Allow at most *max_calls* requests within each rolling *period* seconds.

    Thread-safe; blocks the calling thread when the limit is reached.
    """

    def __init__(self, max_calls: int, period: float) -> None:
        self._max_calls = max_calls
        self._period = period
        self._timestamps: list[float] = []
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            cutoff = now - self._period
            self._timestamps = [t for t in self._timestamps if t > cutoff]

            if len(self._timestamps) >= self._max_calls:
                oldest = self._timestamps[0]
                wait = self._period - (now - oldest)
                if wait > 0:
                    time.sleep(wait)
                now = time.monotonic()
                cutoff = now - self._period
                self._timestamps = [t for t in self._timestamps if t > cutoff]

            self._timestamps.append(time.monotonic())

    def __call__(self) -> None:
        self.acquire()
