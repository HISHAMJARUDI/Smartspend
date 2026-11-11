import hashlib
import secrets

from sqlalchemy import select

from app.database import SessionLocal
from app.models.canteen_terminal import CanteenTerminal
from app.models.terminal_credential import TerminalCredential


def main():
    with SessionLocal.begin() as db:
        terminal = db.get(CanteenTerminal, 1)

        if terminal is None or not terminal.is_active:
            raise SystemExit("Terminal unavailable")

        credential = db.scalar(
            select(TerminalCredential)
            .where(TerminalCredential.terminal_id == terminal.id)
            .with_for_update()
        )

        if credential is None:
            raise SystemExit(
                "Terminal credential not found. "
                "Run the initial provisioning script instead."
            )

        secret = secrets.token_urlsafe(48)

        credential.secret_hash = hashlib.sha256(
            secret.encode("utf-8")
        ).hexdigest()

        credential.is_active = True

        new_key = f"{terminal.id}.{secret}"

    print("Terminal credential rotated successfully.")
    print("Previous terminal credential is now invalid.")
    print("Copy and securely store your new key:")
    print(new_key)


if __name__ == "__main__":
    main()
