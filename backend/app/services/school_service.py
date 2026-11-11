from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.school import School


class SchoolAlreadyExists(Exception):
    pass


def create_school(
    db: Session,
    name: str,
    code: str,
) -> School:

    code = code.strip().upper()
    name = name.strip()

    existing = db.scalar(
        select(School).where(School.code == code)
    )

    if existing:
        raise SchoolAlreadyExists(
            "A school with this code already exists"
        )

    school = School(
        name=name,
        code=code,
        is_active=True,
    )

    db.add(school)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise SchoolAlreadyExists(
            "A school with this code already exists"
        )

    db.refresh(school)

    return school


def list_schools(db: Session):
    return db.scalars(
        select(School).order_by(School.id)
    ).all()


def get_school(db: Session, school_id: int):
    return db.get(School, school_id)
