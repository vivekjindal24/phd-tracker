"""A general request limit in front of every route (SECURITY.md §6): per signed-in user, or
per client address for requests without a valid token. It blunts scripted abuse — scraping,
guessing across many accounts, floods — on top of the per-email login throttle; ordinary use
never comes near it. The client address is the one Caddy hands on (deploy/Caddyfile)."""

import hashlib
import math
import time
from collections import Counter

from starlette.requests import Request
from starlette.responses import Response

from app.auth.service import REFRESH_COOKIE, decode_access_token
from app.errors import ApiError, envelope

WINDOW_S = 60
PER_USER = 600  # a page fans out to ~10 calls; an export makes a few more through /internal
PER_ADDRESS = 300  # a whole campus can share one address, so this stays generous
EXEMPT = {"/api/v1/healthz"}
REFRESH_PATH = "/api/v1/auth/refresh"

# ponytail: counts live in this process (the API runs one replica, Dockerfile); move them to
# Postgres or Redis if the API ever runs several.
_counts: Counter[str] = Counter()
_window = 0


def reset() -> None:
    """Tests start each case with fresh counts."""
    _counts.clear()


def _key(request: Request) -> tuple[str, int]:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and token:
        try:
            return f"user:{decode_access_token(token)}", PER_USER
        except ApiError:
            pass  # an expired token is counted by address; the route answers 401 as usual
    # Each full page load renews the session before the user's token is known: counted per
    # session, so a campus behind one address does not share one count for it.
    # ponytail: an invented cookie gets a count of its own, but buys only a failed lookup here.
    if request.url.path == REFRESH_PATH and (cookie := request.cookies.get(REFRESH_COOKIE)):
        return f"session:{hashlib.sha256(cookie.encode()).hexdigest()[:32]}", PER_USER
    return f"addr:{request.client.host if request.client else 'unknown'}", PER_ADDRESS


async def limit(request: Request, call_next) -> Response:
    global _window
    if request.url.path in EXEMPT or request.method == "OPTIONS":
        return await call_next(request)
    now = time.time()
    if (window := int(now // WINDOW_S)) != _window:
        _window = window
        _counts.clear()
    key, allowed = _key(request)
    _counts[key] += 1
    if _counts[key] > allowed:
        response = envelope(
            429, "rate_limited", "Too many requests in a short time. Please wait a minute."
        )
        response.headers["Retry-After"] = str(math.ceil((window + 1) * WINDOW_S - now))
        return response
    return await call_next(request)
