import pytest

from sqlalchemy import select, func

from pydantic import ValidationError

from app.database import SessionLocal
from app.models.transaction import Transaction
from app.models.wallet import Wallet
from app.schemas.pos import PurchaseCreate
from app.services.wallet_service import (
    PaymentError,
    process_scanned_card_purchase,
    process_canteen_purchase,
)


def financial_snapshot():
    """Read financial totals without modifying the database."""
    with SessionLocal() as db:
        transaction_count = db.scalar(
            select(func.count(Transaction.id))
        )

        wallet_total = db.scalar(
            select(func.coalesce(func.sum(Wallet.balance), 0))
        )

    return transaction_count, wallet_total


def test_legacy_pos_request_rejected():
    with pytest.raises(ValidationError):
        PurchaseCreate(
            wallet_id=1,
            student_id=1,
            card_id=2,
            amount=1000,
            idempotency_key="legacy-test-12345",
        )


def test_malformed_card_credential_rejected():
    with pytest.raises(ValidationError):
        PurchaseCreate(
            card_credential="INVALID-CARD",
            amount=1000,
            idempotency_key="malformed-test-12345",
        )


def test_zero_or_negative_purchase_rejected():
    credential = "SC1." + ("A" * 43)

    for amount in (0, -1000):
        with pytest.raises(ValidationError):
            PurchaseCreate(
                card_credential=credential,
                amount=amount,
                idempotency_key="amount-test-12345",
            )


def test_unknown_card_creates_no_transaction():
    before = financial_snapshot()

    unknown_credential = "SC1." + ("A" * 43)

    with SessionLocal() as db:
        with pytest.raises(PaymentError):
            process_scanned_card_purchase(
                db=db,
                card_credential=unknown_credential,
                terminal_id=1,
                attendant_id=1,
                amount=1000,
                key="unknown-card-test-12345",
            )

    after = financial_snapshot()

    assert after == before, (
        "Unknown card changed financial records!"
    )


def test_malformed_card_creates_no_transaction():
    before = financial_snapshot()

    with SessionLocal() as db:
        with pytest.raises(PaymentError):
            process_scanned_card_purchase(
                db=db,
                card_credential="not-a-real-card",
                terminal_id=1,
                attendant_id=1,
                amount=1000,
                key="bad-card-test-12345",
            )

    assert financial_snapshot() == before


def test_negative_purchase_service_rejected():
    before = financial_snapshot()

    with SessionLocal() as db:
        with pytest.raises(PaymentError):
            process_canteen_purchase(
                db=db,
                wallet_id=1,
                student_id=1,
                card_id=1,
                terminal_id=1,
                attendant_id=1,
                amount=-1000,
                key="negative-test-12345",
            )

    assert financial_snapshot() == before
