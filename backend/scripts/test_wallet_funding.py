from uuid import uuid4

from sqlalchemy import select

from app.database import SessionLocal
from app.models.wallet import Wallet
from app.services.wallet_service import (
    demo_fund_wallet,
    PaymentError,
)


def main():
    with SessionLocal() as db:
        wallet = db.scalar(
            select(Wallet).where(Wallet.student_id == 1)
        )

        if wallet is None:
            print("Student wallet not found")
            return

        wallet_id = wallet.id

    try:
        with SessionLocal() as db:
            result = demo_fund_wallet(
                db=db,
                wallet_id=wallet_id,
                admin_id=1,
                amount=50000,
                key=f"demo-funding-{uuid4()}",
            )

        print("DEMO funding successful")
        print(f"Transaction ID: {result['transaction_id']}")
        print(f"Amount: UGX {result['amount']:,}")
        print(f"New balance: UGX {result['balance']:,}")

    except PaymentError as error:
        print(f"Funding rejected: {error}")


if __name__ == "__main__":
    main()
