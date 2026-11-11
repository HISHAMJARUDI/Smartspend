from uuid import uuid4

from sqlalchemy import select, func

from app.database import SessionLocal
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from app.models.user import User
from app.models.canteen_terminal import CanteenTerminal
from app.services.wallet_service import (
    process_canteen_purchase,
    PaymentError,
)


def main():
    with SessionLocal() as db:
        wallet = db.scalar(
            select(Wallet).where(Wallet.student_id == 1)
        )

        attendant = db.scalar(
            select(User).where(
                User.email == "canteen.demo@example.com"
            )
        )

        terminal = db.scalar(
            select(CanteenTerminal).where(
                CanteenTerminal.terminal_code == "SSD001-POS001"
            )
        )

        if not all([wallet, attendant, terminal]):
            raise RuntimeError("Missing demonstration records")

        initial_balance = wallet.balance
        initial_count = db.scalar(
            select(func.count(Transaction.id))
        )

        wallet_id = wallet.id
        attendant_id = attendant.id
        terminal_id = terminal.id

    rejected = False

    try:
        with SessionLocal() as db:
            process_canteen_purchase(
                db=db,
                wallet_id=wallet_id,
                student_id=1,
                card_id=1,  # Previously blocked card
                terminal_id=terminal_id,
                attendant_id=attendant_id,
                amount=1000,
                key=f"old-card-{uuid4()}",
            )

    except PaymentError as error:
        print(f"Old card rejected: {error}")
        rejected = True

    with SessionLocal() as db:
        current_balance = db.get(Wallet, wallet_id).balance
        current_count = db.scalar(
            select(func.count(Transaction.id))
        )

    assert rejected, "Blocked card was accepted!"
    assert current_balance == initial_balance
    assert current_count == initial_count

    print("PASS: Replaced card cannot make purchases")
    print("PASS: Wallet balance unchanged")
    print("PASS: No new financial transaction")
    print(f"Balance: UGX {current_balance:,}")


if __name__ == "__main__":
    main()
