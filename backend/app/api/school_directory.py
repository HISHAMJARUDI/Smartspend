from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.database import get_db
from app.models.school import School
from app.models.student import Student
from app.models.user import User
from app.models.wallet import Wallet

router = APIRouter(
    prefix="/admin/school-directory",
    tags=["Admin School Directory"],
)

system_admin_only = require_roles("system_admin")


@router.get("")
def school_directory(
    db: Session = Depends(get_db),
    admin: User = Depends(system_admin_only),
):
    counts = (
        select(
            Student.school_id.label("school_id"),
            func.count(Student.id).label("total_students"),
            func.count(Student.id)
            .filter(Student.is_active.is_(True))
            .label("active_students"),
        )
        .group_by(Student.school_id)
        .subquery()
    )

    statement = (
        select(
            School,
            func.coalesce(counts.c.total_students, 0),
            func.coalesce(counts.c.active_students, 0),
        )
        .outerjoin(counts, School.id == counts.c.school_id)
        .order_by(School.name, School.id)
    )

    rows = db.execute(statement).all()

    return [
        {
            "id": school.id,
            "name": school.name,
            "code": school.code,
            "is_active": school.is_active,
            "total_students": int(total),
            "active_students": int(active),
        }
        for school, total, active in rows
    ]


@router.get("/{school_id}/students")
def school_student_directory(
    school_id: int,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    admin: User = Depends(system_admin_only),
):
    school = db.get(School, school_id)

    if school is None:
        raise HTTPException(
            status_code=404,
            detail="School not found",
        )

    total = db.scalar(
        select(func.count(Student.id)).where(
            Student.school_id == school_id
        )
    ) or 0

    rows = db.execute(
        select(Student, User, Wallet)
        .join(User, Student.user_id == User.id)
        .outerjoin(Wallet, Wallet.student_id == Student.id)
        .where(Student.school_id == school_id)
        .order_by(Student.id)
        .limit(limit)
        .offset(offset)
    ).all()

    return {
        "school": {
            "id": school.id,
            "name": school.name,
            "code": school.code,
        },
        "total_students": total,
        "students": [
            {
                "id": student.id,
                "full_name": user.full_name,
                "student_number": student.student_number,
                "class_name": student.class_name,
                "school_id": student.school_id,
                "is_active": student.is_active,
                "wallet_balance": (
                    wallet.balance if wallet is not None else None
                ),
                "currency": (
                    wallet.currency if wallet is not None else None
                ),
            }
            for student, user, wallet in rows
        ],
    }
