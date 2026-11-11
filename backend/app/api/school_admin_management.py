from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, SecretStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.core.security import hash_password
from app.database import get_db
from app.models.school import School
from app.models.user import User
from app.services.audit_service import record_audit_event


router = APIRouter(
    prefix="/admin/school-admins",
    tags=["School Administrator Management"],
)

system_admin_only = require_roles("system_admin")


class SchoolAdminCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    school_id: int = Field(gt=0)
    temporary_password: SecretStr = Field(
        min_length=12,
    )


class SchoolAdminResponse(BaseModel):
    id: int
    full_name: str
    email: str
    school_id: int
    role: str
    is_active: bool


def serialize_admin(user: User) -> SchoolAdminResponse:
    return SchoolAdminResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        school_id=user.school_id,
        role=user.role,
        is_active=user.is_active,
    )


@router.post(
    "",
    response_model=SchoolAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_school_admin(
    payload: SchoolAdminCreate,
    actor: User = Depends(system_admin_only),
    db: Session = Depends(get_db),
):
    school = db.get(School, payload.school_id)

    if school is None or not school.is_active:
        raise HTTPException(
            status_code=400,
            detail="School does not exist or is inactive",
        )

    email = str(payload.email).strip().lower()

    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(
            status_code=409,
            detail="Email already registered",
        )

    try:
        admin = User(
            full_name=payload.full_name.strip(),
            email=email,
            phone=None,
            password_hash=hash_password(
                payload.temporary_password.get_secret_value()
            ),
            role="school_admin",
            school_id=school.id,
            is_active=True,
        )

        db.add(admin)
        db.flush()

        record_audit_event(
            db,
            action="school_admin.created",
            entity_type="user",
            entity_id=admin.id,
            actor_id=actor.id,
            school_id=school.id,
            outcome="success",
        )

        db.commit()
        db.refresh(admin)

        return serialize_admin(admin)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Account conflicts with an existing record",
        )

    except Exception:
        db.rollback()
        raise


@router.get(
    "",
    response_model=list[SchoolAdminResponse],
)
def list_school_admins(
    actor: User = Depends(system_admin_only),
    db: Session = Depends(get_db),
):
    admins = db.scalars(
        select(User)
        .where(User.role == "school_admin")
        .order_by(User.id)
        .limit(500)
    ).all()

    return [serialize_admin(admin) for admin in admins]


@router.post(
    "/{admin_id}/deactivate",
    response_model=SchoolAdminResponse,
)
def deactivate_school_admin(
    admin_id: int,
    actor: User = Depends(system_admin_only),
    db: Session = Depends(get_db),
):
    try:
        admin = db.scalar(
            select(User)
            .where(
                User.id == admin_id,
                User.role == "school_admin",
            )
            .with_for_update()
        )

        if admin is None:
            raise HTTPException(
                status_code=404,
                detail="School administrator not found",
            )

        if not admin.is_active:
            raise HTTPException(
                status_code=409,
                detail="Administrator is already deactivated",
            )

        admin.is_active = False

        record_audit_event(
            db,
            action="school_admin.deactivated",
            entity_type="user",
            entity_id=admin.id,
            actor_id=actor.id,
            school_id=admin.school_id,
            outcome="success",
        )

        db.commit()
        db.refresh(admin)

        return serialize_admin(admin)

    except Exception:
        db.rollback()
        raise
