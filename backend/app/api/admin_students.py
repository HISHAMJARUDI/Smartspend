from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.database import get_db
from app.models.user import User
from app.models.student import Student
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from app.models.card import Card
from app.schemas.wallet import TransactionResponse
from app.schemas.card import CardResponse

router = APIRouter(
    prefix="/admin/students",
    tags=["Admin Student Management"],
)

admin_only = require_roles("school_admin", "system_admin")


class AdminStudentResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    student_number: str
    class_name: str | None
    school_id: int
    is_active: bool
    wallet_id: int | None
    wallet_balance: int | None
    currency: str | None
    wallet_active: bool | None


def scoped_query(statement, admin: User):
    if admin.role == "school_admin":
        if admin.school_id is None:
            raise HTTPException(
                status_code=403,
                detail="Administrator has no assigned school",
            )
        statement = statement.where(
            Student.school_id == admin.school_id
        )
    return statement


def base_query():
    return (
        select(Student, User, Wallet)
        .join(User, User.id == Student.user_id)
        .outerjoin(Wallet, Wallet.student_id == Student.id)
    )


def serialize(student, user, wallet):
    return AdminStudentResponse(
        id=student.id,
        user_id=user.id,
        full_name=user.full_name,
        student_number=student.student_number,
        class_name=student.class_name,
        school_id=student.school_id,
        is_active=student.is_active and user.is_active,
        wallet_id=wallet.id if wallet else None,
        wallet_balance=wallet.balance if wallet else None,
        currency=wallet.currency if wallet else None,
        wallet_active=wallet.is_active if wallet else None,
    )


def authorized_student(db, student_id, admin):
    statement = scoped_query(
        base_query().where(Student.id == student_id),
        admin,
    )
    result = db.execute(statement).one_or_none()

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Student not found",
        )
    return result


@router.get("", response_model=list[AdminStudentResponse])
def list_students(
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    admin: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    statement = scoped_query(base_query(), admin)

    if q and q.strip():
        search = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                User.full_name.ilike(search),
                Student.student_number.ilike(search),
            )
        )

    rows = db.execute(
        statement.order_by(User.full_name, Student.id).limit(limit)
    ).all()

    return [serialize(s, u, w) for s, u, w in rows]


@router.get("/{student_id}", response_model=AdminStudentResponse)
def get_student(
    student_id: int,
    admin: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return serialize(*authorized_student(db, student_id, admin))


@router.get(
    "/{student_id}/transactions",
    response_model=list[TransactionResponse],
)
def get_transactions(
    student_id: int,
    admin: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    student, user, wallet = authorized_student(
        db, student_id, admin
    )

    if wallet is None:
        return []

    return db.scalars(
        select(Transaction)
        .where(Transaction.wallet_id == wallet.id)
        .order_by(
            Transaction.created_at.desc(),
            Transaction.id.desc(),
        )
        .limit(100)
    ).all()


@router.get(
    "/{student_id}/cards",
    response_model=list[CardResponse],
)
def get_cards(
    student_id: int,
    admin: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    authorized_student(db, student_id, admin)

    return db.scalars(
        select(Card)
        .where(Card.student_id == student_id)
        .order_by(Card.issued_at.desc(), Card.id.desc())
    ).all()
