import time
from threading import Lock


class InMemoryRateLimiter:
    """Sliding-window limiter keyed by client id (typically IP)."""

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def allow(self, key: str, limit: int, window_seconds: float = 60.0) -> bool:
        if limit <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            stamps = [stamp for stamp in self._hits.get(key, []) if now - stamp < window_seconds]
            if len(stamps) >= limit:
                self._hits[key] = stamps
                return False
            stamps.append(now)
            self._hits[key] = stamps
            return True
