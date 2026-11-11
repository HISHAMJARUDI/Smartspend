from sqlalchemy import (
    Boolean, ForeignKey, String, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Student(Base):
    __tablename__ = "students"

    # PRIMARY KEY
    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    # FOREIGN KEY: students.user_id -> users.id
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        unique=True,
        nullable=False
    )

    # FOREIGN KEY: students.school_id -> schools.id
    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id"),
        nullable=False
    )

    student_number: Mapped[str] = mapped_column(
        String(50), nullable=False
    )

    class_name: Mapped[str | None] = mapped_column(
        String(50)
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "school_id",
            "student_number",
            name="uq_student_school_number"
        ),
    )
