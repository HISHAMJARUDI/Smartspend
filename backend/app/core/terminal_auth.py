from fastapi import (
    Depends, Header, HTTPException
)
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.canteen_terminal import CanteenTerminal
from app.services.terminal_service import verify_terminal_key


def get_current_terminal(
    x_terminal_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> CanteenTerminal:

    if not x_terminal_key:
        raise HTTPException(
            status_code=401,
            detail="Terminal authentication required",
        )

    terminal = verify_terminal_key(
        db, x_terminal_key
    )

    if terminal is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid terminal credentials",
        )

    return terminal
