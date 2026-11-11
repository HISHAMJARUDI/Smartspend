import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.database import engine, get_db
from app.core.dependencies import get_current_user
from app.models.school import School
from app.models.user import User
from app.models.student import Student
from app.models.wallet import Wallet
from app.models.parent_student import ParentStudent
from app.schemas.student import StudentCreate
from app.services.student_service import (
    create_student,
    StudentConflict,
)


@pytest.fixture
def isolated_db():
    # Tests run only through scripts.run_tests,
    # which selects smartspend_test.
    assert engine.url.database == "smartspend_test"

    connection = engine.connect()
    outer_transaction = connection.begin()

    db = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield db, connection
    finally:
        db.close()
        outer_transaction.rollback()
        connection.close()


def unique():
    return uuid.uuid4().hex[:12]


def make_school(db, suffix):
    school = School(
        name=f"Integration Test School {suffix}",
        code=f"TS{suffix}",
        is_active=True,
    )
    db.add(school)
    db.flush()
    return school


def enroll(db, school_id, number, parent_id=None, new_parent=None):
    return create_student(
        db,
        StudentCreate(
            full_name=f"Test Student {number}",
            school_id=school_id,
            student_number=number,
            class_name="Senior One",
            parent_id=parent_id,
            new_parent=new_parent,
        ),
    )


def test_new_parent_created_during_enrollment(isolated_db):
    db, _ = isolated_db
    suffix = unique()
    school = make_school(db, suffix)
    email = f"test-parent-{suffix}@example.com"

    result = enroll(
        db,
        school.id,
        f"ST-{suffix}",
        new_parent={
            "full_name": "Test Parent",
            "email": email,
        },
    )

    parent = db.get(User, result["parent_id"])
    student = db.get(Student, result["id"])
    wallet = db.get(Wallet, result["wallet_id"])

    link = db.scalar(
        select(ParentStudent).where(
            ParentStudent.parent_id == parent.id,
            ParentStudent.student_id == student.id,
        )
    )

    assert parent.role == "parent"
    assert parent.email == email
    assert student.school_id == school.id
    assert wallet.student_id == student.id
    assert wallet.balance == 0
    assert link is not None


def test_existing_parent_reused_for_second_student(isolated_db):
    db, _ = isolated_db
    suffix = unique()
    school = make_school(db, suffix)
    email = f"shared-parent-{suffix}@example.com"

    first = enroll(
        db,
        school.id,
        f"A-{suffix}",
        new_parent={
            "full_name": "Shared Parent",
            "email": email,
        },
    )

    second = enroll(
        db,
        school.id,
        f"B-{suffix}",
        parent_id=first["parent_id"],
    )

    assert first["parent_id"] == second["parent_id"]
    assert first["wallet_id"] != second["wallet_id"]

    parent_accounts = db.scalars(
        select(User).where(User.email == email)
    ).all()

    links = db.scalars(
        select(ParentStudent).where(
            ParentStudent.parent_id == first["parent_id"]
        )
    ).all()

    assert len(parent_accounts) == 1
    assert len(links) == 2


def test_duplicate_parent_email_rejected(isolated_db):
    db, _ = isolated_db
    suffix = unique()
    school = make_school(db, suffix)
    email = f"duplicate-{suffix}@example.com"

    enroll(
        db,
        school.id,
        f"A-{suffix}",
        new_parent={
            "full_name": "Existing Parent",
            "email": email,
        },
    )

    with pytest.raises(StudentConflict):
        enroll(
            db,
            school.id,
            f"B-{suffix}",
            new_parent={
                "full_name": "Duplicate Parent",
                "email": email,
            },
        )

    assert len(
        db.scalars(
            select(User).where(User.email == email)
        ).all()
    ) == 1


def test_school_admin_cannot_access_other_school(isolated_db):
    db, connection = isolated_db
    suffix_a = unique()
    suffix_b = unique()

    school_a = make_school(db, suffix_a)
    school_b = make_school(db, suffix_b)

    own_student = enroll(
        db,
        school_a.id,
        f"A-{suffix_a}",
        new_parent={
            "full_name": "Parent A",
            "email": f"parent-a-{suffix_a}@example.com",
        },
    )

    other_student = enroll(
        db,
        school_b.id,
        f"B-{suffix_b}",
        new_parent={
            "full_name": "Parent B",
            "email": f"parent-b-{suffix_b}@example.com",
        },
    )

    admin = User(
        full_name="School A Administrator",
        role="school_admin",
        school_id=school_a.id,
        is_active=True,
    )

    def override_db():
        with Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
        ) as request_db:
            yield request_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin

    try:
        with TestClient(app) as client:
            directory = client.get("/admin/students")
            assert directory.status_code == 200

            ids = {s["id"] for s in directory.json()}
            assert own_student["id"] in ids
            assert other_student["id"] not in ids

            own = client.get(
                f"/admin/students/{own_student['id']}"
            )
            assert own.status_code == 200

            restricted_paths = [
                f"/admin/students/{other_student['id']}",
                f"/admin/students/{other_student['id']}/transactions",
                f"/admin/students/{other_student['id']}/cards",
            ]

            for path in restricted_paths:
                response = client.get(path)
                assert response.status_code == 404, path

    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
