import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.card import Card
from app.models.student import Student
from app.services.audit_service import record_audit_event


class CardError(Exception):
    pass


class CardNotFound(CardError):
    pass


class CardConflict(CardError):
    pass


def make_demo_card_hash() -> str:
    # Internal demo credential, NOT physical card authentication.
    token = secrets.token_bytes(32)
    return hashlib.sha256(token).hexdigest()


def lock_student(db: Session, student_id: int) -> Student:
    student = db.scalar(
        select(Student)
        .where(Student.id == student_id)
        .with_for_update()
    )

    if student is None:
        raise CardNotFound("Student not found")

    if not student.is_active:
        raise CardConflict("Student account is inactive")

    return student


def find_active_card(db: Session, student_id: int):
    return db.scalar(
        select(Card).where(
            Card.student_id == student_id,
            Card.status == "active",
        )
    )


def issue_card(
    db: Session,
    student_id: int,
    actor_id: int | None = None,
):
    with db.begin():
        student = lock_student(db, student_id)

        if find_active_card(db, student_id):
            raise CardConflict(
                "Student already has an active card"
            )

        card = Card(
            student_id=student_id,
            card_token_hash=make_demo_card_hash(),
            status="active",
        )

        db.add(card)
        db.flush()
        card_id = card.id

        record_audit_event(
            db,
            action="card.issued",
            entity_type="card",
            entity_id=card_id,
            actor_id=actor_id,
            school_id=student.school_id,
            details={
                "new_status": "active",
                "card_id": card_id,
            },
        )

    return db.get(Card, card_id)


def list_student_cards(db: Session, student_id: int):
    student = db.get(Student, student_id)

    if student is None:
        raise CardNotFound("Student not found")

    return db.scalars(
        select(Card)
        .where(Card.student_id == student_id)
        .order_by(Card.id.desc())
    ).all()


def block_card(
    db: Session,
    card_id: int,
    actor_id: int | None = None,
):
    # Read only to identify the student. The record is
    # rechecked after obtaining the student row lock.
    initial = db.get(Card, card_id)

    if initial is None:
        raise CardNotFound("Card not found")

    student_id = initial.student_id

    db.rollback()

    with db.begin():
        student = lock_student(db, student_id)

        card = db.scalar(
            select(Card)
            .where(Card.id == card_id)
            .with_for_update()
        )

        if card.status != "active":
            raise CardConflict(
                "Only active cards can be blocked"
            )

        card.status = "blocked"

        record_audit_event(
            db,
            action="card.blocked",
            entity_type="card",
            entity_id=card_id,
            actor_id=actor_id,
            school_id=student.school_id,
            details={
                "card_id": card_id,
                "previous_status": "active",
                "new_status": "blocked",
            },
        )

    return db.get(Card, card_id)


def replace_card(
    db: Session,
    card_id: int,
    actor_id: int | None = None,
):
    initial = db.get(Card, card_id)

    if initial is None:
        raise CardNotFound("Card not found")

    student_id = initial.student_id

    db.rollback()

    with db.begin():
        student = lock_student(db, student_id)

        old_card = db.scalar(
            select(Card)
            .where(Card.id == card_id)
            .with_for_update()
        )

        if old_card.status not in ("active", "blocked", "lost"):
            raise CardConflict(
                "Card cannot be replaced"
            )

        previous_status = old_card.status

        if old_card.status == "active":
            old_card.status = "blocked"

            # SessionLocal uses autoflush=False.
            # Persist the status change inside this transaction
            # before checking for another active card.
            db.flush()

        if find_active_card(db, student_id):
            raise CardConflict(
                "Student already has another active card"
            )

        new_card = Card(
            student_id=student_id,
            card_token_hash=make_demo_card_hash(),
            status="active",
        )

        db.add(new_card)
        db.flush()
        new_card_id = new_card.id

        record_audit_event(
            db,
            action="card.replaced",
            entity_type="card",
            entity_id=card_id,
            actor_id=actor_id,
            school_id=student.school_id,
            details={
                "card_id": card_id,
                "replacement_card_id": new_card_id,
                "previous_status": previous_status,
                "new_status": "active",
            },
        )

    return db.get(Card, new_card_id)
