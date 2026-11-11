import hashlib
import secrets

from sqlalchemy import select

from app.database import SessionLocal
from app.models.student import Student
from app.models.card import Card


def main():
    print("SmartSpend — Demo Card Issuance")

    with SessionLocal() as db:
        student = db.get(Student, 1)

        if student is None or not student.is_active:
            print("Student 1 unavailable.")
            return

        existing = db.scalar(
            select(Card).where(
                Card.student_id == student.id,
                Card.status == "active",
            )
        )

        if existing:
            print(f"Student already has an active card.")
            print(f"Card ID: {existing.id}")
            return

        raw_token = secrets.token_urlsafe(32)

        token_hash = hashlib.sha256(
            raw_token.encode("utf-8")
        ).hexdigest()

        card = Card(
            student_id=student.id,
            card_token_hash=token_hash,
            status="active",
        )

        db.add(card)
        db.commit()
        db.refresh(card)

        print("Demo card issued successfully.")
        print(f"Card ID: {card.id}")
        print(f"Student ID: {card.student_id}")
        print(f"Status: {card.status}")
        print("Keep raw card credentials out of logs and chat.")


if __name__ == "__main__":
    main()
