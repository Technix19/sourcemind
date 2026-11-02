"""Environment-based configuration, read once at startup.

Only non-secret settings live here for M1. Secrets (API keys, etc.) are added
in later milestones and must only ever come from the environment, never code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_env: str
    frontend_origin: str


def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"),
    )
