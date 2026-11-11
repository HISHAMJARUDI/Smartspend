from sqlalchemy import (
    Boolean, ForeignKey, String
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CanteenTerminal(Base):
    __tablename__ = "canteen_terminals"

    # PRIMARY KEY
    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    # FOREIGN KEY:
    # canteen_terminals.school_id -> schools.id
    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id"),
        nullable=False
    )

    terminal_code: Mapped[str] = mapped_column(
        String(60),
        unique=True,
        nullable=False
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
