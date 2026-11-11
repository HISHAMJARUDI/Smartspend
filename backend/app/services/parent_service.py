from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.core.security import hash_password
from app.schemas.parent import ParentCreate


class ParentConflict(Exception):
    pass


def create_parent(db: Session, payload: ParentCreate) -> User:
    email = str(payload.email).strip().lower()

    existing = db.scalar(
        select(User).where(User.email == email)
    )

    if existing:
        raise ParentConflict("Email is already registered")

    parent = User(
        full_name=payload.full_name.strip(),
        email=email,
        phone=payload.phone.strip() if payload.phone else None,
        password_hash=hash_password(payload.password),
        role="parent",
        school_id=None,
        is_active=True,
    )

    db.add(parent)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ParentConflict(
            "Email or phone is already registered"
        )

    db.refresh(parent)
    return parent
