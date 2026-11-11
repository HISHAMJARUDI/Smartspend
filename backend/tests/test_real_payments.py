from app.models.audit_event import AuditEvent
import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text

from app.database import SessionLocal
from app.models.school import School
from app.models.user import User
from app.models.student import Student
from app.models.wallet import Wallet
from app.models.card import Card
from app.models.canteen_terminal import CanteenTerminal
from app.models.transaction import Transaction
from app.models.ledger_account import LedgerAccount
from app.models.ledger_entry import LedgerEntry

from app.services.wallet_service import (
    PaymentError,
    process_scanned_card_purchase,
)
from app.services.terminal_service import create_terminal_secret


@pytest.fixture
def payment_data():
    """
    Create a temporary test school, student, wallet,
    card, attendant and POS terminal.

    Delete the fixture's records after each test.
    """
    suffix = uuid4().hex[:12]
    credential = "SC1." + uuid4().hex + uuid4().hex[:11]
    credential_hash = hashlib.sha256(
        credential.encode("utf-8")
    ).hexdigest()

    # Additional protection against using the wrong database.
    with SessionLocal() as db:
        database = db.scalar(text("SELECT current_database()"))
        assert database == "smartspend_test"

    with SessionLocal.begin() as db:
        school = School(
            name=f"Test School {suffix}",
            code=f"T-{suffix}",
            is_active=True,
        )
        other_school = School(
            name=f"Other School {suffix}",
            code=f"O-{suffix}",
            is_active=True,
        )
        db.add_all([school, other_school])
        db.flush()

        student_user = User(
            full_name="Automated Test Student",
            email=f"student-{suffix}@example.test",
            password_hash="test-only-not-a-login",
            role="student",
            school_id=school.id,
            is_active=True,
        )
        attendant = User(
            full_name="Automated Test Attendant",
            email=f"attendant-{suffix}@example.test",
            password_hash="test-only-not-a-login",
            role="canteen",
            school_id=school.id,
            is_active=True,
        )
        db.add_all([student_user, attendant])
        db.flush()

        student = Student(
            user_id=student_user.id,
            school_id=school.id,
            student_number=f"ST-{suffix}",
            class_name="Senior 3",
            is_active=True,
        )
        db.add(student)
        db.flush()

        wallet = Wallet(
            student_id=student.id,
            balance=10000,
            currency="UGX",
            is_active=True,
        )
        card = Card(
            student_id=student.id,
            card_token_hash=credential_hash,
            status="active",
        )
        terminal = CanteenTerminal(
            school_id=school.id,
            terminal_code=f"POS-{suffix}",
            name="Automated Test POS",
            is_active=True,
        )
        other_terminal = CanteenTerminal(
            school_id=other_school.id,
            terminal_code=f"OTHER-{suffix}",
            name="Unauthorized Test POS",
            is_active=True,
        )

        db.add_all([wallet, card, terminal, other_terminal])
        db.flush()

        # Unique test-only credentials for each POS device.
        terminal_key = create_terminal_secret(db, terminal.id)
        other_terminal_key = create_terminal_secret(
            db, other_terminal.id
        )

        data = {
            "wallet_id": wallet.id,
            "student_id": student.id,
            "card_id": card.id,
            "attendant_id": attendant.id,
            "terminal_id": terminal.id,
            "other_terminal_id": other_terminal.id,
            "student_user_id": student_user.id,
            "school_id": school.id,
            "other_school_id": other_school.id,
            "credential": credential,
            "terminal_key": terminal_key,
            "other_terminal_key": other_terminal_key,
        }

    try:
        yield data

    finally:
        # Remove child records before their parents.
        # Never delete records belonging to other fixtures.
        with SessionLocal.begin() as db:
            # Remove audit records before referenced users
            # and schools are deleted.
            db.execute(
                delete(AuditEvent).where(
                    AuditEvent.school_id.in_([
                        data["school_id"],
                        data["other_school_id"],
                    ])
                )
            )

            wallet_id = data["wallet_id"]

            transaction_ids = select(Transaction.id).where(
                Transaction.wallet_id == wallet_id
            )

            db.execute(
                delete(LedgerEntry).where(
                    LedgerEntry.transaction_id.in_(
                        transaction_ids
                    )
                )
            )

            db.execute(
                delete(Transaction).where(
                    Transaction.wallet_id == wallet_id
                )
            )

            db.execute(
                delete(LedgerAccount).where(
                    LedgerAccount.wallet_id == wallet_id
                )
            )

            db.execute(
                delete(Card).where(
                    Card.student_id == data["student_id"]
                )
            )

            db.execute(
                delete(Wallet).where(
                    Wallet.id == wallet_id
                )
            )

            db.execute(
                delete(Student).where(
                    Student.id == data["student_id"]
                )
            )

            db.execute(
                delete(User).where(
                    User.id.in_([
                        data["student_user_id"],
                        data["attendant_id"],
                    ])
                )
            )

            db.execute(
                delete(TerminalCredential).where(
                    TerminalCredential.terminal_id.in_([
                        data["terminal_id"],
                        data["other_terminal_id"],
                    ])
                )
            )

            db.execute(
                delete(CanteenTerminal).where(
                    CanteenTerminal.id.in_([
                        data["terminal_id"],
                        data["other_terminal_id"],
                    ])
                )
            )

            db.execute(
                delete(School).where(
                    School.id.in_([
                        data["school_id"],
                        data["other_school_id"],
                    ])
                )
            )


def make_purchase(data, amount=1000, key=None, terminal_id=None):
    if key is None:
        key = f"test-{uuid4().hex}"

    if terminal_id is None:
        terminal_id = data["terminal_id"]

    with SessionLocal() as db:
        return process_scanned_card_purchase(
            db=db,
            card_credential=data["credential"],
            terminal_id=terminal_id,
            attendant_id=data["attendant_id"],
            amount=amount,
            key=key,
            terminal_key=(
                data["terminal_key"]
                if terminal_id == data["terminal_id"]
                else data["other_terminal_key"]
            ),
        )


def get_balance(data):
    with SessionLocal() as db:
        return db.get(
            Wallet, data["wallet_id"]
        ).balance


def count_transactions(data):
    with SessionLocal() as db:
        return db.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.wallet_id == data["wallet_id"]
            )
        )


def test_successful_card_payment_and_ledger(payment_data):
    data = payment_data

    result = make_purchase(
        data, amount=2000
    )

    assert result["amount"] == 2000
    assert result["balance"] == 8000
    assert get_balance(data) == 8000
    assert count_transactions(data) == 1

    with SessionLocal() as db:
        transaction = db.get(
            Transaction, result["transaction_id"]
        )

        assert transaction.status == "completed"
        assert transaction.transaction_type == "purchase"
        assert transaction.amount == 2000
        assert transaction.wallet_id == data["wallet_id"]

        entries = db.scalars(
            select(LedgerEntry).where(
                LedgerEntry.transaction_id == transaction.id
            )
        ).all()

        assert len(entries) == 2

        debits = sum(
            entry.amount for entry in entries
            if entry.entry_type == "debit"
        )
        credits = sum(
            entry.amount for entry in entries
            if entry.entry_type == "credit"
        )

        assert debits == 2000
        assert credits == 2000

        account_types = {
            db.get(LedgerAccount, entry.account_id).account_type
            for entry in entries
        }

        assert account_types == {
            "wallet_liability",
            "canteen_payable",
        }


def test_duplicate_payment_not_deducted_twice(payment_data):
    data = payment_data
    key = f"duplicate-{uuid4().hex}"

    first = make_purchase(
        data, amount=1500, key=key
    )

    assert first["balance"] == 8500

    with pytest.raises(
        PaymentError,
        match="Transaction key already used",
    ):
        make_purchase(
            data, amount=1500, key=key
        )

    assert get_balance(data) == 8500
    assert count_transactions(data) == 1


def test_insufficient_balance_rejected(payment_data):
    data = payment_data

    with pytest.raises(
        PaymentError,
        match="Insufficient balance",
    ):
        make_purchase(
            data, amount=15000
        )

    assert get_balance(data) == 10000
    assert count_transactions(data) == 0


def test_blocked_card_rejected(payment_data):
    data = payment_data

    with SessionLocal.begin() as db:
        card = db.get(Card, data["card_id"])
        card.status = "blocked"

    with pytest.raises(
        PaymentError,
        match="Invalid or blocked card",
    ):
        make_purchase(
            data, amount=1000
        )

    assert get_balance(data) == 10000
    assert count_transactions(data) == 0


def test_other_school_terminal_rejected(payment_data):
    data = payment_data

    with pytest.raises(
        PaymentError,
        match="Unauthorized canteen terminal",
    ):
        make_purchase(
            data,
            amount=1000,
            terminal_id=data["other_terminal_id"],
        )

    assert get_balance(data) == 10000
    assert count_transactions(data) == 0



def test_concurrent_purchases_prevent_overspending(payment_data):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    data = payment_data
    barrier = Barrier(2, timeout=10)

    def attempt_purchase():
        barrier.wait()

        try:
            result = make_purchase(
                data,
                amount=7000,
                key=f"concurrent-{uuid4().hex}",
            )
            return ("completed", result)
        except PaymentError as error:
            return ("rejected", str(error))

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(attempt_purchase)
        second = executor.submit(attempt_purchase)

        results = [
            first.result(timeout=20),
            second.result(timeout=20),
        ]

    completed = [
        item for item in results
        if item[0] == "completed"
    ]

    rejected = [
        item for item in results
        if item[0] == "rejected"
    ]

    assert len(completed) == 1
    assert len(rejected) == 1
    assert rejected[0][1] == "Insufficient balance"

    assert get_balance(data) == 3000
    assert count_transactions(data) == 1

    with SessionLocal() as db:
        transaction = db.scalar(
            select(Transaction).where(
                Transaction.wallet_id == data["wallet_id"]
            )
        )

        assert transaction.amount == 7000
        assert transaction.status == "completed"

        entries = db.scalars(
            select(LedgerEntry).where(
                LedgerEntry.transaction_id == transaction.id
            )
        ).all()

        assert len(entries) == 2
        assert sorted(
            entry.amount for entry in entries
        ) == [7000, 7000]

    print(
        "PASS: Concurrent purchases cannot overspend"
    )


def test_concurrent_duplicate_key_charged_once(payment_data):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    data = payment_data
    duplicate_key = f"same-key-{uuid4().hex}"
    barrier = Barrier(2, timeout=10)

    def attempt_purchase():
        barrier.wait()

        try:
            result = make_purchase(
                data,
                amount=2000,
                key=duplicate_key,
            )
            return ("completed", result)
        except PaymentError as error:
            return ("rejected", str(error))

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(attempt_purchase)
        second = executor.submit(attempt_purchase)

        results = [
            first.result(timeout=20),
            second.result(timeout=20),
        ]

    completed = [
        item for item in results
        if item[0] == "completed"
    ]

    rejected = [
        item for item in results
        if item[0] == "rejected"
    ]

    assert len(completed) == 1
    assert len(rejected) == 1
    assert rejected[0][1] == "Transaction key already used"

    assert get_balance(data) == 8000
    assert count_transactions(data) == 1

    print(
        "PASS: Concurrent duplicate request charged once"
    )



def test_purchase_rejected_when_card_blocking_commits_first(
    payment_data,
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from time import sleep

    data = payment_data
    worker_started = Event()

    def attempt_purchase():
        worker_started.set()

        try:
            make_purchase(
                data,
                amount=2000,
                key=f"block-race-{uuid4().hex}",
            )
            return "completed"

        except PaymentError as error:
            return str(error)

    # Begin an administrator-like blocking transaction.
    with SessionLocal.begin() as db:
        student = db.scalar(
            select(Student)
            .where(Student.id == data["student_id"])
            .with_for_update()
        )

        assert student is not None

        card = db.scalar(
            select(Card)
            .where(Card.id == data["card_id"])
            .with_for_update()
        )

        assert card.status == "active"

        # The change is initially uncommitted.
        card.status = "blocked"
        db.flush()

        executor = ThreadPoolExecutor(max_workers=1)

        try:
            future = executor.submit(attempt_purchase)
            assert worker_started.wait(timeout=10)

            sleep(0.3)

            assert not future.done(), (
                "Payment finished before the blocking "
                "transaction committed"
            )
        except BaseException:
            executor.shutdown(wait=False, cancel_futures=True)
            raise

    # The card-blocking transaction has now committed.
    try:
        result = future.result(timeout=15)
    finally:
        executor.shutdown(wait=True)

    assert result == "Invalid or blocked card"
    assert get_balance(data) == 10000
    assert count_transactions(data) == 0



# ============================================================
# PHASE 13: FULL HTTP POS SECURITY TESTS
# ============================================================

import secrets

from fastapi.testclient import TestClient

from app.main import app
from app.database import settings
from app.core.security import create_access_token
from app.models.terminal_credential import TerminalCredential
from app.services.terminal_service import hash_terminal_secret


@pytest.fixture
def api_context(payment_data, monkeypatch):
    """
    Set up authenticated HTTP testing.

    All records belong to the isolated test database.
    No real passwords, JWTs, or terminal secrets are used.
    """
    data = payment_data

    monkeypatch.setattr(
        settings,
        "DEMO_POS_ENABLED",
        True,
    )

    terminal_key = data["terminal_key"]
    other_terminal_key = data["other_terminal_key"]

    attendant_token = create_access_token(
        data["attendant_id"]
    )

    student_token = create_access_token(
        data["student_user_id"]
    )

    context = {
        "data": data,
        "terminal_key": terminal_key,
        "other_terminal_key": other_terminal_key,
        "attendant_token": attendant_token,
        "student_token": student_token,
    }

    with TestClient(app) as client:
        context["client"] = client
        yield context


def api_headers(context, token=None, terminal_key=None):
    if token is None:
        token = context["attendant_token"]

    if terminal_key is None:
        terminal_key = context["terminal_key"]

    return {
        "Authorization": f"Bearer {token}",
        "X-Terminal-Key": terminal_key,
    }


def api_purchase_body(context, amount=1000, key=None):
    if key is None:
        key = f"api-test-{uuid4().hex}"

    return {
        "card_credential": context["data"]["credential"],
        "amount": amount,
        "idempotency_key": key,
    }


def test_api_valid_card_purchase(api_context):
    context = api_context
    data = context["data"]

    response = context["client"].post(
        "/pos/purchases",
        headers=api_headers(context),
        json=api_purchase_body(context, amount=2000),
    )

    assert response.status_code == 201, response.text

    result = response.json()

    assert result["status"] == "completed"
    assert result["amount"] == 2000
    assert result["balance"] == 8000

    assert get_balance(data) == 8000
    assert count_transactions(data) == 1

    with SessionLocal() as db:
        entries = db.scalars(
            select(LedgerEntry).where(
                LedgerEntry.transaction_id ==
                result["transaction_id"]
            )
        ).all()

    assert len(entries) == 2

    assert sum(
        entry.amount
        for entry in entries
        if entry.entry_type == "debit"
    ) == 2000

    assert sum(
        entry.amount
        for entry in entries
        if entry.entry_type == "credit"
    ) == 2000


def test_api_missing_jwt_rejected(api_context):
    context = api_context
    data = context["data"]

    response = context["client"].post(
        "/pos/purchases",
        headers={
            "X-Terminal-Key": context["terminal_key"]
        },
        json=api_purchase_body(context),
    )

    assert response.status_code == 401
    assert get_balance(data) == 10000
    assert count_transactions(data) == 0


def test_api_wrong_role_rejected(api_context):
    context = api_context
    data = context["data"]

    response = context["client"].post(
        "/pos/purchases",
        headers=api_headers(
            context,
            token=context["student_token"],
        ),
        json=api_purchase_body(context),
    )

    assert response.status_code == 403
    assert get_balance(data) == 10000
    assert count_transactions(data) == 0


def test_api_missing_terminal_key_rejected(api_context):
    context = api_context
    data = context["data"]

    response = context["client"].post(
        "/pos/purchases",
        headers={
            "Authorization": (
                f"Bearer {context['attendant_token']}"
            )
        },
        json=api_purchase_body(context),
    )

    assert response.status_code == 401
    assert get_balance(data) == 10000
    assert count_transactions(data) == 0


def test_api_invalid_terminal_key_rejected(api_context):
    context = api_context
    data = context["data"]

    response = context["client"].post(
        "/pos/purchases",
        headers=api_headers(
            context,
            terminal_key="1.invalid-test-secret",
        ),
        json=api_purchase_body(context),
    )

    assert response.status_code == 401
    assert get_balance(data) == 10000
    assert count_transactions(data) == 0


def test_api_cross_school_terminal_rejected(api_context):
    context = api_context
    data = context["data"]

    response = context["client"].post(
        "/pos/purchases",
        headers=api_headers(
            context,
            terminal_key=context["other_terminal_key"],
        ),
        json=api_purchase_body(context),
    )

    assert response.status_code == 403
    assert get_balance(data) == 10000
    assert count_transactions(data) == 0


def test_api_missing_card_credential_rejected(api_context):
    context = api_context
    data = context["data"]

    response = context["client"].post(
        "/pos/purchases",
        headers=api_headers(context),
        json={
            "amount": 1000,
            "idempotency_key": f"missing-{uuid4().hex}",
        },
    )

    assert response.status_code == 422
    assert get_balance(data) == 10000
    assert count_transactions(data) == 0


def test_api_blocked_card_rejected(api_context):
    context = api_context
    data = context["data"]

    with SessionLocal.begin() as db:
        card = db.get(Card, data["card_id"])
        card.status = "blocked"

    response = context["client"].post(
        "/pos/purchases",
        headers=api_headers(context),
        json=api_purchase_body(context),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Invalid or blocked card"
    )

    assert get_balance(data) == 10000
    assert count_transactions(data) == 0


def test_api_duplicate_purchase_charged_once(api_context):
    context = api_context
    data = context["data"]

    body = api_purchase_body(
        context,
        amount=1500,
        key=f"http-duplicate-{uuid4().hex}",
    )

    first = context["client"].post(
        "/pos/purchases",
        headers=api_headers(context),
        json=body,
    )

    second = context["client"].post(
        "/pos/purchases",
        headers=api_headers(context),
        json=body,
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 400, second.text

    assert second.json()["detail"] == (
        "Transaction key already used"
    )

    assert get_balance(data) == 8500
    assert count_transactions(data) == 1



# ============================================================
# PHASE 14C: CARD MANAGEMENT AUDIT TESTS
# ============================================================

from app.services.card_service import (
    issue_card,
    block_card,
    replace_card,
    CardConflict,
)


def get_card_audits(data):
    with SessionLocal() as db:
        return db.scalars(
            select(AuditEvent)
            .where(AuditEvent.school_id == data["school_id"])
            .order_by(AuditEvent.id)
        ).all()


def test_card_blocking_creates_audit_event(payment_data):
    data = payment_data

    with SessionLocal() as db:
        card = block_card(
            db,
            data["card_id"],
            actor_id=data["student_user_id"],
        )

        assert card.status == "blocked"

    events = get_card_audits(data)
    assert len(events) == 1

    event = events[0]
    assert event.action == "card.blocked"
    assert event.actor_id == data["student_user_id"]
    assert event.school_id == data["school_id"]
    assert event.entity_id == data["card_id"]
    assert event.outcome == "success"
    assert event.details["previous_status"] == "active"
    assert event.details["new_status"] == "blocked"

    assert get_balance(data) == 10000
    assert count_transactions(data) == 0


def test_card_issuance_creates_audit_event(payment_data):
    data = payment_data

    # Retire the existing test card first.
    with SessionLocal() as db:
        block_card(
            db,
            data["card_id"],
            actor_id=data["student_user_id"],
        )

    with SessionLocal() as db:
        new_card = issue_card(
            db,
            data["student_id"],
            actor_id=data["student_user_id"],
        )
        new_card_id = new_card.id

    events = get_card_audits(data)
    issued = [e for e in events if e.action == "card.issued"]

    assert len(issued) == 1
    assert issued[0].entity_id == new_card_id
    assert issued[0].actor_id == data["student_user_id"]
    assert issued[0].details["new_status"] == "active"

    assert get_balance(data) == 10000


def test_card_replacement_creates_audit_event(payment_data):
    data = payment_data

    with SessionLocal() as db:
        new_card = replace_card(
            db,
            data["card_id"],
            actor_id=data["student_user_id"],
        )
        new_card_id = new_card.id

    events = get_card_audits(data)

    assert len(events) == 1
    assert events[0].action == "card.replaced"
    assert events[0].actor_id == data["student_user_id"]
    assert events[0].entity_id == data["card_id"]
    assert events[0].details["replacement_card_id"] == new_card_id

    with SessionLocal() as db:
        old_card = db.get(Card, data["card_id"])
        replacement = db.get(Card, new_card_id)

        assert old_card.status == "blocked"
        assert replacement.status == "active"

    assert get_balance(data) == 10000


def test_rejected_card_issuance_has_no_success_audit(payment_data):
    data = payment_data

    # An active card already exists for the student.
    with SessionLocal() as db:
        with pytest.raises(
            CardConflict,
            match="Student already has an active card",
        ):
            issue_card(
                db,
                data["student_id"],
                actor_id=data["student_user_id"],
            )

    assert get_card_audits(data) == []
    assert get_balance(data) == 10000
    assert count_transactions(data) == 0



# ============================================================
# PHASE 14D: AUDIT HISTORY API TESTS
# ============================================================

from app.services.audit_service import record_audit_event


@pytest.fixture
def audit_api_context(payment_data):
    data = payment_data
    suffix = uuid4().hex[:12]

    with SessionLocal.begin() as db:
        admin = User(
            full_name="Audit Test Administrator",
            email=f"audit-admin-{suffix}@example.test",
            password_hash="test-only-not-a-login",
            role="system_admin",
            school_id=None,
            is_active=True,
        )

        db.add(admin)
        db.flush()
        admin_id = admin.id

        record_audit_event(
            db,
            actor_id=admin_id,
            school_id=data["school_id"],
            action="card.blocked",
            entity_type="card",
            entity_id=data["card_id"],
            outcome="success",
            details={
                "previous_status": "active",
                "new_status": "blocked",
            },
        )

        record_audit_event(
            db,
            actor_id=admin_id,
            school_id=data["school_id"],
            action="card.issued",
            entity_type="card",
            entity_id=data["card_id"],
            outcome="success",
            details={"new_status": "active"},
        )

    context = {
        "data": data,
        "admin_id": admin_id,
        "admin_token": create_access_token(admin_id),
        "student_token": create_access_token(
            data["student_user_id"]
        ),
    }

    try:
        with TestClient(app) as client:
            context["client"] = client
            yield context

    finally:
        # Remove records referencing this administrator
        # before deleting the temporary admin account.
        with SessionLocal.begin() as db:
            db.execute(
                delete(AuditEvent).where(
                    AuditEvent.actor_id == admin_id
                )
            )
            db.execute(
                delete(User).where(User.id == admin_id)
            )


def test_audit_api_system_admin_can_read(audit_api_context):
    context = audit_api_context

    response = context["client"].get(
        "/audit/events",
        headers={
            "Authorization":
            f"Bearer {context['admin_token']}"
        },
        params={
            "school_id": context["data"]["school_id"],
        },
    )

    assert response.status_code == 200, response.text

    events = response.json()
    assert len(events) == 2

    assert events[0]["action"] == "card.issued"
    assert events[1]["action"] == "card.blocked"

    assert all(
        event["actor_id"] == context["admin_id"]
        for event in events
    )


def test_audit_api_missing_jwt_rejected(audit_api_context):
    context = audit_api_context

    response = context["client"].get(
        "/audit/events"
    )

    assert response.status_code == 401


def test_audit_api_student_forbidden(audit_api_context):
    context = audit_api_context

    response = context["client"].get(
        "/audit/events",
        headers={
            "Authorization":
            f"Bearer {context['student_token']}"
        },
    )

    assert response.status_code == 403


def test_audit_api_filters_and_pagination(audit_api_context):
    context = audit_api_context

    headers = {
        "Authorization":
        f"Bearer {context['admin_token']}"
    }

    filtered = context["client"].get(
        "/audit/events",
        headers=headers,
        params={
            "school_id": context["data"]["school_id"],
            "action": "card.blocked",
        },
    )

    assert filtered.status_code == 200
    assert len(filtered.json()) == 1
    assert filtered.json()[0]["action"] == "card.blocked"

    paginated = context["client"].get(
        "/audit/events",
        headers=headers,
        params={
            "school_id": context["data"]["school_id"],
            "limit": 1,
            "offset": 0,
        },
    )

    assert paginated.status_code == 200
    assert len(paginated.json()) == 1

    invalid_limit = context["client"].get(
        "/audit/events",
        headers=headers,
        params={"limit": 101},
    )

    assert invalid_limit.status_code == 422



# ============================================================
# PHASE 14E: REJECTED POS AUDIT TESTS
# ============================================================


def test_api_invalid_card_creates_denied_audit(api_context):
    context = api_context
    data = context["data"]

    body = {
        "card_credential": "SC1." + ("A" * 43),
        "amount": 1000,
        "idempotency_key": f"invalid-audit-{uuid4().hex}",
    }

    response = context["client"].post(
        "/pos/purchases",
        headers=api_headers(context),
        json=body,
    )

    assert response.status_code == 400
    assert get_balance(data) == 10000
    assert count_transactions(data) == 0

    with SessionLocal() as db:
        events = db.scalars(
            select(AuditEvent).where(
                AuditEvent.school_id == data["school_id"],
                AuditEvent.action == "pos.purchase_rejected",
            )
        ).all()

        assert len(events) == 1
        event = events[0]

        assert event.outcome == "denied"
        assert event.actor_id == data["attendant_id"]
        assert event.entity_id == data["terminal_id"]
        assert event.details["reason_code"] == "invalid_card"

        # No credentials or secrets in audit metadata.
        assert "card_credential" not in event.details
        assert "terminal_secret" not in event.details


def test_api_duplicate_payment_creates_denied_audit(api_context):
    context = api_context
    data = context["data"]

    body = api_purchase_body(
        context,
        amount=2000,
        key=f"duplicate-audit-{uuid4().hex}",
    )

    first = context["client"].post(
        "/pos/purchases",
        headers=api_headers(context),
        json=body,
    )

    second = context["client"].post(
        "/pos/purchases",
        headers=api_headers(context),
        json=body,
    )

    assert first.status_code == 201
    assert second.status_code == 400

    assert get_balance(data) == 8000
    assert count_transactions(data) == 1

    with SessionLocal() as db:
        events = db.scalars(
            select(AuditEvent).where(
                AuditEvent.school_id == data["school_id"],
                AuditEvent.action == "pos.purchase_rejected",
            )
        ).all()

        assert len(events) == 1
        assert events[0].outcome == "denied"
        assert events[0].details["reason_code"] == (
            "duplicate_request"
        )



# ============================================================
# PHASE 15B: TERMINAL CREDENTIAL MANAGEMENT TESTS
# ============================================================

from app.services.terminal_service import verify_terminal_key


@pytest.fixture
def terminal_admin_context(api_context):
    context = api_context
    suffix = uuid4().hex[:12]

    with SessionLocal.begin() as db:
        admin = User(
            full_name="Temporary Terminal Administrator",
            email=f"terminal-admin-{suffix}@example.test",
            password_hash="test-only-not-a-login",
            role="system_admin",
            school_id=None,
            is_active=True,
        )
        db.add(admin)
        db.flush()
        admin_id = admin.id

    context["terminal_admin_id"] = admin_id
    context["terminal_admin_token"] = create_access_token(
        admin_id
    )

    try:
        yield context

    finally:
        # Audit records reference the temporary administrator.
        # Remove them before deleting the user.
        with SessionLocal.begin() as db:
            db.execute(
                delete(AuditEvent).where(
                    AuditEvent.actor_id == admin_id
                )
            )
            db.execute(
                delete(User).where(
                    User.id == admin_id
                )
            )


def terminal_admin_headers(context):
    return {
        "Authorization": (
            f"Bearer {context['terminal_admin_token']}"
        )
    }


def terminal_key_is_valid(key):
    with SessionLocal() as db:
        terminal = verify_terminal_key(db, key)
        return terminal is not None


def test_admin_rotates_terminal_credential(
    terminal_admin_context,
):
    context = terminal_admin_context
    data = context["data"]
    old_key = context["terminal_key"]

    assert terminal_key_is_valid(old_key)

    response = context["client"].post(
        f"/admin/terminals/{data['terminal_id']}/rotate",
        headers=terminal_admin_headers(context),
    )

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"

    result = response.json()
    new_key = result["terminal_key"]

    assert result["terminal_id"] == data["terminal_id"]
    assert new_key != old_key

    assert not terminal_key_is_valid(old_key)
    assert terminal_key_is_valid(new_key)

    with SessionLocal() as db:
        event = db.scalar(
            select(AuditEvent).where(
                AuditEvent.action ==
                "terminal.credential_rotated",
                AuditEvent.entity_id == data["terminal_id"],
            )
        )

        assert event is not None
        assert event.actor_id == context["terminal_admin_id"]
        assert event.school_id == data["school_id"]
        assert event.outcome == "success"

        # Audit details must never contain the new secret.
        assert new_key not in str(event.details)
        assert "terminal_key" not in event.details


def test_admin_revokes_terminal_credential(
    terminal_admin_context,
):
    context = terminal_admin_context
    data = context["data"]
    key = context["terminal_key"]

    assert terminal_key_is_valid(key)

    response = context["client"].post(
        f"/admin/terminals/{data['terminal_id']}/revoke",
        headers=terminal_admin_headers(context),
    )

    assert response.status_code == 200, response.text
    assert not terminal_key_is_valid(key)

    with SessionLocal() as db:
        event = db.scalar(
            select(AuditEvent).where(
                AuditEvent.action ==
                "terminal.credential_revoked",
                AuditEvent.entity_id == data["terminal_id"],
            )
        )

        assert event is not None
        assert event.actor_id == context["terminal_admin_id"]
        assert event.outcome == "success"

    # Repeated revocation must not create a second success.
    repeated = context["client"].post(
        f"/admin/terminals/{data['terminal_id']}/revoke",
        headers=terminal_admin_headers(context),
    )

    assert repeated.status_code == 409


def test_student_cannot_manage_terminal_credentials(
    terminal_admin_context,
):
    context = terminal_admin_context
    data = context["data"]

    headers = {
        "Authorization": (
            f"Bearer {context['student_token']}"
        )
    }

    for action in ("rotate", "revoke"):
        response = context["client"].post(
            f"/admin/terminals/{data['terminal_id']}/{action}",
            headers=headers,
        )

        assert response.status_code == 403

    assert terminal_key_is_valid(context["terminal_key"])


def test_unauthenticated_terminal_management_rejected(
    terminal_admin_context,
):
    context = terminal_admin_context
    data = context["data"]

    for action in ("rotate", "revoke"):
        response = context["client"].post(
            f"/admin/terminals/{data['terminal_id']}/{action}",
        )

        assert response.status_code == 401

    assert terminal_key_is_valid(context["terminal_key"])



# ============================================================
# PHASE 15C: POS PAYMENTS AFTER CREDENTIAL CHANGES
# ============================================================


def test_revoked_terminal_cannot_purchase(
    terminal_admin_context,
):
    context = terminal_admin_context
    data = context["data"]

    # Administrator revokes the existing terminal credential.
    revoke = context["client"].post(
        f"/admin/terminals/{data['terminal_id']}/revoke",
        headers=terminal_admin_headers(context),
    )

    assert revoke.status_code == 200, revoke.text

    # Attempt a payment using the revoked key.
    purchase = context["client"].post(
        "/pos/purchases",
        headers=api_headers(context),
        json=api_purchase_body(context, amount=1000),
    )

    assert purchase.status_code == 401
    assert purchase.json()["detail"] == (
        "Invalid terminal credentials"
    )

    assert get_balance(data) == 10000
    assert count_transactions(data) == 0


def test_rotated_old_terminal_key_cannot_purchase(
    terminal_admin_context,
):
    context = terminal_admin_context
    data = context["data"]

    old_key = context["terminal_key"]

    # Administrator issues a new credential.
    rotation = context["client"].post(
        f"/admin/terminals/{data['terminal_id']}/rotate",
        headers=terminal_admin_headers(context),
    )

    assert rotation.status_code == 200, rotation.text

    new_key = rotation.json()["terminal_key"]

    # Old key must fail.
    rejected = context["client"].post(
        "/pos/purchases",
        headers=api_headers(
            context,
            terminal_key=old_key,
        ),
        json=api_purchase_body(context, amount=1000),
    )

    assert rejected.status_code == 401
    assert get_balance(data) == 10000
    assert count_transactions(data) == 0

    # New key must allow a valid simulated purchase.
    approved = context["client"].post(
        "/pos/purchases",
        headers=api_headers(
            context,
            terminal_key=new_key,
        ),
        json=api_purchase_body(context, amount=1000),
    )

    assert approved.status_code == 201, approved.text
    assert approved.json()["balance"] == 9000

    assert get_balance(data) == 9000
    assert count_transactions(data) == 1



# ============================================================
# PHASE 15E: IN-FLIGHT TERMINAL CREDENTIAL SECURITY
# ============================================================


@pytest.mark.parametrize("action", ["revoke", "rotate"])
def test_inflight_credential_change_rejects_payment(
    terminal_admin_context,
    monkeypatch,
    action,
):
    import importlib

    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    context = terminal_admin_context
    data = context["data"]

    entered_payment_service = Event()
    resume_payment = Event()

    # Patch only the POS endpoint's service reference.
    # The original financial service still runs afterward.
    pos_module = importlib.import_module("app.api.pos")

    original_service = (
        pos_module.process_scanned_card_purchase
    )

    def paused_payment_service(*args, **kwargs):
        entered_payment_service.set()

        if not resume_payment.wait(timeout=15):
            raise RuntimeError(
                "Timed out waiting to resume payment"
            )

        return original_service(*args, **kwargs)

    monkeypatch.setattr(
        pos_module,
        "process_scanned_card_purchase",
        paused_payment_service,
    )

    body = api_purchase_body(
        context,
        amount=2000,
        key=f"inflight-{action}-{uuid4().hex}",
    )

    def submit_purchase():
        return context["client"].post(
            "/pos/purchases",
            headers=api_headers(context),
            json=body,
        )

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(submit_purchase)

        try:
            assert entered_payment_service.wait(timeout=15), (
                "Purchase did not reach the financial service"
            )

            # The terminal has already passed its initial
            # authentication dependency at this point.
            assert not future.done()

            change = context["client"].post(
                (
                    f"/admin/terminals/"
                    f"{data['terminal_id']}/{action}"
                ),
                headers=terminal_admin_headers(context),
            )

            assert change.status_code == 200, change.text

        finally:
            # Always release the worker, even if an
            # assertion above fails.
            resume_payment.set()

        payment = future.result(timeout=20)

    # The original request used the credential that
    # has now been revoked or rotated.
    assert payment.status_code == 401, payment.text

    assert payment.json()["detail"] == (
        "Invalid terminal credentials"
    )

    assert get_balance(data) == 10000
    assert count_transactions(data) == 0

    # Verify the rejected purchase was audited,
    # without recording the device secret.
    with SessionLocal() as db:
        events = db.scalars(
            select(AuditEvent).where(
                AuditEvent.school_id == data["school_id"],
                AuditEvent.action == "pos.purchase_rejected",
            )
        ).all()

        assert len(events) == 1

        event = events[0]
        assert event.outcome == "denied"
        assert event.details["reason_code"] == (
            "unauthorized_terminal"
        )
        assert "terminal_key" not in event.details
        assert "card_credential" not in event.details



# ============================================================
# PHASE 15F: POSTGRESQL CREDENTIAL ROW-LOCK TEST
# ============================================================


def test_purchase_waits_for_credential_revocation_lock(
    terminal_admin_context,
):
    import time

    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy import text

    from app.models.terminal_credential import TerminalCredential

    context = terminal_admin_context
    data = context["data"]

    terminal_id = data["terminal_id"]

    body = api_purchase_body(
        context,
        amount=2000,
        key=f"locked-revocation-{uuid4().hex}",
    )

    def submit_purchase():
        return context["client"].post(
            "/pos/purchases",
            headers=api_headers(context),
            json=body,
        )

    def has_waiting_database_lock():
        with SessionLocal() as monitor_db:
            return bool(
                monitor_db.scalar(
                    text("""
                        SELECT EXISTS (
                            SELECT 1
                            FROM pg_stat_activity
                            WHERE datname = current_database()
                              AND wait_event_type = 'Lock'
                              AND pid <> pg_backend_pid()
                        )
                    """)
                )
            )

    with ThreadPoolExecutor(max_workers=1) as executor:

        # Hold the credential row lock in a separate
        # database transaction, just like credential
        # management does during revocation.
        with SessionLocal() as admin_db:

            with admin_db.begin():

                credential = admin_db.scalar(
                    select(TerminalCredential)
                    .where(
                        TerminalCredential.terminal_id
                        == terminal_id
                    )
                    .with_for_update()
                )

                assert credential is not None
                assert credential.is_active

                # Update but deliberately do not commit yet.
                credential.is_active = False
                admin_db.flush()

                # Start the POS purchase concurrently.
                future = executor.submit(submit_purchase)

                # Wait until PostgreSQL reports lock
                # contention. No arbitrary timing assumption.
                deadline = time.monotonic() + 10
                observed_lock_wait = False

                while time.monotonic() < deadline:

                    if has_waiting_database_lock():
                        observed_lock_wait = True
                        break

                    if future.done():
                        break

                    time.sleep(0.05)

                assert observed_lock_wait, (
                    "POS request did not wait for the "
                    "credential row lock"
                )

                assert not future.done(), (
                    "Payment finished before credential "
                    "revocation committed"
                )

            # Exiting admin_db.begin() commits revocation
            # and releases the PostgreSQL row lock.

        payment = future.result(timeout=15)

    assert payment.status_code == 401, payment.text
    assert payment.json()["detail"] == (
        "Invalid terminal credentials"
    )

    # No purchase or wallet deduction is permitted.
    assert get_balance(data) == 10000
    assert count_transactions(data) == 0

    # The denied purchase should be audited.
    with SessionLocal() as db:
        events = db.scalars(
            select(AuditEvent).where(
                AuditEvent.school_id == data["school_id"],
                AuditEvent.action == "pos.purchase_rejected",
            )
        ).all()

        assert len(events) == 1

        event = events[0]
        assert event.outcome == "denied"

        assert event.details["reason_code"] == (
            "unauthorized_terminal"
        )

        assert "terminal_key" not in event.details
        assert "card_credential" not in event.details



# ============================================================
# PHASE 16A: MANDATORY TERMINAL AUTHENTICATION
# ============================================================


def test_direct_purchase_missing_terminal_key_rejected(
    payment_data,
):
    data = payment_data

    with SessionLocal() as db:
        with pytest.raises(
            PaymentError,
            match="Invalid terminal credentials",
        ):
            process_scanned_card_purchase(
                db=db,
                card_credential=data["credential"],
                terminal_id=data["terminal_id"],
                attendant_id=data["attendant_id"],
                amount=1000,
                key=f"missing-key-{uuid4().hex}",
            )

    assert get_balance(data) == 10000
    assert count_transactions(data) == 0


def test_core_payment_missing_terminal_key_rejected(
    payment_data,
):
    from app.services.wallet_service import (
        process_canteen_purchase,
    )

    data = payment_data

    with SessionLocal() as db:
        with pytest.raises(
            PaymentError,
            match="Invalid terminal credentials",
        ):
            process_canteen_purchase(
                db=db,
                wallet_id=data["wallet_id"],
                student_id=data["student_id"],
                card_id=data["card_id"],
                terminal_id=data["terminal_id"],
                attendant_id=data["attendant_id"],
                amount=1000,
                key=f"core-missing-key-{uuid4().hex}",
            )

    assert get_balance(data) == 10000
    assert count_transactions(data) == 0


def test_direct_purchase_revoked_terminal_key_rejected(
    payment_data,
):
    data = payment_data

    with SessionLocal.begin() as db:
        credential = db.scalar(
            select(TerminalCredential).where(
                TerminalCredential.terminal_id
                == data["terminal_id"]
            )
        )

        assert credential is not None
        credential.is_active = False

    with SessionLocal() as db:
        with pytest.raises(
            PaymentError,
            match="Invalid terminal credentials",
        ):
            process_scanned_card_purchase(
                db=db,
                card_credential=data["credential"],
                terminal_id=data["terminal_id"],
                attendant_id=data["attendant_id"],
                amount=1000,
                key=f"revoked-direct-{uuid4().hex}",
                terminal_key=data["terminal_key"],
            )

    assert get_balance(data) == 10000
    assert count_transactions(data) == 0
