import getpass

from sqlalchemy import select

from app.database import SessionLocal
from app.models.school import School
from app.models.user import User
from app.core.security import hash_password


def main():
    print("SmartSpend — Canteen Attendant Setup")

    with SessionLocal() as db:
        school = db.get(School, 1)

        if school is None or not school.is_active:
            print("School 1 not found or inactive.")
            return

        email = "canteen.demo@example.com"

        existing = db.scalar(
            select(User).where(User.email == email)
        )

        if existing:
            print(f"Attendant already exists. ID: {existing.id}")
            return

        password = getpass.getpass(
            "Create canteen attendant password: "
        )

        if len(password) < 12:
            print("Password must have at least 12 characters.")
            return

        attendant = User(
            full_name="SmartSpend Canteen Attendant",
            email=email,
            password_hash=hash_password(password),
            role="canteen",
            school_id=school.id,
            is_active=True,
        )

        db.add(attendant)
        db.commit()
        db.refresh(attendant)

        print("Canteen attendant created successfully.")
        print(f"User ID: {attendant.id}")
        print(f"School ID: {attendant.school_id}")
        print(f"Role: {attendant.role}")


if __name__ == "__main__":
    main()
