from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, CheckConstraint, DateTime,
    ForeignKey, String
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    # PRIMARY KEY
    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    # FOREIGN KEY -> wallets.id
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id"),
        nullable=False
    )

    # FOREIGN KEY -> users.id
    initiated_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )

    # FOREIGN KEY -> canteen_terminals.id
    # NULL for deposits
    terminal_id: Mapped[int | None] = mapped_column(
        ForeignKey("canteen_terminals.id"),
        nullable=True
    )

    amount: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="UGX",
        nullable=False
    )

    transaction_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_transaction_positive_amount"
        ),
        CheckConstraint(
            "transaction_type IN "
            "('deposit', 'purchase', 'refund')",
            name="ck_transaction_type"
        ),
        CheckConstraint(
            "status IN "
            "('pending', 'completed', 'failed', 'reversed')",
            name="ck_transaction_status"
        ),
    )
