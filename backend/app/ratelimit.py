"""
Per-IP request limits for the hosted demo.

Every endpoint is anonymous, and routing and search spend free third-party
quotas (ORS, LocationIQ) shared by all visitors, so one client must not be
able to drain them. Off in development.

Counts live in this process's memory: fine for one uvicorn worker, and they
reset on restart. The client address comes from X-Forwarded-For because the
app sits behind the host's proxy; a client calling the backend directly can
forge that header, which is an accepted gap for a demo.
"""
import math
import time
from collections import deque

from fastapi import Depends, HTTPException, Request

from app.config import Settings, get_settings

_WINDOW_S = 60.0
_MAX_KEYS = 20_000  # prune idle clients past this so the table can't grow forever

_hits: dict[tuple[str, str], deque[float]] = {}


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _prune(now: float) -> None:
    for key in [k for k, q in _hits.items() if not q or q[-1] <= now - _WINDOW_S]:
        del _hits[key]


def rate_limit(bucket: str, setting: str):
    """Dependency allowing `settings.<setting>` requests a minute per client IP."""

    def dependency(request: Request, settings: Settings = Depends(get_settings)) -> None:
        if settings.environment == "development":
            return
        limit: int = getattr(settings, setting)
        now = time.monotonic()
        if len(_hits) > _MAX_KEYS:
            _prune(now)

        q = _hits.setdefault((bucket, client_ip(request)), deque())
        while q and q[0] <= now - _WINDOW_S:
            q.popleft()
        if len(q) >= limit:
            retry_after = max(1, math.ceil(q[0] + _WINDOW_S - now))
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Wait a minute and try again.",
                headers={"Retry-After": str(retry_after)},
            )
        q.append(now)

    return dependency
