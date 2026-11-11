from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import engine
from app.models.school import School
from app.models.user import User
from app.models.student import Student
from app.models.card import Card
from app.models.audit_event import AuditEvent
from app.services.card_service import (
    CardNotFound,
    issue_card,
    block_card,
    replace_card,
    list_student_cards,
)


@pytest.fixture
def two_schools():
    assert engine.url.database == "smartspend_test"

    connection = engine.connect()
    transaction = connection.begin()

    def session():
        return Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
        )

    try:
        suffix = uuid4().hex[:12]

        with session() as db:
            schools = []

            for number in (1, 2):
                school = School(
                    name=f"Card Security School {number} {suffix}",
                    code=f"CS{number}{suffix}",
                    is_active=True,
                )
                db.add(school)
                schools.append(school)

            db.flush()

            students = []
            cards = []

            for number, school in enumerate(schools, start=1):
                user = User(
                    full_name=f"Card Test Student {number}",
                    email=f"card-student-{number}-{suffix}@example.com",
                    password_hash="test-account-not-for-login",
                    role="student",
                    school_id=school.id,
                    is_active=True,
                )
                db.add(user)
                db.flush()

                student = Student(
                    user_id=user.id,
                    school_id=school.id,
                    student_number=f"CARD-{number}-{suffix}",
                    is_active=True,
                )
                db.add(student)
                db.flush()

                card = Card(
                    student_id=student.id,
                    card_token_hash=uuid4().hex + uuid4().hex,
                    status="active",
                )
                db.add(card)
                db.flush()

                students.append(student.id)
                cards.append(card.id)

            result = {
                "school_a": schools[0].id,
                "school_b": schools[1].id,
                "student_a": students[0],
                "student_b": students[1],
                "card_a": cards[0],
                "card_b": cards[1],
                "session": session,
            }

            db.commit()

        yield result

    finally:
        transaction.rollback()
        connection.close()


def snapshot(db, card_id):
    card = db.get(Card, card_id)

    audit_count = db.scalar(
        select(func.count(AuditEvent.id)).where(
            AuditEvent.entity_type == "card",
            AuditEvent.entity_id == card_id,
        )
    )

    return card.status, audit_count


@pytest.mark.parametrize(
    "operation",
    ["issue", "list", "block", "replace"],
)
def test_other_school_card_operations_denied(two_schools, operation):
    data = two_schools

    with data["session"]() as db:
        before = snapshot(db, data["card_b"])

    with pytest.raises(CardNotFound):
        with data["session"]() as db:
            if operation == "issue":
                issue_card(
                    db,
                    data["student_b"],
                    allowed_school_id=data["school_a"],
                )
            elif operation == "list":
                list_student_cards(
                    db,
                    data["student_b"],
                    allowed_school_id=data["school_a"],
                )
            elif operation == "block":
                block_card(
                    db,
                    data["card_b"],
                    allowed_school_id=data["school_a"],
                )
            else:
                replace_card(
                    db,
                    data["card_b"],
                    allowed_school_id=data["school_a"],
                )

    with data["session"]() as db:
        assert snapshot(db, data["card_b"]) == before


def test_own_school_card_can_be_blocked(two_schools):
    data = two_schools

    with data["session"]() as db:
        card = block_card(
            db,
            data["card_a"],
            allowed_school_id=data["school_a"],
        )

        assert card.status == "blocked"

    with data["session"]() as db:
        assert db.get(Card, data["card_a"]).status == "blocked"


def test_own_school_card_can_be_replaced(two_schools):
    data = two_schools

    with data["session"]() as db:
        replacement = replace_card(
            db,
            data["card_a"],
            allowed_school_id=data["school_a"],
        )
        replacement_id = replacement.id
        assert replacement.status == "active"

    with data["session"]() as db:
        old = db.get(Card, data["card_a"])
        new = db.get(Card, replacement_id)

        assert old.status == "blocked"
        assert new.status == "active"
        assert new.student_id == data["student_a"]


def test_own_school_card_can_be_listed(two_schools):
    data = two_schools

    with data["session"]() as db:
        cards = list_student_cards(
            db,
            data["student_a"],
            allowed_school_id=data["school_a"],
        )

    assert len(cards) == 1
    assert cards[0].id == data["card_a"]
