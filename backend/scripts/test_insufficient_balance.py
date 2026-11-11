from uuid import uuid4

from sqlalchemy import select

from app.database import SessionLocal
from app.models.wallet import Wallet
from app.models.card import Card
from app.models.canteen_terminal import CanteenTerminal
from app.models.user import User
from app.services.wallet_service import (
    process_canteen_purchase,
    PaymentError,
)


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
        raise SystemExit("Missing test records")

    wallet_id = wallet.id
    card_id = card.id
    terminal_id = terminal.id
    attendant_id = attendant.id
    original_balance = wallet.balance


try:
    with SessionLocal() as db:
        process_canteen_purchase(
            db=db,
            wallet_id=wallet_id,
            student_id=1,
            card_id=card_id,
            terminal_id=terminal_id,
            attendant_id=attendant_id,
            amount=1000000,
            key=f"insufficient-test-{uuid4()}",
        )

    raise SystemExit("ERROR: Oversized purchase was approved")

except PaymentError as error:
    print(f"Expected rejection: {error}")


with SessionLocal() as db:
    current_balance = db.get(Wallet, wallet_id).balance

assert current_balance == original_balance

print("PASS: Wallet balance was not changed")
