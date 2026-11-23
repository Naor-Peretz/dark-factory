"""Acceptance oracle for spec/auth-rate-limit.md. One test per acceptance criterion.

The VERIFIER owns this file. The Builder has no access to it -- its cwd is the app
checkout and this directory is supplied to the Verifier alone via the adapter's add_dirs.
That is deliberate: a critic that reads the author's own tests is not an independent check.

Criterion 6 ("the suite passes from a clean checkout") is not here. The Verifier checks
it by running the repo's own `pytest` in the checkout.
"""

from __future__ import annotations

import time

import pytest

from app import create_app  # resolved against cwd by conftest.py

BAD = {"username": "alice", "password": "wrong"}
GOOD = {"username": "alice", "password": "correct-horse"}


def hammer(client, n, ip="10.0.0.1", payload=None):
    """Fire n requests from one IP and return the status codes."""
    return [
        client.post(
            "/login", json=payload or BAD, environ_base={"REMOTE_ADDR": ip}
        ).status_code
        for _ in range(n)
    ]


@pytest.fixture
def client():
    """Short window so the reset criterion is testable without waiting a minute."""
    return create_app(window_seconds=1, max_requests=10).test_client()


# --- criterion 1 ---
def test_eleventh_request_within_window_is_throttled(client):
    codes = hammer(client, 11)
    assert codes[10] == 429, f"11th request should be 429, got {codes[10]} (all: {codes})"


# --- criterion 2 ---
def test_tenth_request_still_returns_its_normal_status(client):
    codes = hammer(client, 10)
    assert 429 not in codes, f"no request within budget may be throttled: {codes}"
    assert codes[9] == 401, f"10th should still be the normal 401, got {codes[9]}"


# --- criterion 3 ---
def test_limiter_resets_after_the_window_elapses(client):
    hammer(client, 11)
    time.sleep(1.2)  # window_seconds=1
    after = client.post("/login", json=BAD, environ_base={"REMOTE_ADDR": "10.0.0.1"})
    assert after.status_code == 401, (
        f"budget should be restored after the window, got {after.status_code}"
    )


# --- criterion 4 ---
def test_throttled_response_carries_retry_after(client):
    hammer(client, 10)
    r = client.post("/login", json=BAD, environ_base={"REMOTE_ADDR": "10.0.0.1"})
    assert r.status_code == 429
    assert "Retry-After" in r.headers, f"429 must carry Retry-After; headers: {dict(r.headers)}"
    value = r.headers["Retry-After"]
    assert value.isdigit(), f"Retry-After should be whole seconds, got {value!r}"
    assert 0 < int(value) <= 1, f"Retry-After should be within the window, got {value}"


# --- criterion 5 ---
def test_two_ips_have_independent_budgets(client):
    first = hammer(client, 11, ip="10.0.0.1")
    assert first[10] == 429, "first IP should be throttled"
    second = hammer(client, 10, ip="10.0.0.2")
    assert 429 not in second, f"a second IP must have its own budget, got {second}"


# --- guard: the limiter must not break the happy path ---
def test_valid_credentials_still_work_within_budget(client):
    r = client.post("/login", json=GOOD, environ_base={"REMOTE_ADDR": "10.0.0.9"})
    assert r.status_code == 200, "rate limiting must not break valid logins"


def test_limiting_is_per_ip_not_global(client):
    """A global bucket would pass criterion 1 while violating the spec's constraint."""
    hammer(client, 11, ip="10.0.0.1")
    for ip in ("10.0.0.2", "10.0.0.3", "10.0.0.4"):
        codes = hammer(client, 1, ip=ip)
        assert codes[0] != 429, f"{ip} throttled by another IP's traffic -- shared bucket"


# --- added after the Gatekeeper's finding 3, 23 Nov ---------------------------
#
# The Gatekeeper blocked a 7/7 run and was right: every test above builds the app
# with window_seconds=1, so NOTHING here proved create_app's real defaults. The
# criteria are stated for the default configuration (10 requests / 60s), and the
# oracle never touched it. A gap in the checker, found by the critic.


def test_default_configuration_is_ten_requests_per_sixty_seconds():
    """Criteria 1 and 2 are stated for the DEFAULT config, not a 1s test window."""
    app = create_app()
    assert app.config["WINDOW_SECONDS"] == 60, "default window must be 60s"
    assert app.config["MAX_REQUESTS"] == 10, "default budget must be 10 requests"


def test_eleventh_request_is_throttled_under_the_real_defaults():
    """Exercise criterion 1 against create_app() with no arguments at all."""
    client = create_app().test_client()
    codes = hammer(client, 11, ip="10.9.9.1")
    assert 429 not in codes[:10], f"first 10 must not be throttled by default: {codes}"
    assert codes[10] == 429, f"11th must be 429 under defaults, got {codes[10]}"


def test_retry_after_is_plausible_under_the_real_defaults():
    client = create_app().test_client()
    hammer(client, 10, ip="10.9.9.2")
    r = client.post("/login", json=BAD, environ_base={"REMOTE_ADDR": "10.9.9.2"})
    assert r.status_code == 429
    value = r.headers.get("Retry-After", "")
    assert value.isdigit(), f"Retry-After must be whole seconds, got {value!r}"
    assert 0 < int(value) <= 60, f"must fall inside the 60s default window, got {value}"
