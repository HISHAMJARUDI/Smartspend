import argparse
import hashlib
import secrets

from sqlalchemy import select

from app.database import SessionLocal
from app.models.card import Card
from app.models.student import Student


def enroll_card(card_id: int):
    # High-entropy, locally simulated card credential.
    credential = "SC1." + secrets.token_urlsafe(32)
    credential_hash = hashlib.sha256(
        credential.encode("utf-8")
    ).hexdigest()

    with SessionLocal.begin() as db:
        # Same student-before-card lock ordering
        # used by card management.
        student_id = db.scalar(
            select(Card.student_id).where(Card.id == card_id)
        )

        if student_id is None:
            raise ValueError("Card does not exist")

        student = db.scalar(
            select(Student)
            .where(Student.id == student_id)
            .with_for_update()
        )

        if student is None or not student.is_active:
            raise ValueError("Student is inactive or missing")

        card = db.scalar(
            select(Card)
            .where(Card.id == card_id)
            .with_for_update()
        )

        if card is None or card.status != "active":
            raise ValueError("Only an active card can be enrolled")

        card.card_token_hash = credential_hash

    # Printed only after successful database commit.
    print("Card credential enrolled successfully.")
    print(f"Card ID: {card_id}")
    print("Save the following credential privately.")
    print("It will not be shown again:")
    print(credential)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--card-id",
        type=int,
        required=True,
    )
    args = parser.parse_args()

    enroll_card(args.card_id)
