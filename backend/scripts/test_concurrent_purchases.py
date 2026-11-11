from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from uuid import uuid4

from sqlalchemy import select, func

from app.database import SessionLocal
from app.models.wallet import Wallet
from app.models.card import Card
from app.models.canteen_terminal import CanteenTerminal
from app.models.user import User
from app.models.transaction import Transaction
from app.models.ledger_account import LedgerAccount
from app.models.ledger_entry import LedgerEntry
from app.services.wallet_service import (
    process_canteen_purchase,
    PaymentError,
)


PURCHASE_AMOUNT = 25000
barrier = Barrier(2)
print_lock = Lock()


def attempt_purchase(name, ids, key):
    # Each thread gets its own SQLAlchemy session.
    barrier.wait(timeout=10)

    try:
        with SessionLocal() as db:
            result = process_canteen_purchase(
                db=db,
                wallet_id=ids["wallet_id"],
                student_id=ids["student_id"],
                card_id=ids["card_id"],
                terminal_id=ids["terminal_id"],
                attendant_id=ids["attendant_id"],
                amount=PURCHASE_AMOUNT,
                key=key,
            )

        with print_lock:
            print(
                f"{name}: APPROVED | "
                f"Transaction {result['transaction_id']} | "
                f"Balance UGX {result['balance']:,}"
            )

        return ("approved", result)

    except PaymentError as error:
        with print_lock:
            print(f"{name}: DECLINED | {error}")

        return ("declined", str(error))


def main():
    print("SmartSpend — Concurrent Purchase Test")

    # Load configuration and snapshot the initial state.
    with SessionLocal() as db:
        wallet = db.scalar(
            select(Wallet).where(Wallet.student_id == 1)
        )

        card = db.scalar(
            select(Card).where(
                Card.student_id == 1,
                Card.status == "active",
            )
        )

        terminal = db.scalar(
            select(CanteenTerminal).where(
                CanteenTerminal.terminal_code
                == "SSD001-POS001"
            )
        )

        attendant = db.scalar(
            select(User).where(
                User.email == "canteen.demo@example.com",
                User.role == "canteen",
            )
        )

        if not all([wallet, card, terminal, attendant]):
            raise SystemExit("Missing required test records")

        if wallet.balance != 37000:
            raise SystemExit(
                f"Test stopped: expected UGX 37,000, "
                f"found UGX {wallet.balance:,}. "
                "No payment was attempted."
            )

        ids = {
            "wallet_id": wallet.id,
            "student_id": wallet.student_id,
            "card_id": card.id,
            "terminal_id": terminal.id,
            "attendant_id": attendant.id,
        }

        before_balance = wallet.balance

        before_count = db.scalar(
            select(func.count(Transaction.id))
        )

    print(f"Starting balance: UGX {before_balance:,}")
    print("Launching two UGX 25,000 purchases...")

    # Use different keys because these represent
    # two independent purchase requests.
    key_a = f"concurrency-a-{uuid4()}"
    key_b = f"concurrency-b-{uuid4()}"

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(
            attempt_purchase, "Purchase A", ids, key_a
        )
        future_b = executor.submit(
            attempt_purchase, "Purchase B", ids, key_b
        )

        results = [
            future_a.result(),
            future_b.result(),
        ]

    approved = sum(r[0] == "approved" for r in results)
    declined = sum(r[0] == "declined" for r in results)

    with SessionLocal() as db:
        wallet = db.get(Wallet, ids["wallet_id"])
        after_balance = wallet.balance

        after_count = db.scalar(
            select(func.count(Transaction.id))
        )

        account = db.scalar(
            select(LedgerAccount).where(
                LedgerAccount.wallet_id == wallet.id
            )
        )

        assert account is not None

        ledger_balance = db.scalar(
            select(
                func.coalesce(
                    func.sum(
                        LedgerEntry.amount
                    ).filter(
                        LedgerEntry.account_id == account.id,
                        LedgerEntry.entry_type == "credit",
                    ),
                    0,
                )
            )
        )

        ledger_debits = db.scalar(
            select(
                func.coalesce(
                    func.sum(LedgerEntry.amount),
                    0,
                )
            ).where(
                LedgerEntry.account_id == account.id,
                LedgerEntry.entry_type == "debit",
            )
        )

        ledger_balance -= ledger_debits

    print("\n--- TEST RESULTS ---")
    print(f"Approved: {approved}")
    print(f"Declined: {declined}")
    print(f"Final balance: UGX {after_balance:,}")
    print(f"Ledger balance: UGX {ledger_balance:,}")

    assert approved == 1, "Expected one approved purchase"
    assert declined == 1, "Expected one declined purchase"
    assert after_balance == 12000, "Unexpected wallet balance"
    assert ledger_balance == after_balance, "Ledger mismatch"
    assert after_count == before_count + 1, (
        "Unexpected number of transactions"
    )

    print("\nPASS: No double spending")
    print("PASS: Exactly one purchase completed")
    print("PASS: Wallet and ledger balances agree")


if __name__ == "__main__":
    main()
