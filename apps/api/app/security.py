"""Response hardening for the API (M7c).

The API only returns JSON and file redirects, never HTML, so its Content-Security-Policy can be
as strict as possible: nothing may load or run from an API response. These headers are defense in
depth; they do not replace authentication.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware

API_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-site",
}
# The interactive docs page loads its own scripts, so a strict policy would break it. It only
# exists locally (see docs_settings), never in a deployment.
DOCS_PATHS = frozenset({"/api/docs", "/openapi.json"})


def docs_settings(app_env: str) -> dict:
    """Interactive docs and the OpenAPI schema describe every route; offer them only locally."""
    if app_env.strip().lower() == "local":
        return {"docs_url": "/api/docs", "openapi_url": "/openapi.json"}
    return {"docs_url": None, "redoc_url": None, "openapi_url": None}


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path not in DOCS_PATHS:
            for name, value in API_HEADERS.items():
                response.headers.setdefault(name, value)
        return response
