import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.database import settings
from app.main import app
from app.core import rate_limiter


@pytest.fixture
def limited_client(monkeypatch):
    monkeypatch.setattr(
        settings, "RATE_LIMIT_ENABLED", True
    )
    monkeypatch.setattr(
        settings,
        "RATE_LIMIT_PREFIX",
        f"smartspend:test:{uuid4().hex}",
    )

    with TestClient(app) as client:
        yield client


def test_login_rate_limit(limited_client, monkeypatch):
    monkeypatch.setitem(
        rate_limiter.LIMITS, "login", (2, 60)
    )

    payload = {
        "username": "missing-user@example.test",
        "password": "incorrect-test-password",
    }

    first = limited_client.post(
        "/auth/login", data=payload
    )
    second = limited_client.post(
        "/auth/login", data=payload
    )
    third = limited_client.post(
        "/auth/login", data=payload
    )

    assert first.status_code == 401
    assert second.status_code == 401
    assert third.status_code == 429
    assert int(third.headers["retry-after"]) > 0


def test_pos_rate_limit(limited_client, monkeypatch):
    monkeypatch.setitem(
        rate_limiter.LIMITS, "pos_ip", (2, 60)
    )

    for _ in range(2):
        response = limited_client.post(
            "/pos/purchases",
            json={},
        )
        assert response.status_code == 401

    blocked = limited_client.post(
        "/pos/purchases",
        json={},
    )

    assert blocked.status_code == 429


def test_terminal_admin_rate_limit(
    limited_client, monkeypatch
):
    monkeypatch.setitem(
        rate_limiter.LIMITS, "terminal_admin", (2, 60)
    )

    for _ in range(2):
        response = limited_client.post(
            "/admin/terminals/1/revoke"
        )
        assert response.status_code == 401

    blocked = limited_client.post(
        "/admin/terminals/1/revoke"
    )

    assert blocked.status_code == 429


def test_rate_limit_recovers_after_expiration(
    limited_client, monkeypatch
):
    monkeypatch.setitem(
        rate_limiter.LIMITS, "login", (1, 1)
    )

    payload = {
        "username": "missing-user@example.test",
        "password": "incorrect-test-password",
    }

    first = limited_client.post(
        "/auth/login", data=payload
    )

    blocked = limited_client.post(
        "/auth/login", data=payload
    )

    assert first.status_code == 401
    assert blocked.status_code == 429

    time.sleep(1.2)

    recovered = limited_client.post(
        "/auth/login", data=payload
    )

    assert recovered.status_code == 401


def test_redis_failure_blocks_protected_requests(
    limited_client, monkeypatch
):
    monkeypatch.setattr(
        settings,
        "REDIS_URL",
        "redis://127.0.0.1:1/0",
    )

    response = limited_client.post(
        "/auth/login",
        data={
            "username": "missing-user@example.test",
            "password": "incorrect-test-password",
        },
    )

    assert response.status_code == 503



# ============================================================
# PHASE 16D: POS RATE LIMIT ISOLATION
# ============================================================


def test_terminal_specific_rate_limit(
    limited_client,
    monkeypatch,
):
    # Use a generous IP limit so only the terminal
    # limit controls this test.
    monkeypatch.setitem(
        rate_limiter.LIMITS,
        "pos_ip",
        (100, 60),
    )

    monkeypatch.setitem(
        rate_limiter.LIMITS,
        "pos_terminal",
        (2, 60),
    )

    terminal_one = "900001." + ("A" * 43)
    terminal_two = "900002." + ("B" * 43)

    for _ in range(2):
        response = limited_client.post(
            "/pos/purchases",
            headers={
                "X-Terminal-Key": terminal_one
            },
            json={},
        )

        assert response.status_code == 401

    blocked = limited_client.post(
        "/pos/purchases",
        headers={
            "X-Terminal-Key": terminal_one
        },
        json={},
    )

    assert blocked.status_code == 429

    # A different terminal identifier must have
    # its own counter.
    independent = limited_client.post(
        "/pos/purchases",
        headers={
            "X-Terminal-Key": terminal_two
        },
        json={},
    )

    assert independent.status_code == 401


def test_malformed_terminal_key_cannot_bypass_ip_limit(
    limited_client,
    monkeypatch,
):
    monkeypatch.setitem(
        rate_limiter.LIMITS,
        "pos_ip",
        (2, 60),
    )

    malformed_keys = [
        "invalid-key-one",
        "invalid-key-two",
        "invalid-key-three",
    ]

    statuses = []

    for key in malformed_keys:
        response = limited_client.post(
            "/pos/purchases",
            headers={
                "X-Terminal-Key": key
            },
            json={},
        )

        statuses.append(response.status_code)

    assert statuses == [401, 401, 429]
