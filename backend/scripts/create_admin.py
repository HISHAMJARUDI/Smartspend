import getpass
import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models.user import User
from app.core.security import hash_password


def main():
    print("SmartSpend: Initial Administrator Setup")

    with SessionLocal() as db:
        existing_admin = db.scalar(
            select(User).where(User.role == "system_admin")
        )

        if existing_admin:
            print("A system administrator already exists.")
            sys.exit(1)

        name = input("Full name: ").strip()
        email = input("Email: ").strip().lower()
        password = getpass.getpass("Password: ")
        confirmation = getpass.getpass("Confirm password: ")

        if not name or not email or "@" not in email:
            print("Valid name and email are required.")
            sys.exit(1)

        if len(password) < 12:
            print("Password must contain at least 12 characters.")
            sys.exit(1)

        if password != confirmation:
            print("Passwords do not match.")
            sys.exit(1)

        if db.scalar(select(User).where(User.email == email)):
            print("Email already registered.")
            sys.exit(1)

        admin = User(
            full_name=name,
            email=email,
            password_hash=hash_password(password),
            role="system_admin",
            school_id=None,
            is_active=True,
        )

        db.add(admin)
        db.commit()
        db.refresh(admin)

        print(f"Administrator created successfully. ID: {admin.id}")


if __name__ == "__main__":
    main()
