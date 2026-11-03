"""Authentication: verify Supabase access tokens locally, before any work is done.

How it works (see docs/m6b-design.md):
  * Supabase signs tokens with an asymmetric key (ES256) and publishes the PUBLIC
    key. We verify offline: no secret, and no call to Supabase per request.
  * Verification runs in a gate in FRONT of routing (`AuthGate`), because a plain
    FastAPI dependency would let the server read a whole upload before rejecting
    an unauthenticated caller (measured: 8 of 8 MB read vs 0).
  * `current_user` only reads the gate's result and also fails closed.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

import httpx
import jwt
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from .config import get_settings

logger = logging.getLogger("sourcemind.auth")

ALGORITHM = "ES256"          # the only algorithm accepted; never taken from the token
AUDIENCE = "authenticated"
PROTECTED_PREFIX = "/api/v1/"
PUBLIC_PATHS = frozenset({"/api/v1/health"})  # everything else under /api/v1/ needs a user


@dataclass(frozen=True)
class AuthUser:
    id: str
    token: str = field(repr=False)  # forwarded to the database so Row Level Security applies


class AuthError(Exception):
    """The token is missing, malformed, expired, or otherwise not acceptable."""


class AuthUnavailable(Exception):
    """We could not obtain the keys needed to decide (network problem)."""


class TokenVerifier:
    def __init__(
        self,
        *,
        issuer: str,
        jwks_url: str | None = None,
        fetch_keys: Callable[[], dict] | None = None,
        now: Callable[[], float] = time.time,
        leeway: int = 10,
        cache_seconds: int = 600,
        min_refetch_seconds: int = 30,
    ) -> None:
        if not (jwks_url or fetch_keys):
            raise ValueError("need jwks_url or fetch_keys")
        self._issuer = issuer
        self._fetch = fetch_keys or (lambda: _download_jwks(jwks_url))  # type: ignore[arg-type]
        self._now = now
        self._leeway = leeway
        self._cache_seconds = cache_seconds
        self._min_refetch = min_refetch_seconds
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at: float | None = None
        self._lock = threading.Lock()

    # -- keys ---------------------------------------------------------------
    def _refresh(self) -> None:
        try:
            data = self._fetch()
        except Exception:
            raise AuthUnavailable("could not fetch signing keys") from None
        keys: dict[str, jwt.PyJWK] = {}
        for jwk in data.get("keys", []):
            if jwk.get("kty") == "EC" and jwk.get("kid"):
                keys[jwk["kid"]] = jwt.PyJWK.from_dict(jwk, algorithm=ALGORITHM)
        self._keys = keys
        self._fetched_at = self._now()

    def _key_for(self, kid: str) -> jwt.PyJWK:
        with self._lock:
            age = None if self._fetched_at is None else self._now() - self._fetched_at
            if age is None or age >= self._cache_seconds:
                self._refresh()           # first use, or the cache has aged out (rotation/revocation)
            elif kid not in self._keys and age >= self._min_refetch:
                self._refresh()           # unknown key id: maybe rotated; at most once per interval
            key = self._keys.get(kid)
        if key is None:
            raise AuthError("unknown signing key")
        return key

    # -- tokens -------------------------------------------------------------
    def verify(self, token: str) -> AuthUser:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            raise AuthError("malformed token") from None
        if header.get("alg") != ALGORITHM:           # blocks "none" and HS256-with-public-key tricks
            raise AuthError("unexpected algorithm")
        kid = header.get("kid")
        if not isinstance(kid, str):
            raise AuthError("missing key id")
        key = self._key_for(kid)
        try:
            claims = jwt.decode(
                token,
                key.key,
                algorithms=[ALGORITHM],
                audience=AUDIENCE,
                issuer=self._issuer,
                leeway=self._leeway,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthError(type(exc).__name__) from None
        if claims.get("role") != "authenticated":    # the public anon key is a token too; refuse it
            raise AuthError("wrong role")
        if claims.get("is_anonymous") is True:
            raise AuthError("anonymous users are not accepted")
        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub:
            raise AuthError("missing subject")
        return AuthUser(id=sub, token=token)


def _download_jwks(url: str) -> dict:
    response = httpx.get(url, timeout=5)
    response.raise_for_status()
    return response.json()


_verifier: TokenVerifier | None = None
_verifier_lock = threading.Lock()


def get_verifier() -> TokenVerifier:
    """Process-wide verifier (it only holds PUBLIC keys). Tests replace this function."""
    global _verifier
    with _verifier_lock:
        if _verifier is None:
            base = get_settings().supabase_url
            _verifier = TokenVerifier(
                issuer=f"{base}/auth/v1", jwks_url=f"{base}/auth/v1/.well-known/jwks.json"
            )
        return _verifier


def _unauthorized(detail: str = "Not authenticated", status: int = 401) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else {}
    return JSONResponse({"detail": detail}, status_code=status, headers=headers)


class AuthGate(BaseHTTPMiddleware):
    """Reject unauthenticated calls to protected routes before routing and body parsing."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith(PROTECTED_PREFIX) or path in PUBLIC_PATHS:
            return await call_next(request)
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return _unauthorized()
        try:
            user = await run_in_threadpool(get_verifier().verify, token.strip())
        except AuthError as exc:
            logger.info("rejected token: %s", exc)       # reason only, never the token
            return _unauthorized()
        except AuthUnavailable:
            logger.warning("signing keys unavailable")
            return _unauthorized("Authentication is temporarily unavailable.", status=503)
        request.state.user = user
        return await call_next(request)


def current_user(request: Request) -> AuthUser:
    user = getattr(request.state, "user", None)
    if user is None:  # the gate did not run: fail closed rather than serve anonymously
        raise HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    return user
