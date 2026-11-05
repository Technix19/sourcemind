"""Per-user rate limits and a daily cap on paid model calls (M7c).

Why: every signed-in user can trigger CPU-heavy work (PDF parsing, embedding) and, when generation
is on, paid model calls. Limits keep one account, or a leaked token, from exhausting the server or
the bill. They are applied only after the token is verified, so they are keyed by the verified
user id and cannot be dodged by changing an IP address. Unauthenticated floods are rejected by the
auth gate before any expensive work.

Known limits (also in the README):
  * Counters live in this process's memory. They reset on restart, and N server instances would
    allow N times the limit. Fine for one small host; use a shared store before scaling out.
  * It is a sliding window of recent events, not a billing system. The daily generation cap counts
    attempts, including failed model calls, because those can cost money too.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .config import get_settings

logger = logging.getLogger("sourcemind")

MAX_TRACKED_KEYS = 10_000  # memory bound: idle keys are swept before this is exceeded
DAY_SECONDS = 24 * 60 * 60


class RateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._events: dict[tuple[str, str], deque[float]] = {}
        self._windows: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()

    def hit(self, bucket: str, user_id: str, limit: int, window: float) -> float | None:
        """Record one event. Returns None if allowed, else the seconds until it would be allowed.
        A blocked attempt is not recorded, so retrying cannot extend the wait."""
        key, now = (bucket, user_id), self._clock()
        with self._lock:
            events = self._events.get(key)
            if events is None:
                if len(self._events) >= MAX_TRACKED_KEYS:
                    self._sweep(now)
                events = self._events[key] = deque()
            self._windows[key] = window
            while events and events[0] <= now - window:
                events.popleft()
            if len(events) >= limit:
                return max(events[0] + window - now, 1.0)
            events.append(now)
            return None

    def _sweep(self, now: float) -> None:
        for key in [k for k, e in self._events.items() if not e or e[-1] <= now - self._windows[k]]:
            del self._events[key]
            del self._windows[key]

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._windows.clear()


limiter = RateLimiter()


GLOBAL_KEY = "*"  # one shared counter for every user


def generation_allowed(user_id: str) -> bool:
    """Spend one daily model call, for this user and for the whole server. False when either allowance
    is used up. The user's own cap is checked first, so a user who is over it cannot burn shared slots.
    Without the server-wide ceiling, many accounts could each use their own allowance and the total
    spend would have no bound at all."""
    settings = get_settings()
    if limiter.hit("generation", user_id, settings.daily_generations, DAY_SECONDS) is not None:
        return False
    return limiter.hit("generation-global", GLOBAL_KEY, settings.global_daily_generations, DAY_SECONDS) is None


def _bucket_for(method: str, path: str) -> tuple[str, int, int]:
    """(bucket, limit, window seconds) for a protected request."""
    s = get_settings()
    if method == "POST" and path == "/api/v1/documents":
        return "uploads", s.rate_uploads_per_hour, 3600
    if method == "POST" and path == "/api/v1/queries":
        return "queries", s.rate_queries_per_minute, 60
    return "other", s.rate_other_per_minute, 60


class RateLimitGate(BaseHTTPMiddleware):
    """Must sit just inside AuthGate: it relies on the verified user, and runs before routing, so a
    rejected upload is refused before its body is read."""

    async def dispatch(self, request, call_next):
        user = getattr(request.state, "user", None)
        if user is None:  # public route (health) or unauthenticated: not this gate's job
            return await call_next(request)
        bucket, limit, window = _bucket_for(request.method, request.url.path)
        wait = limiter.hit(bucket, user.id, limit, window)
        if wait is None:
            return await call_next(request)
        logger.info("rate limited bucket=%s", bucket)  # never the user id or token
        seconds = int(wait) + (0 if wait == int(wait) else 1)
        return JSONResponse(
            {"detail": f"Too many requests. Try again in {seconds} seconds."},
            status_code=429, headers={"Retry-After": str(seconds)},
        )
