import secrets

from sqlalchemy import or_, select
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

    student_number = payload.student_number.strip()
    full_name = payload.full_name.strip()

    if not student_number or not full_name:
        raise StudentValidationError(
            "Student name and number are required"
        )

    existing_student = db.scalar(
        select(Student).where(
            Student.school_id == payload.school_id,
            Student.student_number == student_number,
        )
    )

    if existing_student is not None:
        raise StudentConflict(
            "Student number already exists in this school"
        )

    student_email = (
        str(payload.email).strip().lower()
        if payload.email is not None else None
    )

    if student_email:
        existing_user = db.scalar(
            select(User).where(User.email == student_email)
        )
        if existing_user is not None:
            raise StudentConflict(
                "Student email is already registered"
            )

    try:
        if payload.parent_id is not None:
            # Explicitly selected existing parent.
            parent = db.get(User, payload.parent_id)

            if (
                parent is None
                or parent.role != "parent"
                or not parent.is_active
            ):
                raise StudentValidationError(
                    "A valid active parent account is required"
                )

        else:
            # New parent created within student enrollment.
            details = payload.new_parent
            if details is None:
                raise StudentValidationError(
                    "Parent information is required"
                )

            parent_email = str(details.email).strip().lower()
            parent_phone = (
                details.phone.strip()
                if details.phone else None
            ) or None

            if student_email == parent_email:
                raise StudentValidationError(
                    "Parent and student cannot share an email"
                )

            conditions = [User.email == parent_email]

            if parent_phone:
                conditions.append(User.phone == parent_phone)

            existing_parent_or_user = db.scalar(
                select(User).where(or_(*conditions))
            )

            if existing_parent_or_user is not None:
                raise StudentConflict(
                    "An account already uses this parent email "
                    "or phone. Select the existing parent instead."
                )

            # A random, undisclosed credential prevents staff
            # from knowing or choosing a parent's password.
            # Secure password setup/invitation comes later.
            parent = User(
                full_name=details.full_name.strip(),
                email=parent_email,
                phone=parent_phone,
                password_hash=hash_password(
                    secrets.token_urlsafe(48)
                ),
                role="parent",
                school_id=None,
                is_active=True,
            )

            db.add(parent)
            db.flush()

        # Maintain the current User -> Student relationship.
        # New students have no usable password supplied to staff.
        user = User(
            full_name=full_name,
            email=student_email,
            password_hash=hash_password(
                payload.password
                if payload.password is not None
                else secrets.token_urlsafe(48)
            ),
            role="student",
            school_id=school.id,
            is_active=True,
        )
        db.add(user)
        db.flush()

        student = Student(
            user_id=user.id,
            school_id=school.id,
            student_number=student_number,
            class_name=payload.class_name,
            is_active=True,
        )
        db.add(student)
        db.flush()

        db.add(
            ParentStudent(
                parent_id=parent.id,
                student_id=student.id,
            )
        )

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
            "Registration conflicts with an existing record"
        )

    except Exception:
        db.rollback()
        raise
