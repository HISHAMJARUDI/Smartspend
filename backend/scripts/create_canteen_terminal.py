from sqlalchemy import select

from app.database import SessionLocal
from app.models.school import School
from app.models.canteen_terminal import CanteenTerminal


def main():
    print("SmartSpend — POS Terminal Registration")

    with SessionLocal() as db:
        school = db.get(School, 1)

        if school is None or not school.is_active:
            print("School 1 unavailable.")
            return

        code = "SSD001-POS001"

        existing = db.scalar(
            select(CanteenTerminal).where(
                CanteenTerminal.terminal_code == code
            )
        )

        if existing:
            print(f"Terminal already exists. ID: {existing.id}")
            return

        terminal = CanteenTerminal(
            school_id=school.id,
            terminal_code=code,
            name="Main School Canteen POS",
            is_active=True,
        )

        db.add(terminal)
        db.commit()
        db.refresh(terminal)

        print("Terminal registered successfully.")
        print(f"Terminal ID: {terminal.id}")
        print(f"Code: {terminal.terminal_code}")
        print(f"School ID: {terminal.school_id}")


if __name__ == "__main__":
    main()
