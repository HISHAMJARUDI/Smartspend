from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.student import Student
from app.models.wallet import Wallet
from app.models.transaction import Transaction


class WalletNotFound(Exception):
    pass


def get_student_wallet(db: Session, user_id: int):
    student = db.scalar(
        select(Student).where(
            Student.user_id == user_id,
            Student.is_active.is_(True),
        )
    )

    if student is None:
        raise WalletNotFound("Student profile unavailable")

    wallet = db.scalar(
        select(Wallet).where(
            Wallet.student_id == student.id
        )
    )

    if wallet is None:
        raise WalletNotFound("Student wallet unavailable")

    return wallet


def get_wallet_transactions(
    db: Session,
    wallet_id: int,
):
    return db.scalars(
        select(Transaction)
        .where(Transaction.wallet_id == wallet_id)
        .order_by(
            Transaction.created_at.desc(),
            Transaction.id.desc(),
        )
        .limit(100)
    ).all()
