"""Token verification, offline. A throw-away ES256 key pair lets us mint ANY token we like,
including the malicious ones a real attacker would try."""
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.auth import AuthError, AuthUnavailable, TokenVerifier

ISSUER = "https://proj.example/auth/v1"
SUB = "00000000-0000-0000-0000-000000000001"
def now() -> int:
    """PyJWT checks `exp` against the REAL clock, so tests must read it when they RUN, not at import:
    a slow test ahead of them in the suite would otherwise push 'a few seconds ago' far into the past."""
    return int(time.time())


NOW = now()  # only used to seed the fake key-cache clock, which has nothing to do with token expiry


def make_key(kid: str):
    private = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private.public_key()))
    jwk.update(kid=kid, alg="ES256", use="sig")
    return private, jwk


class Clock:
    def __init__(self, t=float(NOW)):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def env():
    private, jwk = make_key("k1")
    clock = Clock()
    fetches = []

    def fetch():
        fetches.append(1)
        return {"keys": [jwk]}

    verifier = TokenVerifier(issuer=ISSUER, fetch_keys=fetch, now=clock)

    def mint(key=private, kid="k1", alg="ES256", **claims):
        payload = {
            "iss": ISSUER, "aud": "authenticated", "role": "authenticated", "sub": SUB,
            "iat": now(), "exp": now() + 3600,
        }
        payload.update(claims)
        payload = {k: v for k, v in payload.items() if v is not None}  # None removes a claim
        return jwt.encode(payload, key, algorithm=alg, headers={"kid": kid} if kid else {})

    return type("Env", (), {"verifier": verifier, "mint": staticmethod(mint), "clock": clock, "fetches": fetches, "private": private})


def test_a_valid_token_is_accepted(env):
    user = env.verifier.verify(env.mint())
    assert user.id == SUB and user.token


def test_the_token_is_never_shown_in_the_user_repr(env):
    token = env.mint()
    assert token not in repr(env.verifier.verify(token))


@pytest.mark.parametrize(
    "claims",
    [
        {"exp": now() - 3600},                           # expired
        {"iss": "https://evil.example/auth/v1"},         # wrong issuer
        {"aud": "something-else"},                       # wrong audience
        {"role": "anon"},                                # the public key is a token too
        {"role": "service_role"},
        {"sub": None},                                   # no subject
        {"exp": None},                                   # never expires
        {"is_anonymous": True},                          # anonymous sign-in user
    ],
    ids=["expired", "issuer", "audience", "anon-role", "service-role", "no-sub", "no-exp", "anonymous-user"],
)
def test_bad_claims_are_rejected(env, claims):
    with pytest.raises(AuthError):
        env.verifier.verify(env.mint(**claims))


def test_expiry_allows_only_a_few_seconds_of_clock_skew(env):
    just_expired = env.mint(exp=now() - 5)                  # inside the 10 s leeway
    env.verifier.verify(just_expired)
    with pytest.raises(AuthError):
        env.verifier.verify(env.mint(exp=now() - 60))


def test_unsigned_none_algorithm_token_is_rejected(env):
    token = jwt.encode({"iss": ISSUER, "aud": "authenticated", "sub": SUB, "role": "authenticated", "exp": now() + 3600}, None, algorithm="none")
    with pytest.raises(AuthError, match="algorithm"):
        env.verifier.verify(token)


def test_hs256_token_is_rejected_even_with_a_valid_looking_header(env):
    token = env.mint(key="shared-secret-attackers-guess", alg="HS256")
    with pytest.raises(AuthError, match="algorithm"):
        env.verifier.verify(token)


def test_token_signed_by_a_different_key_with_the_same_kid_is_rejected(env):
    attacker, _ = make_key("k1")
    with pytest.raises(AuthError):
        env.verifier.verify(env.mint(key=attacker))


def test_tampered_payload_or_signature_is_rejected(env):
    head, body, sig = env.mint().split(".")
    forged_body = env.mint(sub="00000000-0000-0000-0000-0000000000ff").split(".")[1]
    for bad in (f"{head}.{forged_body}.{sig}", f"{head}.{body}.{sig[:-4]}AAAA"):
        with pytest.raises(AuthError):
            env.verifier.verify(bad)


@pytest.mark.parametrize("junk", ["", "abc", "a.b.c", "Bearer x", "....", "é.é.é"])
def test_malformed_tokens_are_rejected_not_crashed_on(env, junk):
    with pytest.raises(AuthError):
        env.verifier.verify(junk)


def test_missing_key_id_is_rejected(env):
    with pytest.raises(AuthError, match="key id"):
        env.verifier.verify(env.mint(kid=None))


def test_keys_are_cached_between_requests(env):
    for _ in range(5):
        env.verifier.verify(env.mint())
    assert len(env.fetches) == 1


def test_unknown_key_id_does_not_cause_a_refetch_storm(env):
    other, _ = make_key("not-published")
    env.verifier.verify(env.mint())                       # first use fetches once
    for _ in range(10):
        with pytest.raises(AuthError):
            env.verifier.verify(env.mint(key=other, kid="not-published"))
    assert len(env.fetches) == 1                           # attackers cannot make us hammer the key server
    env.clock.t += 31                                      # after the minimum interval one retry is allowed
    with pytest.raises(AuthError):
        env.verifier.verify(env.mint(key=other, kid="not-published"))
    assert len(env.fetches) == 2


def test_key_rotation_is_picked_up(env):
    new_private, new_jwk = make_key("k2")
    published = {"keys": [env.verifier._fetch()["keys"][0]]}
    env.verifier._fetch = lambda: published
    env.verifier.verify(env.mint())
    with pytest.raises(AuthError):
        env.verifier.verify(env.mint(key=new_private, kid="k2"))   # not published yet
    published["keys"].append(new_jwk)                               # the project rotates
    env.clock.t += 31
    assert env.verifier.verify(env.mint(key=new_private, kid="k2")).id == SUB


def test_cache_expires_so_revoked_keys_stop_working(env):
    env.verifier.verify(env.mint())
    env.clock.t += 601
    env.verifier.verify(env.mint())
    assert len(env.fetches) == 2


def test_key_server_outage_is_reported_as_unavailable_not_as_a_bad_token():
    def down():
        raise ConnectionError("no network")

    verifier = TokenVerifier(issuer=ISSUER, fetch_keys=down)
    private, _ = make_key("k1")
    token = jwt.encode({"iss": ISSUER, "aud": "authenticated", "sub": SUB, "role": "authenticated", "exp": now() + 3600}, private, algorithm="ES256", headers={"kid": "k1"})
    with pytest.raises(AuthUnavailable):
        verifier.verify(token)
