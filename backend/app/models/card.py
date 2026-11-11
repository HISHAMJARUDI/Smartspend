from sqlalchemy import Index
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey,
    String
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Card(Base):
    __tablename__ = "cards"

    # PRIMARY KEY
    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    # FOREIGN KEY: cards.student_id -> students.id
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        nullable=False
    )

    card_token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False
    )

    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'blocked', 'lost', 'expired')",
            name="ck_cards_status"
        ),
    )


# PostgreSQL permits multiple historical cards,
# but only one active card per student.
Index(
    "uq_cards_one_active_per_student",
    Card.student_id,
    unique=True,
    postgresql_where=(Card.status == "active"),
)
