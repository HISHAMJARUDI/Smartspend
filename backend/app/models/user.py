from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime,
    ForeignKey, String
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    # PRIMARY KEY
    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    full_name: Mapped[str] = mapped_column(
        String(150), nullable=False
    )

    email: Mapped[str | None] = mapped_column(
        String(255), unique=True
    )

    phone: Mapped[str | None] = mapped_column(
        String(30), unique=True
    )

    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    role: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    # FOREIGN KEY: users.school_id -> schools.id
    school_id: Mapped[int | None] = mapped_column(
        ForeignKey("schools.id"),
        nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('parent', 'student', 'canteen', "
            "'school_admin', 'system_admin')",
            name="ck_users_role"
        ),
    )
