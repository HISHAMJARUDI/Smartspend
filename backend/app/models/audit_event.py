from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
)

from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    # PRIMARY KEY
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    # FOREIGN KEY -> users.id
    # Nullable for unauthenticated or system events.
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    # FOREIGN KEY -> schools.id
    # Nullable for platform-wide security events.
    school_id: Mapped[int | None] = mapped_column(
        ForeignKey("schools.id"),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # Polymorphic reference, not a foreign key.
    entity_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    outcome: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    details: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


Index(
    "ix_audit_events_actor_created",
    AuditEvent.actor_id,
    AuditEvent.created_at,
)

Index(
    "ix_audit_events_school_created",
    AuditEvent.school_id,
    AuditEvent.created_at,
)
