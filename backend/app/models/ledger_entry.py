from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, CheckConstraint, DateTime,
    ForeignKey, String
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    # PRIMARY KEY
    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    # FOREIGN KEY -> transactions.id
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id"),
        nullable=False
    )

    # FOREIGN KEY -> ledger_accounts.id
    account_id: Mapped[int] = mapped_column(
        ForeignKey("ledger_accounts.id"),
        nullable=False
    )

    entry_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )

    amount: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('debit', 'credit')",
            name="ck_ledger_entry_type"
        ),
        CheckConstraint(
            "amount > 0",
            name="ck_ledger_entry_positive"
        ),
    )
