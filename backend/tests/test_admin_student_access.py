import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.api.admin_students import base_query, scoped_query


def make_admin(role, school_id=None):
    return User(
        id=999,
        full_name="Test Administrator",
        role=role,
        school_id=school_id,
        is_active=True,
    )


@pytest.mark.parametrize("path", [
    "/admin/students",
    "/admin/students/1",
    "/admin/students/1/transactions",
    "/admin/students/1/cards",
])
def test_unauthenticated_admin_access_denied(path):
    with TestClient(app) as client:
        response = client.get(path)

    assert response.status_code == 401


@pytest.mark.parametrize("role", [
    "parent",
    "student",
    "canteen",
])
def test_non_admin_roles_denied(role):
    app.dependency_overrides[get_current_user] = (
        lambda: make_admin(role)
    )

    try:
        with TestClient(app) as client:
            response = client.get("/admin/students")

        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_school_admin_query_is_school_scoped():
    admin = make_admin("school_admin", school_id=17)

    statement = scoped_query(base_query(), admin)
    compiled = statement.compile()

    sql = str(compiled)

    assert "WHERE students.school_id" in sql
    assert 17 in compiled.params.values()


def test_school_admin_without_school_denied():
    admin = make_admin("school_admin", school_id=None)

    with pytest.raises(HTTPException) as error:
        scoped_query(base_query(), admin)

    assert error.value.status_code == 403


def test_system_admin_query_has_no_school_filter():
    admin = make_admin("system_admin")

    statement = scoped_query(base_query(), admin)
    compiled = statement.compile()

    assert "WHERE students.school_id" not in str(compiled)
