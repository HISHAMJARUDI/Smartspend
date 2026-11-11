from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User
from app.schemas.parent import ParentCreate
from app.schemas.auth import UserResponse
from app.services.parent_service import (
    create_parent,
    ParentConflict,
)


router = APIRouter(
    prefix="/parents",
    tags=["Parents"],
)

system_admin_only = require_roles("system_admin")


@router.post(
    "",
    response_model=UserResponse,
    status_code=201,
)
def register_parent(
    payload: ParentCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(system_admin_only),
):
    try:
        return create_parent(db, payload)
    except ParentConflict as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        )
