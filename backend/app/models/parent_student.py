from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ParentStudent(Base):
    __tablename__ = "parent_students"

    # PRIMARY KEY
    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    # FOREIGN KEY: parent_students.parent_id -> users.id
    parent_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )

    # FOREIGN KEY: parent_students.student_id -> students.id
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "parent_id",
            "student_id",
            name="uq_parent_student"
        ),
    )
