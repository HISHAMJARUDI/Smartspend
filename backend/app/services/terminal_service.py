import hashlib
import hmac
import secrets

from sqlalchemy.orm import Session

from app.models.canteen_terminal import CanteenTerminal
from app.models.terminal_credential import TerminalCredential


def hash_terminal_secret(secret: str) -> str:
    return hashlib.sha256(
        secret.encode("utf-8")
    ).hexdigest()


def create_terminal_secret(
    db: Session,
    terminal_id: int,
) -> str:
    terminal = db.get(CanteenTerminal, terminal_id)

    if terminal is None or not terminal.is_active:
        raise ValueError("Terminal unavailable")

    existing = db.query(TerminalCredential).filter_by(
        terminal_id=terminal_id
    ).first()

    if existing:
        raise ValueError(
            "Terminal already has a credential"
        )

    secret = secrets.token_urlsafe(48)

    credential = TerminalCredential(
        terminal_id=terminal.id,
        secret_hash=hash_terminal_secret(secret),
        is_active=True,
    )

    db.add(credential)
    db.flush()

    # Returned only once during provisioning.
    return f"{terminal.id}.{secret}"


def verify_terminal_key(
    db: Session,
    supplied_key: str,
) -> CanteenTerminal | None:
    try:
        terminal_part, secret = supplied_key.split(".", 1)
        terminal_id = int(terminal_part)

        if terminal_id <= 0 or len(secret) > 256:
            return None

    except (ValueError, AttributeError):
        return None

    credential = db.query(TerminalCredential).filter_by(
        terminal_id=terminal_id,
        is_active=True,
    ).first()

    if credential is None:
        return None

    terminal = db.get(
        CanteenTerminal, credential.terminal_id
    )

    if terminal is None or not terminal.is_active:
        return None

    supplied_hash = hash_terminal_secret(secret)

    if not hmac.compare_digest(
        supplied_hash,
        credential.secret_hash,
    ):
        return None

    return terminal
