from sqlalchemy import (
    CheckConstraint, ForeignKey,
    String, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LedgerAccount(Base):
    __tablename__ = "ledger_accounts"

    # PRIMARY KEY
    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    account_code: Mapped[str] = mapped_column(
        String(80),
        unique=True,
        nullable=False
    )

    account_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    account_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    # FOREIGN KEY -> wallets.id
    # NULL for clearing and settlement accounts
    wallet_id: Mapped[int | None] = mapped_column(
        ForeignKey("wallets.id"),
        unique=True,
        nullable=True
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="UGX",
        nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "account_type IN "
            "('wallet_liability', 'funding_clearing', "
            "'canteen_payable')",
            name="ck_ledger_account_type"
        ),
        CheckConstraint(
            "(account_type = 'wallet_liability' "
            "AND wallet_id IS NOT NULL) OR "
            "(account_type <> 'wallet_liability' "
            "AND wallet_id IS NULL)",
            name="ck_ledger_wallet_type"
        ),
    )
