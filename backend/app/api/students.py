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

system_admin_only = require_roles("system_admin")


@router.post(
    "",
    response_model=StudentResponse,
    status_code=201,
)
def register_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(system_admin_only),
):
    try:
        return create_student(db, payload)

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
