"""Per-user rate limits and the daily generation cap. Fake clock and fake model: no waiting, no cost."""
import pytest
from fastapi.testclient import TestClient

from app import limits
from app.config import get_settings
from app.limits import DAY_SECONDS, MAX_TRACKED_KEYS, RateLimiter
from app.main import app
from conftest import AUTH_A, AUTH_B

alice = TestClient(app, headers=AUTH_A)
bob = TestClient(app, headers=AUTH_B)
TEXT = b"The Random Forest classifier selects question difficulty."


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


# ---- the limiter itself -------------------------------------------------------------------

def test_allows_up_to_the_limit_then_blocks_with_a_wait():
    clock = Clock()
    rl = RateLimiter(clock)
    assert [rl.hit("b", "u", 3, 60) for _ in range(3)] == [None, None, None]
    assert rl.hit("b", "u", 3, 60) == 60.0
    clock.now += 45
    assert rl.hit("b", "u", 3, 60) == 15.0   # the oldest event leaves the window in 15 s


def test_window_slides_instead_of_resetting_all_at_once():
    clock = Clock()
    rl = RateLimiter(clock)
    rl.hit("b", "u", 2, 60)
    clock.now += 30
    rl.hit("b", "u", 2, 60)
    clock.now += 31                           # first event expired, second has not
    assert rl.hit("b", "u", 2, 60) is None
    assert rl.hit("b", "u", 2, 60) is not None


def test_blocked_attempts_do_not_extend_the_wait():
    clock = Clock()
    rl = RateLimiter(clock)
    rl.hit("b", "u", 1, 60)                  # t = 0, allowed
    for _ in range(5):
        clock.now += 10
        assert rl.hit("b", "u", 1, 60) is not None   # t = 10..50, refused and NOT recorded
    clock.now += 10                           # t = 60: the only recorded event has just expired
    assert rl.hit("b", "u", 1, 60) is None


def test_users_and_buckets_are_independent():
    rl = RateLimiter(Clock())
    assert rl.hit("queries", "a", 1, 60) is None
    assert rl.hit("queries", "a", 1, 60) is not None
    assert rl.hit("queries", "b", 1, 60) is None
    assert rl.hit("uploads", "a", 1, 60) is None


def test_memory_is_bounded_by_sweeping_idle_users():
    clock = Clock()
    rl = RateLimiter(clock)
    for i in range(MAX_TRACKED_KEYS):
        rl.hit("b", f"user-{i}", 5, 60)
    clock.now += 61                            # all of them are idle now
    rl.hit("b", "newcomer", 5, 60)
    assert len(rl._events) == 1


# ---- configuration ------------------------------------------------------------------------

@pytest.mark.parametrize("value", ["0", "-5", "abc", ""])
def test_a_bad_setting_falls_back_to_the_default_never_to_unlimited(monkeypatch, value):
    monkeypatch.setenv("RATE_QUERIES_PER_MINUTE", value)
    monkeypatch.setenv("DAILY_GENERATIONS", value)
    s = get_settings()
    assert s.rate_queries_per_minute == 30 and s.daily_generations == 20


# ---- through the API ----------------------------------------------------------------------

def ask(c=alice):
    return c.post("/api/v1/queries", json={"question": "Which classifier selects difficulty?"})


def test_queries_are_limited_per_user_with_retry_after(monkeypatch):
    monkeypatch.setenv("RATE_QUERIES_PER_MINUTE", "3")
    alice.post("/api/v1/documents", files={"file": ("a.txt", TEXT, "text/plain")})
    codes = [ask().status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    blocked = ask()
    assert 1 <= int(blocked.headers["Retry-After"]) <= 60
    assert "Too many requests" in blocked.json()["detail"]
    assert "Content-Security-Policy" in blocked.headers          # even refusals are hardened
    assert ask(bob).status_code != 429                            # another user is unaffected


def test_an_upload_over_the_limit_is_refused_before_its_body_is_parsed(monkeypatch):
    monkeypatch.setenv("RATE_UPLOADS_PER_HOUR", "1")
    first = alice.post("/api/v1/documents", files={"file": ("a.txt", TEXT, "text/plain")})
    assert first.status_code == 201
    parsed = []
    monkeypatch.setattr("app.main._process", lambda *a: parsed.append(a))
    blocked = alice.post("/api/v1/documents", files={"file": ("b.txt", TEXT, "text/plain")})
    assert blocked.status_code == 429 and parsed == []


def test_other_routes_have_their_own_generous_bucket(monkeypatch):
    monkeypatch.setenv("RATE_OTHER_PER_MINUTE", "2")
    assert [alice.get("/api/v1/documents").status_code for _ in range(3)] == [200, 200, 429]


def test_health_and_unauthenticated_calls_never_spend_anyones_allowance(monkeypatch):
    monkeypatch.setenv("RATE_OTHER_PER_MINUTE", "1")
    anonymous = TestClient(app)
    for _ in range(5):
        assert anonymous.get("/api/v1/health").status_code == 200
        assert anonymous.get("/api/v1/documents").status_code == 401
    assert alice.get("/api/v1/documents").status_code == 200


# ---- daily generation cap -----------------------------------------------------------------

class FakeLLM:
    model = "test-model"

    def __init__(self, error: Exception | None = None):
        self.calls, self.error = 0, error

    def complete(self, system, user):
        self.calls += 1
        if self.error:
            raise self.error
        return "A Random Forest classifier does this [1]."


def install(monkeypatch, llm):
    monkeypatch.setattr("app.main.get_llm_client", lambda: llm)
    alice.post("/api/v1/documents", files={"file": ("a.txt", TEXT, "text/plain")})


def generate(c=alice):
    return c.post("/api/v1/queries", json={"question": "Which classifier selects difficulty?", "mode": "generated"}).json()


def test_daily_cap_stops_model_calls_but_still_returns_evidence(monkeypatch):
    monkeypatch.setenv("DAILY_GENERATIONS", "2")
    llm = FakeLLM()
    install(monkeypatch, llm)
    modes = [generate()["answer_mode"] for _ in range(4)]
    assert modes == ["generated", "generated", "sources_only", "sources_only"]
    assert llm.calls == 2                                          # the paid call is never made
    capped = generate()
    assert capped["evidence"] and "today's allowance" in capped["notice"]


def test_the_daily_cap_is_per_user(monkeypatch):
    monkeypatch.setenv("DAILY_GENERATIONS", "1")
    llm = FakeLLM()
    install(monkeypatch, llm)
    bob.post("/api/v1/documents", files={"file": ("a.txt", TEXT, "text/plain")})
    assert generate()["answer_mode"] == "generated"
    assert generate()["answer_mode"] == "sources_only"
    assert generate(bob)["answer_mode"] == "generated"


def test_failed_model_calls_still_count_because_they_can_cost_money(monkeypatch):
    monkeypatch.setenv("DAILY_GENERATIONS", "2")
    llm = FakeLLM(error=RuntimeError("boom"))
    install(monkeypatch, llm)
    for _ in range(4):
        generate()
    assert llm.calls == 2


def test_sources_only_and_no_evidence_questions_spend_no_allowance(monkeypatch):
    monkeypatch.setenv("DAILY_GENERATIONS", "1")
    llm = FakeLLM()
    install(monkeypatch, llm)
    for _ in range(3):
        alice.post("/api/v1/queries", json={"question": "Which classifier selects difficulty?"})
    alice.post("/api/v1/queries", json={"question": "galaxies and nebulae", "mode": "generated"})
    assert generate()["answer_mode"] == "generated"                # the one allowed call is still available


def test_the_allowance_returns_after_a_day(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(limits, "limiter", RateLimiter(clock))
    monkeypatch.setenv("DAILY_GENERATIONS", "1")
    install(monkeypatch, FakeLLM())
    assert generate()["answer_mode"] == "generated"
    assert generate()["answer_mode"] == "sources_only"
    clock.now += DAY_SECONDS + 1
    assert generate()["answer_mode"] == "generated"


# ---- server-wide ceiling ------------------------------------------------------------------

def test_a_server_wide_ceiling_stops_generation_for_everyone(monkeypatch):
    monkeypatch.setenv("DAILY_GENERATIONS", "10")
    monkeypatch.setenv("GLOBAL_DAILY_GENERATIONS", "3")
    llm = FakeLLM()
    install(monkeypatch, llm)
    bob.post("/api/v1/documents", files={"file": ("a.txt", TEXT, "text/plain")})
    modes = [generate()["answer_mode"], generate(bob)["answer_mode"], generate()["answer_mode"],   # 3 allowed in total
             generate(bob)["answer_mode"], generate()["answer_mode"]]
    assert modes == ["generated", "generated", "generated", "sources_only", "sources_only"]
    assert llm.calls == 3
    assert generate(bob)["evidence"]                                  # still useful: evidence is returned


def test_a_user_over_their_own_cap_does_not_use_up_shared_slots(monkeypatch):
    monkeypatch.setenv("DAILY_GENERATIONS", "1")
    monkeypatch.setenv("GLOBAL_DAILY_GENERATIONS", "2")
    llm = FakeLLM()
    install(monkeypatch, llm)
    bob.post("/api/v1/documents", files={"file": ("a.txt", TEXT, "text/plain")})
    assert generate()["answer_mode"] == "generated"                   # alice: 1 of her 1, 1 of 2 shared
    for _ in range(5):
        assert generate()["answer_mode"] == "sources_only"            # over her cap: must not touch the shared count
    assert generate(bob)["answer_mode"] == "generated"                # the second shared slot is still there


def test_the_global_ceiling_has_a_safe_default_and_rejects_bad_values(monkeypatch):
    monkeypatch.delenv("GLOBAL_DAILY_GENERATIONS", raising=False)
    assert get_settings().global_daily_generations == 200
    for bad in ("0", "-1", "x"):
        monkeypatch.setenv("GLOBAL_DAILY_GENERATIONS", bad)
        assert get_settings().global_daily_generations == 200
