from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, String
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TerminalCredential(Base):
    __tablename__ = "terminal_credentials"

    # PRIMARY KEY
    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    # FOREIGN KEY -> canteen_terminals.id
    terminal_id: Mapped[int] = mapped_column(
        ForeignKey("canteen_terminals.id"),
        unique=True,
        nullable=False
    )

    secret_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
