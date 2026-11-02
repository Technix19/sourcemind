"""SourceMind API. M1: application skeleton and health check only."""
from fastapi import FastAPI

from .config import get_settings

API_VERSION = "0.1.0"

app = FastAPI(title="SourceMind API", version=API_VERSION, docs_url="/api/docs")


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    """Readiness probe. Must never expose secrets or sensitive config."""
    return {
        "status": "ok",
        "version": API_VERSION,
        "environment": get_settings().app_env,
    }
