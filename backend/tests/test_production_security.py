import pytest
from pydantic import ValidationError

from app.database import Settings, SessionLocal, settings
from app.services.wallet_service import (
    PaymentError,
    demo_fund_wallet,
)


def make_settings(**overrides):
    values = {
        "DATABASE_URL": "postgresql+psycopg://test:test@localhost/test",
        "JWT_SECRET_KEY": "A" * 48,
        "APP_ENV": "production",
        "DEMO_POS_ENABLED": False,
        "RATE_LIMIT_ENABLED": True,
        "REDIS_URL": "redis://127.0.0.1:6380/0",
        "_env_file": None,
    }

    values.update(overrides)
    return Settings(**values)


def test_production_rejects_demo_pos():
    with pytest.raises(
        ValidationError,
        match="Demo POS cannot be enabled",
    ):
        make_settings(DEMO_POS_ENABLED=True)


def test_production_rejects_short_jwt_secret():
    with pytest.raises(
        ValidationError,
        match="Production JWT secret",
    ):
        make_settings(JWT_SECRET_KEY="short")


def test_valid_production_config_disables_demo_pos():
    config = make_settings()

    assert config.APP_ENV == "production"
    assert config.DEMO_POS_ENABLED is False


def test_demo_funding_rejected_in_production(monkeypatch):
    monkeypatch.setattr(
        settings,
        "APP_ENV",
        "production",
    )

    with SessionLocal() as db:
        with pytest.raises(
            PaymentError,
            match="Demo funding is disabled in production",
        ):
            demo_fund_wallet(
                db=db,
                wallet_id=1,
                admin_id=1,
                amount=10000,
                key="production-funding-must-fail",
            )
