from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User
from app.schemas.student import (
    StudentCreate,
    StudentResponse,
)
from app.services.student_service import (
    create_student,
    StudentValidationError,
    StudentConflict,
)


router = APIRouter(
    prefix="/students",
    tags=["Students"],
)

admin_only = require_roles("school_admin", "system_admin")


@router.post(
    "",
    response_model=StudentResponse,
    status_code=201,
)
def register_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_only),
):
    try:
        if admin.role == "school_admin":
            if admin.school_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Administrator has no assigned school",
                )
            if payload.school_id != admin.school_id:
                raise HTTPException(
                    status_code=403,
                    detail="Cannot register students in another school",
                )

        return create_student(
            db,
            payload,
            allowed_school_id=(
                admin.school_id
                if admin.role == "school_admin"
                else None
            ),
        )

    except StudentValidationError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except StudentConflict as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        )
