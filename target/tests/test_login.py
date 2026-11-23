"""The repo's own suite. Passes before the change and must keep passing after it."""

import pytest

from app import create_app


@pytest.fixture
def client():
    return create_app().test_client()


def test_health(client):
    assert client.get("/health").status_code == 200


def test_valid_credentials_succeed(client):
    r = client.post("/login", json={"username": "alice", "password": "correct-horse"})
    assert r.status_code == 200
    assert r.get_json()["user"] == "alice"


def test_invalid_password_rejected(client):
    r = client.post("/login", json={"username": "alice", "password": "wrong"})
    assert r.status_code == 401


def test_unknown_user_rejected(client):
    r = client.post("/login", json={"username": "nobody", "password": "x"})
    assert r.status_code == 401


def test_malformed_body_does_not_crash(client):
    assert client.post("/login", data="not json").status_code == 401
