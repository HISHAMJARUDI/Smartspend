from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent


ALLOWED_OUTCOMES = {
    "success",
    "failure",
    "denied",
}

ALLOWED_DETAIL_FIELDS = {
    "reason_code",
    "previous_status",
    "new_status",
    "card_id",
    "replacement_card_id",
    "terminal_id",
    "transaction_id",
    "amount",
    "currency",
}


def record_audit_event(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    actor_id: int | None = None,
    school_id: int | None = None,
    outcome: str = "success",
    details: dict | None = None,
) -> AuditEvent:
    """
    Add an audit event to the current database transaction.

    The caller owns commit/rollback.

    Never store passwords, JWTs, card credentials,
    terminal secrets or authorization headers.
    """

    if not action or len(action) > 80:
        raise ValueError("Invalid audit action")

    if not entity_type or len(entity_type) > 50:
        raise ValueError("Invalid audit entity type")

    if outcome not in ALLOWED_OUTCOMES:
        raise ValueError("Invalid audit outcome")

    if details is not None:
        if not isinstance(details, dict):
            raise ValueError("Audit details must be a dictionary")

        disallowed = set(details) - ALLOWED_DETAIL_FIELDS

        if disallowed:
            raise ValueError(
                "Disallowed audit detail fields: "
                + ", ".join(sorted(disallowed))
            )

        if any(
            not isinstance(value, (str, int, bool, type(None)))
            for value in details.values()
        ):
            raise ValueError(
                "Audit details must contain simple values"
            )

    event = AuditEvent(
        actor_id=actor_id,
        school_id=school_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        outcome=outcome,
        details=details,
    )

    db.add(event)

    return event
