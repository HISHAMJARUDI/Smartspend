from uuid import uuid4

from sqlalchemy import select, func

from app.database import SessionLocal
from app.models.wallet import Wallet
from app.models.card import Card
from app.models.canteen_terminal import CanteenTerminal
from app.models.user import User
from app.models.transaction import Transaction
from app.services.wallet_service import (
    process_canteen_purchase,
    PaymentError,
)


def main():
    with SessionLocal() as db:
        wallet = db.scalar(
            select(Wallet).where(Wallet.student_id == 1)
        )

        card = db.scalar(
            select(Card).where(
                Card.student_id == 1,
                Card.status == "active"
            )
        )

        terminal = db.scalar(
            select(CanteenTerminal).where(
                CanteenTerminal.terminal_code == "SSD001-POS001"
            )
        )

        attendant = db.scalar(
            select(User).where(
                User.email == "canteen.demo@example.com"
            )
        )

        if not all([wallet, card, terminal, attendant]):
            raise RuntimeError("Missing demo test records")

        wallet_id = wallet.id
        card_id = card.id
        terminal_id = terminal.id
        attendant_id = attendant.id
        original_balance = wallet.balance

        transaction_count = db.scalar(
            select(func.count(Transaction.id))
        )

        original_status = card.status

    try:
        # Temporarily block the student card.
        with SessionLocal.begin() as db:
            card = db.get(Card, card_id)
            card.status = "blocked"

        print("Card status: BLOCKED")

        # Attempt a payment with the blocked card.
        rejected = False

        try:
            with SessionLocal() as db:
                process_canteen_purchase(
                    db=db,
                    wallet_id=wallet_id,
                    student_id=1,
                    card_id=card_id,
                    terminal_id=terminal_id,
                    attendant_id=attendant_id,
                    amount=2000,
                    key=f"blocked-test-{uuid4()}",
                )

        except PaymentError as error:
            print(f"Purchase rejected: {error}")
            rejected = True

        # Verify no money was deducted.
        with SessionLocal() as db:
            balance = db.get(Wallet, wallet_id).balance

            new_count = db.scalar(
                select(func.count(Transaction.id))
            )

        assert rejected, "Blocked card purchase was approved!"
        assert balance == original_balance, "Wallet changed!"
        assert new_count == transaction_count, "Transaction was created!"

        print("PASS: Blocked card cannot make purchases")
        print("PASS: Wallet balance unchanged")
        print("PASS: No additional transaction created")
        print(f"Balance: UGX {balance:,}")

    finally:
        # Restore the card to its previous status.
        with SessionLocal.begin() as db:
            card = db.get(Card, card_id)
            card.status = original_status

        print(f"Card restored to: {original_status}")


if __name__ == "__main__":
    main()
