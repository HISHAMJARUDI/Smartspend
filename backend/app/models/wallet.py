from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint,
    ForeignKey, String
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Wallet(Base):
    __tablename__ = "wallets"

    # PRIMARY KEY
    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    # FOREIGN KEY: wallets.student_id -> students.id
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        unique=True,
        nullable=False
    )

    balance: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="UGX",
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "balance >= 0",
            name="ck_wallet_nonnegative"
        ),
    )
