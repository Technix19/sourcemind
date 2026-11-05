"""Helpers and fixtures for the Supabase integration tests (M6).

These talk to a REAL Supabase project over the public API, using real user
sessions. That matters: the SQL Editor and the service key bypass Row Level
Security, so only calls made like an ordinary signed-in user prove isolation.

Needs SUPABASE_URL and SUPABASE_ANON_KEY (the publishable key) in apps/api/.env.
The service-role key is never used here.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pytest
from dotenv import load_dotenv

# Explicit path: do not depend on dotenv's directory search from inside a test package.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _base_url(raw: str) -> str:
    """Keep only scheme + host, so pasting '.../rest/v1/' from the dashboard still works."""
    parsed = urlparse(raw.strip())
    return f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""


URL = _base_url(os.getenv("SUPABASE_URL", ""))
KEY = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_PUBLISHABLE_KEY", "")

skip_without_supabase = pytest.mark.skipif(
    not (URL and KEY), reason="SUPABASE_URL / SUPABASE_ANON_KEY not set"
)


@dataclass(frozen=True)
class User:
    id: str
    token: str


def rest(method: str, path: str, user: User | None = None, *, token: str | None = None, **kwargs) -> httpx.Response:
    """Call PostgREST. No user means an anonymous caller (public key only)."""
    headers = {"apikey": KEY, "Prefer": "return=representation"}
    bearer = token or (user.token if user else None)
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    return httpx.request(method, f"{URL}/rest/v1/{path}", headers=headers, timeout=20, **kwargs)


def sign_up() -> User:
    # Supabase rejects reserved domains such as example.com. No email is sent while
    # "Confirm email" is off, so the address only has to be well-formed. Override the
    # domain with SUPABASE_TEST_EMAIL_DOMAIN if your project restricts sign-ups.
    domain = os.getenv("SUPABASE_TEST_EMAIL_DOMAIN", "mailinator.com")
    email = f"sourcemind-test-{uuid.uuid4().hex[:12]}@{domain}"
    response = httpx.post(
        f"{URL}/auth/v1/signup",
        headers={"apikey": KEY},
        json={"email": email, "password": uuid.uuid4().hex + "Aa1!"},
        timeout=20,
    )
    body = response.json()
    if response.status_code >= 400 or "access_token" not in body:
        reason = body.get("msg") or body.get("message") or body.get("error_description") or ""
        code = body.get("error_code") or body.get("code") or ""
        pytest.fail(
            f"Sign-up failed (status {response.status_code}, code={code!r}, reason={reason!r}). "
            "If there is no error and no session, turn 'Confirm email' off in the DEV project's "
            "Authentication settings."
        )
    return User(id=body["user"]["id"], token=body["access_token"])


def sign_in(email: str, password: str) -> User:
    """Sign in to a pre-made, already-confirmed test account (see docs/m7c-test-accounts.md)."""
    response = httpx.post(
        f"{URL}/auth/v1/token", params={"grant_type": "password"}, headers={"apikey": KEY},
        json={"email": email, "password": password}, timeout=20,
    )
    body = response.json()
    if response.status_code >= 400 or "access_token" not in body:
        pytest.fail(f"Test account sign-in failed (status {response.status_code}). Check SUPABASE_TEST_USER_* in apps/api/.env "
                    "and that the address was confirmed.")
    return User(id=body["user"]["id"], token=body["access_token"])


def _test_user(which: str) -> User:
    """Fixed accounts when configured (needed once 'Confirm email' is on: throwaway sign-ups would get no
    session and would send real emails to made-up addresses). Otherwise a fresh throwaway account."""
    email, password = os.getenv(f"SUPABASE_TEST_USER_{which}_EMAIL", ""), os.getenv(f"SUPABASE_TEST_USER_{which}_PASSWORD", "")
    return sign_in(email, password) if email and password else sign_up()


@pytest.fixture(scope="module")
def user_a() -> User:
    return _test_user("A")


@pytest.fixture(scope="module")
def user_b() -> User:
    return _test_user("B")


DOC = {"name": "notes.pdf", "size_bytes": 1000, "page_count": 2}


def chunk_payload(document_id: str, **extra) -> dict:
    return {
        "document_id": document_id, "page_number": 1, "chunk_index": 0,
        "start_offset": 0, "end_offset": 5, "text": "hello", **extra,
    }


@pytest.fixture
def doc_a(user_a: User):
    """A document owned by user A, removed again afterwards."""
    created = rest("POST", "documents", user_a, json=DOC)
    assert created.status_code == 201, created.text
    doc = created.json()[0]
    yield doc
    rest("DELETE", f"documents?id=eq.{doc['id']}", user_a)
