from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.database import engine, get_db
from app.core.dependencies import get_current_user
from app.core.security import hash_password
from app.models.school import School
from app.models.user import User
from app.models.audit_event import AuditEvent


@pytest.fixture
def admin_context():
    assert engine.url.database == "smartspend_test"

    connection = engine.connect()
    outer_transaction = connection.begin()

    db = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    suffix = uuid4().hex[:12]

    school = School(
        name=f"Admin Test School {suffix}",
        code=f"SA{suffix}",
        is_active=True,
    )
    db.add(school)
    db.flush()

    actor = User(
        full_name="Test System Administrator",
        email=f"system-{suffix}@example.com",
        password_hash=hash_password(
            "TestSystemPassword123!"
        ),
        role="system_admin",
        school_id=None,
        is_active=True,
    )
    db.add(actor)
    db.flush()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: actor

    try:
        yield db, school, actor, suffix
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        db.close()
        outer_transaction.rollback()
        connection.close()


def payload(school_id, suffix):
    return {
        "full_name": "New School Administrator",
        "email": f"admin-{suffix}@example.com",
        "school_id": school_id,
        "temporary_password": "StrongTemporaryPassword123!",
    }


def test_system_admin_creates_school_admin(admin_context):
    db, school, actor, suffix = admin_context

    with TestClient(app) as client:
        response = client.post(
            "/admin/school-admins",
            json=payload(school.id, suffix),
        )

    assert response.status_code == 201, response.text

    data = response.json()
    assert data["role"] == "school_admin"
    assert data["school_id"] == school.id
    assert data["is_active"] is True

    assert "password_hash" not in data
    assert "temporary_password" not in data

    created = db.get(User, data["id"])
    assert created is not None

    event = db.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "school_admin.created",
            AuditEvent.entity_id == created.id,
        )
    )

    assert event is not None
    assert event.actor_id == actor.id
    assert event.school_id == school.id
    assert event.outcome == "success"
    assert "password" not in str(event.details).lower()


@pytest.mark.parametrize(
    "role",
    ["school_admin", "parent", "canteen"],
)
def test_other_roles_cannot_create_admin(admin_context, role):
    db, school, actor, suffix = admin_context

    actor.role = role
    db.flush()

    with TestClient(app) as client:
        response = client.post(
            "/admin/school-admins",
            json=payload(school.id, suffix),
        )

    assert response.status_code == 403


def test_cannot_create_admin_for_inactive_school(admin_context):
    db, school, actor, suffix = admin_context

    school.is_active = False
    db.flush()

    with TestClient(app) as client:
        response = client.post(
            "/admin/school-admins",
            json=payload(school.id, suffix),
        )

    assert response.status_code == 400


def test_duplicate_school_admin_email_rejected(admin_context):
    db, school, actor, suffix = admin_context
    data = payload(school.id, suffix)

    with TestClient(app) as client:
        first = client.post(
            "/admin/school-admins",
            json=data,
        )
        second = client.post(
            "/admin/school-admins",
            json=data,
        )

    assert first.status_code == 201
    assert second.status_code == 409


def test_system_admin_deactivates_and_audits(admin_context):
    db, school, actor, suffix = admin_context

    with TestClient(app) as client:
        created = client.post(
            "/admin/school-admins",
            json=payload(school.id, suffix),
        )

        assert created.status_code == 201
        admin_id = created.json()["id"]

        response = client.post(
            f"/admin/school-admins/{admin_id}/deactivate"
        )

        again = client.post(
            f"/admin/school-admins/{admin_id}/deactivate"
        )

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert again.status_code == 409

    admin = db.get(User, admin_id)
    assert admin.is_active is False

    event = db.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "school_admin.deactivated",
            AuditEvent.entity_id == admin_id,
        )
    )

    assert event is not None
    assert event.actor_id == actor.id
    assert event.school_id == school.id


def test_school_admin_cannot_deactivate_admin(admin_context):
    db, school, actor, suffix = admin_context

    with TestClient(app) as client:
        created = client.post(
            "/admin/school-admins",
            json=payload(school.id, suffix),
        )

        assert created.status_code == 201
        admin_id = created.json()["id"]

        actor.role = "school_admin"
        actor.school_id = school.id
        db.flush()

        response = client.post(
            f"/admin/school-admins/{admin_id}/deactivate"
        )

    assert response.status_code == 403
    assert db.get(User, admin_id).is_active is True
