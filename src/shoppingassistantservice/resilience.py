import threading
import time
from collections import deque

from metrics import CIRCUIT_BREAKER_STATE


class RateLimiter:
    def __init__(self, window_seconds: int, max_requests: int):
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self.events: dict[str, deque[float]] = {}
        self._last_eviction = 0.0
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self.lock:
            self._evict_expired_keys(now)
            queue = self.events.setdefault(key, deque())
            while queue and now - queue[0] > self.window_seconds:
                queue.popleft()
            if len(queue) >= self.max_requests:
                return False
            queue.append(now)
            return True

    def _evict_expired_keys(self, now: float) -> None:
        """Drop keys whose deques are empty or fully expired.

        Without this, keys for one-off callers stay in the map forever and the
        events dict grows without bound. Sweeps run at most once per window.
        """
        if now - self._last_eviction < self.window_seconds:
            return
        self._last_eviction = now
        expired = [
            key
            for key, queue in self.events.items()
            if not queue or now - queue[0] > self.window_seconds
        ]
        for key in expired:
            del self.events[key]


class CircuitBreaker:
    def __init__(self, failure_threshold: int, reset_seconds: int):
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self.failure_count = 0
        self.open_until = 0.0
        self.lock = threading.Lock()

    def can_call(self) -> bool:
        with self.lock:
            return time.time() >= self.open_until

    def mark_success(self) -> None:
        with self.lock:
            self.failure_count = 0
            self.open_until = 0.0
            CIRCUIT_BREAKER_STATE.set(0)

    def mark_failure(self) -> None:
        with self.lock:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.open_until = time.time() + self.reset_seconds
                CIRCUIT_BREAKER_STATE.set(1)
