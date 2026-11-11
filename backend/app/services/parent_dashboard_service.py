from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.student import Student
from app.models.parent_student import ParentStudent
from app.models.wallet import Wallet
from app.models.transaction import Transaction


class ChildAccessDenied(Exception):
    pass


def list_parent_children(
    db: Session,
    parent_user_id: int,
):
    rows = db.execute(
        select(Student, User, Wallet)
        .join(
            ParentStudent,
            ParentStudent.student_id == Student.id,
        )
        .join(User, User.id == Student.user_id)
        .join(Wallet, Wallet.student_id == Student.id)
        .where(
            ParentStudent.parent_id == parent_user_id,
            Student.is_active.is_(True),
        )
        .order_by(Student.id)
    ).all()

    return [
        {
            "student_id": student.id,
            "full_name": user.full_name,
            "student_number": student.student_number,
            "class_name": student.class_name,
            "school_id": student.school_id,
            "wallet_id": wallet.id,
            "balance": wallet.balance,
            "currency": wallet.currency,
        }
        for student, user, wallet in rows
    ]


def get_child_transactions(
    db: Session,
    parent_user_id: int,
    student_id: int,
):
    wallet = db.scalar(
        select(Wallet)
        .join(Student, Student.id == Wallet.student_id)
        .join(
            ParentStudent,
            ParentStudent.student_id == Student.id,
        )
        .where(
            Student.id == student_id,
            Student.is_active.is_(True),
            ParentStudent.parent_id == parent_user_id,
        )
    )

    if wallet is None:
        raise ChildAccessDenied(
            "Child not found or access denied"
        )

    return db.scalars(
        select(Transaction)
        .where(Transaction.wallet_id == wallet.id)
        .order_by(
            Transaction.created_at.desc(),
            Transaction.id.desc(),
        )
        .limit(100)
    ).all()
