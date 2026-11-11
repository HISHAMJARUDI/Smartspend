from uuid import uuid4

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models.audit_event import AuditEvent
from app.services.audit_service import record_audit_event


def test_audit_event_saved():
    action = f"test.audit.{uuid4().hex}"

    event_id = None

    try:
        with SessionLocal.begin() as db:
            event = record_audit_event(
                db,
                action=action,
                entity_type="card",
                entity_id=999,
                outcome="success",
                details={
                    "previous_status": "active",
                    "new_status": "blocked",
                },
            )
            db.flush()
            event_id = event.id

        with SessionLocal() as db:
            saved = db.get(AuditEvent, event_id)

            assert saved is not None
            assert saved.action == action
            assert saved.entity_type == "card"
            assert saved.entity_id == 999
            assert saved.outcome == "success"
            assert saved.details["new_status"] == "blocked"

    finally:
        if event_id is not None:
            with SessionLocal.begin() as db:
                event = db.get(AuditEvent, event_id)

                if event is not None:
                    db.delete(event)


def test_sensitive_audit_fields_rejected():
    with SessionLocal() as db:
        with pytest.raises(
            ValueError,
            match="Disallowed audit detail fields",
        ):
            record_audit_event(
                db,
                action="card.blocked",
                entity_type="card",
                outcome="success",
                details={
                    "terminal_secret": "never-store-this"
                },
            )


def test_audit_event_rolled_back_on_failure():
    action = f"test.rollback.{uuid4().hex}"

    with pytest.raises(RuntimeError):
        with SessionLocal.begin() as db:
            record_audit_event(
                db,
                action=action,
                entity_type="card",
                entity_id=999,
                outcome="success",
            )

            db.flush()

            raise RuntimeError(
                "Simulated operation failure"
            )

    with SessionLocal() as db:
        saved = db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == action
            )
        )

    assert saved is None
