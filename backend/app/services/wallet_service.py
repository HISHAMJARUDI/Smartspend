import hashlib
import hmac
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.wallet import Wallet
from app.models.student import Student
from app.models.card import Card
from app.models.canteen_terminal import CanteenTerminal
from app.models.terminal_credential import TerminalCredential
from app.services.terminal_service import hash_terminal_secret
from app.models.transaction import Transaction
from app.models.ledger_account import LedgerAccount
from app.models.ledger_entry import LedgerEntry
from app.models.user import User
from app.database import settings


class PaymentError(Exception):
    pass


def get_account(
    db: Session,
    code: str,
    name: str,
    account_type: str,
    wallet_id: int | None = None,
) -> LedgerAccount:

    account = db.scalar(
        select(LedgerAccount).where(
            LedgerAccount.account_code == code
        )
    )

    if account is None:
        account = LedgerAccount(
            account_code=code,
            account_name=name,
            account_type=account_type,
            wallet_id=wallet_id,
            currency="UGX",
        )
        db.add(account)
        db.flush()

    return account


def get_locked_wallet(db: Session, wallet_id: int):
    wallet = db.scalar(
        select(Wallet)
        .where(Wallet.id == wallet_id)
        .with_for_update()
    )

    if wallet is None or not wallet.is_active:
        raise PaymentError("Wallet unavailable")

    if wallet.currency != "UGX":
        raise PaymentError("Unsupported currency")

    return wallet


def ensure_unique_key(db: Session, key: str):
    if not key or len(key) > 100:
        raise PaymentError("Invalid idempotency key")

    existing = db.scalar(
        select(Transaction).where(
            Transaction.idempotency_key == key
        )
    )

    if existing:
        raise PaymentError(
            "Transaction key already used"
        )


def post_entries(
    db: Session,
    transaction: Transaction,
    debit_account: LedgerAccount,
    credit_account: LedgerAccount,
    amount: int,
):
    if amount <= 0:
        raise PaymentError("Amount must be positive")

    if debit_account.id == credit_account.id:
        raise PaymentError("Accounts must be different")

    if (
        debit_account.currency != transaction.currency
        or credit_account.currency != transaction.currency
    ):
        raise PaymentError("Currency mismatch")

    db.add_all([
        LedgerEntry(
            transaction_id=transaction.id,
            account_id=debit_account.id,
            entry_type="debit",
            amount=amount,
        ),
        LedgerEntry(
            transaction_id=transaction.id,
            account_id=credit_account.id,
            entry_type="credit",
            amount=amount,
        ),
    ])


def demo_fund_wallet(
    db: Session,
    wallet_id: int,
    admin_id: int,
    amount: int,
    key: str,
):
    if settings.APP_ENV == "production":
        raise PaymentError(
            "Demo funding is disabled in production"
        )

    if amount <= 0:
        raise PaymentError("Amount must be positive")

    with db.begin():
        ensure_unique_key(db, key)

        admin = db.get(User, admin_id)

        if (
            admin is None
            or admin.role != "system_admin"
            or not admin.is_active
        ):
            raise PaymentError("System administrator required")

        wallet = get_locked_wallet(db, wallet_id)

        clearing = get_account(
            db,
            "FUNDING-CLEARING-UGX",
            "Demo Funding Clearing",
            "funding_clearing",
        )

        liability = get_account(
            db,
            f"WALLET-{wallet.id}",
            f"Student Wallet {wallet.id}",
            "wallet_liability",
            wallet.id,
        )

        transaction = Transaction(
            wallet_id=wallet.id,
            initiated_by=admin.id,
            terminal_id=None,
            amount=amount,
            currency="UGX",
            transaction_type="deposit",
            status="completed",
            idempotency_key=key,
        )

        db.add(transaction)
        db.flush()

        post_entries(
            db, transaction, clearing, liability, amount
        )

        wallet.balance += amount
        db.flush()

        result = {
            "transaction_id": transaction.id,
            "amount": amount,
            "balance": wallet.balance,
        }

    return result


def _process_canteen_purchase_impl(
    db: Session,
    wallet_id: int,
    student_id: int,
    card_id: int,
    terminal_id: int,
    attendant_id: int,
    amount: int,
    key: str,
    expected_card_hash: str | None = None,
    expected_terminal_key: str | None = None,
):
    if amount <= 0:
        raise PaymentError("Amount must be positive")

    # Fail closed for all callers, including direct Python calls.
    # Demo and test modes must not bypass terminal authentication.
    if (
        not isinstance(expected_terminal_key, str)
        or not expected_terminal_key
        or len(expected_terminal_key) > 300
    ):
        raise PaymentError("Invalid terminal credentials")

    with db.begin():
        ensure_unique_key(db, key)

        wallet = get_locked_wallet(db, wallet_id)

        # Lock student and card before payment authorization.
        # Card-management operations also lock the student.
        student = db.scalar(
            select(Student)
            .where(Student.id == student_id)
            .with_for_update()
        )

        card = db.scalar(
            select(Card)
            .where(Card.id == card_id)
            .with_for_update()
        )

        # Revalidate after acquiring the payment locks.
        # Credential rotation/revocation locks this same row.
        if expected_terminal_key is not None:
            try:
                key_terminal_id, secret = expected_terminal_key.split(
                    ".", 1
                )
                valid_prefix = int(key_terminal_id) == terminal_id
            except (ValueError, AttributeError):
                valid_prefix = False
                secret = ""

            credential = db.scalar(
                select(TerminalCredential)
                .where(TerminalCredential.terminal_id == terminal_id)
                .with_for_update()
            )

            if (
                not valid_prefix
                or credential is None
                or not credential.is_active
                or not hmac.compare_digest(
                    credential.secret_hash,
                    hash_terminal_secret(secret),
                )
            ):
                raise PaymentError("Invalid terminal credentials")

        terminal = db.get(CanteenTerminal, terminal_id)
        attendant = db.get(User, attendant_id)

        if (
            student is None
            or not student.is_active
            or student.id != wallet.student_id
        ):
            raise PaymentError("Invalid student")

        if (
            card is None
            or card.student_id != student.id
            or card.status != "active"
        ):
            raise PaymentError("Invalid or blocked card")

        # Verify the credential again after acquiring row locks.
        # This closes the gap between initial lookup and payment.
        if expected_card_hash is not None:
            if not hmac.compare_digest(
                card.card_token_hash,
                expected_card_hash,
            ):
                raise PaymentError("Invalid card credential")

        if (
            terminal is None
            or not terminal.is_active
            or terminal.school_id != student.school_id
        ):
            raise PaymentError("Unauthorized canteen terminal")

        if (
            attendant is None
            or attendant.role != "canteen"
            or not attendant.is_active
            or attendant.school_id != student.school_id
        ):
            raise PaymentError("Unauthorized attendant")

        if wallet.balance < amount:
            raise PaymentError("Insufficient balance")

        liability = get_account(
            db,
            f"WALLET-{wallet.id}",
            f"Student Wallet {wallet.id}",
            "wallet_liability",
            wallet.id,
        )

        payable = get_account(
            db,
            "CANTEEN-PAYABLE-UGX",
            "Demo Canteen Payable",
            "canteen_payable",
        )

        transaction = Transaction(
            wallet_id=wallet.id,
            initiated_by=attendant.id,
            terminal_id=terminal.id,
            amount=amount,
            currency="UGX",
            transaction_type="purchase",
            status="completed",
            idempotency_key=key,
        )

        db.add(transaction)
        db.flush()

        post_entries(
            db, transaction, liability, payable, amount
        )

        wallet.balance -= amount
        db.flush()

        result = {
            "transaction_id": transaction.id,
            "amount": amount,
            "balance": wallet.balance,
        }

    return result



def process_scanned_card_purchase(
    db: Session,
    card_credential: str,
    terminal_id: int,
    attendant_id: int,
    amount: int,
    key: str,
    terminal_key: str | None = None,
):
    """
    Resolve a simulated card credential to its student wallet.

    Use a separate short-lived session for lookup, then revalidate
    the credential inside the locked financial transaction.
    """
    from app.database import SessionLocal

    if not isinstance(card_credential, str):
        raise PaymentError("Invalid card credential")

    if not re.fullmatch(
        r"SC1\.[A-Za-z0-9_-]{43}",
        card_credential,
    ):
        raise PaymentError("Invalid card credential")

    credential_hash = hashlib.sha256(
        card_credential.encode("utf-8")
    ).hexdigest()

    with SessionLocal() as lookup_db:
        card = lookup_db.scalar(
            select(Card).where(
                Card.card_token_hash == credential_hash
            )
        )

        if card is None:
            raise PaymentError("Invalid card credential")

        wallet = lookup_db.scalar(
            select(Wallet).where(
                Wallet.student_id == card.student_id
            )
        )

        if wallet is None:
            raise PaymentError("Invalid card credential")

        card_id = card.id
        student_id = card.student_id
        wallet_id = wallet.id

    # This function acquires wallet, student and card row locks.
    # The hash is checked again under those locks, preventing
    # a replaced credential from being accepted during a race.
    return process_canteen_purchase(
        db=db,
        wallet_id=wallet_id,
        student_id=student_id,
        card_id=card_id,
        terminal_id=terminal_id,
        attendant_id=attendant_id,
        amount=amount,
        key=key,
        expected_card_hash=credential_hash,
        expected_terminal_key=terminal_key,
    )



def process_canteen_purchase(
    db: Session,
    wallet_id: int,
    student_id: int,
    card_id: int,
    terminal_id: int,
    attendant_id: int,
    amount: int,
    key: str,
    expected_card_hash: str | None = None,
    expected_terminal_key: str | None = None,
):
    """
    Process a purchase and translate concurrent
    idempotency-key conflicts into PaymentError.

    PostgreSQL remains the final authority for
    idempotency-key uniqueness.
    """
    from sqlalchemy.exc import IntegrityError

    try:
        return _process_canteen_purchase_impl(
            db=db,
            wallet_id=wallet_id,
            student_id=student_id,
            card_id=card_id,
            terminal_id=terminal_id,
            attendant_id=attendant_id,
            amount=amount,
            key=key,
            expected_card_hash=expected_card_hash,
            expected_terminal_key=expected_terminal_key,
        )

    except IntegrityError as error:
        original_error = error.orig

        sqlstate = getattr(
            original_error, "sqlstate", None
        )

        diagnostic = getattr(
            original_error, "diag", None
        )

        constraint = getattr(
            diagnostic, "constraint_name", None
        )

        if (
            sqlstate == "23505"
            and constraint ==
            "transactions_idempotency_key_key"
        ):
            raise PaymentError(
                "Transaction key already used"
            ) from error

        # Other integrity failures indicate different
        # problems and must not be disguised as duplicates.
        raise
