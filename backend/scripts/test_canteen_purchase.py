from uuid import uuid4

from sqlalchemy import select

from app.database import SessionLocal
from app.models.wallet import Wallet
from app.models.student import Student
from app.models.user import User
from app.models.card import Card
from app.models.canteen_terminal import CanteenTerminal
from app.models.transaction import Transaction
from app.services.wallet_service import (
    process_canteen_purchase,
    PaymentError,
)


def main():
    print("SmartSpend — First Canteen Purchase Test")

    with SessionLocal() as db:
        student = db.scalar(
            select(Student).where(
                Student.student_number == "STU001",
                Student.school_id == 1,
            )
        )

        if student is None:
            print("Student not found.")
            return

        wallet = db.scalar(
            select(Wallet).where(
                Wallet.student_id == student.id
            )
        )

        card = db.scalar(
            select(Card).where(
                Card.student_id == student.id,
                Card.status == "active",
            )
        )

        terminal = db.scalar(
            select(CanteenTerminal).where(
                CanteenTerminal.terminal_code == "SSD001-POS001"
            )
        )

        attendant = db.scalar(
            select(User).where(
                User.email == "canteen.demo@example.com",
                User.role == "canteen",
            )
        )

        if not all([wallet, card, terminal, attendant]):
            print("Missing wallet, card, terminal or attendant.")
            return

        previous_purchase = db.scalar(
            select(Transaction).where(
                Transaction.wallet_id == wallet.id,
                Transaction.transaction_type == "purchase",
                Transaction.status == "completed",
            )
        )

        if previous_purchase is not None:
            print("A completed purchase already exists.")
            print("Skipping to avoid an unintended extra charge.")
            return

        wallet_id = wallet.id
        student_id = student.id
        card_id = card.id
        terminal_id = terminal.id
        attendant_id = attendant.id

        print(f"Starting balance: UGX {wallet.balance:,}")

    try:
        with SessionLocal() as db:
            result = process_canteen_purchase(
                db=db,
                wallet_id=wallet_id,
                student_id=student_id,
                card_id=card_id,
                terminal_id=terminal_id,
                attendant_id=attendant_id,
                amount=8000,
                key=f"demo-purchase-{uuid4()}",
            )

        print("PURCHASE APPROVED")
        print(f"Transaction ID: {result['transaction_id']}")
        print(f"Purchase amount: UGX {result['amount']:,}")
        print(f"Remaining balance: UGX {result['balance']:,}")

    except PaymentError as error:
        print(f"PURCHASE DECLINED: {error}")


if __name__ == "__main__":
    main()
