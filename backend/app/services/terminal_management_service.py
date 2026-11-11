import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.canteen_terminal import CanteenTerminal
from app.models.terminal_credential import TerminalCredential
from app.services.audit_service import record_audit_event


class TerminalManagementError(Exception):
    pass


class TerminalNotFound(TerminalManagementError):
    pass


class TerminalConflict(TerminalManagementError):
    pass


def lock_terminal(db: Session, terminal_id: int):
    terminal = db.scalar(
        select(CanteenTerminal)
        .where(CanteenTerminal.id == terminal_id)
        .with_for_update()
    )

    if terminal is None:
        raise TerminalNotFound("Terminal not found")

    return terminal


def lock_credential(db: Session, terminal_id: int):
    return db.scalar(
        select(TerminalCredential)
        .where(TerminalCredential.terminal_id == terminal_id)
        .with_for_update()
    )


def revoke_terminal_credential(
    db: Session,
    terminal_id: int,
    actor_id: int,
):
    with db.begin():
        terminal = lock_terminal(db, terminal_id)
        credential = lock_credential(db, terminal_id)

        if credential is None:
            raise TerminalNotFound(
                "Terminal credential not found"
            )

        if not credential.is_active:
            raise TerminalConflict(
                "Terminal credential already revoked"
            )

        credential.is_active = False

        record_audit_event(
            db,
            action="terminal.credential_revoked",
            entity_type="canteen_terminal",
            entity_id=terminal.id,
            actor_id=actor_id,
            school_id=terminal.school_id,
            details={
                "terminal_id": terminal.id,
                "previous_status": "active",
                "new_status": "revoked",
            },
        )

    return {
        "terminal_id": terminal_id,
        "message": "Terminal credential revoked",
    }


def rotate_terminal_credential(
    db: Session,
    terminal_id: int,
    actor_id: int,
):
    with db.begin():
        terminal = lock_terminal(db, terminal_id)

        if not terminal.is_active:
            raise TerminalConflict(
                "Terminal is disabled"
            )

        credential = lock_credential(db, terminal_id)

        previous_status = (
            "active"
            if credential is not None and credential.is_active
            else "revoked"
            if credential is not None
            else "not_provisioned"
        )

        secret = secrets.token_urlsafe(48)

        secret_hash = hashlib.sha256(
            secret.encode("utf-8")
        ).hexdigest()

        if credential is None:
            credential = TerminalCredential(
                terminal_id=terminal.id,
                secret_hash=secret_hash,
                is_active=True,
            )
            db.add(credential)
        else:
            credential.secret_hash = secret_hash
            credential.is_active = True

        record_audit_event(
            db,
            action="terminal.credential_rotated",
            entity_type="canteen_terminal",
            entity_id=terminal.id,
            actor_id=actor_id,
            school_id=terminal.school_id,
            details={
                "terminal_id": terminal.id,
                "previous_status": previous_status,
                "new_status": "active",
            },
        )

        db.flush()

        result = {
            "terminal_id": terminal.id,
            "terminal_key": f"{terminal.id}.{secret}",
            "message": "Terminal credential rotated",
        }

    return result
