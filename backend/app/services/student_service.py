from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.school import School
from app.models.user import User
from app.models.student import Student
from app.models.parent_student import ParentStudent
from app.models.wallet import Wallet
from app.schemas.student import StudentCreate


class StudentValidationError(Exception):
    pass


class StudentConflict(Exception):
    pass


def create_student(db: Session, payload: StudentCreate):
    school = db.get(School, payload.school_id)

    if school is None or not school.is_active:
        raise StudentValidationError(
            "School does not exist or is inactive"
        )

    parent = db.get(User, payload.parent_id)

    if (
        parent is None
        or parent.role != "parent"
        or not parent.is_active
    ):
        raise StudentValidationError(
            "A valid active parent account is required"
        )

    email = str(payload.email).strip().lower()
    student_number = payload.student_number.strip()

    if not student_number:
        raise StudentValidationError(
            "Student number cannot be empty"
        )

    existing_email = db.scalar(
        select(User).where(User.email == email)
    )

    if existing_email:
        raise StudentConflict("Email is already registered")

    existing_student = db.scalar(
        select(Student).where(
            Student.school_id == payload.school_id,
            Student.student_number == student_number,
        )
    )

    if existing_student:
        raise StudentConflict(
            "Student number already exists in this school"
        )

    try:
        # Create the student's login account.
        user = User(
            full_name=payload.full_name.strip(),
            email=email,
            password_hash=hash_password(payload.password),
            role="student",
            school_id=school.id,
            is_active=True,
        )
        db.add(user)
        db.flush()

        # Create the student profile.
        student = Student(
            user_id=user.id,
            school_id=school.id,
            student_number=student_number,
            class_name=payload.class_name,
            is_active=True,
        )
        db.add(student)
        db.flush()

        # Link the student to the parent.
        parent_link = ParentStudent(
            parent_id=parent.id,
            student_id=student.id,
        )
        db.add(parent_link)

        # Automatically create a zero-balance wallet.
        wallet = Wallet(
            student_id=student.id,
            balance=0,
            currency="UGX",
            is_active=True,
        )
        db.add(wallet)
        db.flush()

        result = {
            "id": student.id,
            "user_id": user.id,
            "full_name": user.full_name,
            "school_id": student.school_id,
            "student_number": student.student_number,
            "class_name": student.class_name,
            "parent_id": parent.id,
            "wallet_id": wallet.id,
            "wallet_balance": wallet.balance,
            "currency": wallet.currency,
        }

        db.commit()
        return result

    except IntegrityError:
        db.rollback()
        raise StudentConflict(
            "Student registration conflicts with an existing record"
        )

    except Exception:
        db.rollback()
        raise
