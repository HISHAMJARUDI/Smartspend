from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User
from app.schemas.school import SchoolCreate, SchoolResponse
from app.services.school_service import (
    create_school,
    list_schools,
    get_school,
    SchoolAlreadyExists,
)


router = APIRouter(
    prefix="/schools",
    tags=["Schools"],
)

system_admin_only = require_roles("system_admin")


@router.post(
    "",
    response_model=SchoolResponse,
    status_code=201,
)
def register_school(
    payload: SchoolCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(system_admin_only),
):
    try:
        return create_school(
            db,
            name=payload.name,
            code=payload.code,
        )
    except SchoolAlreadyExists as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        )


@router.get("", response_model=list[SchoolResponse])
def get_all_schools(
    db: Session = Depends(get_db),
    admin: User = Depends(system_admin_only),
):
    return list_schools(db)


@router.get("/{school_id}", response_model=SchoolResponse)
def get_school_by_id(
    school_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(system_admin_only),
):
    school = get_school(db, school_id)

    if school is None:
        raise HTTPException(
            status_code=404,
            detail="School not found",
        )

    return school
