from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.database import get_db
from app.models.audit_event import AuditEvent
from app.models.user import User
from app.schemas.audit import AuditEventResponse


router = APIRouter(
    prefix="/audit",
    tags=["Security Audit"],
)

admin_only = require_roles("system_admin")


@router.get(
    "/events",
    response_model=list[AuditEventResponse],
)
def list_audit_events(
    school_id: int | None = Query(default=None, gt=0),
    action: str | None = Query(
        default=None,
        min_length=1,
        max_length=80,
    ),
    entity_type: str | None = Query(
        default=None,
        min_length=1,
        max_length=50,
    ),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    admin: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    """
    System administrators can inspect audit history.

    School administrators do not yet have access.
    """

    statement = select(AuditEvent)

    if school_id is not None:
        statement = statement.where(
            AuditEvent.school_id == school_id
        )

    if action is not None:
        statement = statement.where(
            AuditEvent.action == action
        )

    if entity_type is not None:
        statement = statement.where(
            AuditEvent.entity_type == entity_type
        )

    statement = (
        statement
        .order_by(AuditEvent.id.desc())
        .offset(offset)
        .limit(limit)
    )

    return db.scalars(statement).all()
