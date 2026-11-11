from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
)

from app.core.dependencies import require_roles
from app.database import SessionLocal
from app.models.user import User

from app.schemas.terminal_management import (
    TerminalRevocationResponse,
    TerminalRotationResponse,
)

from app.services.terminal_management_service import (
    revoke_terminal_credential,
    rotate_terminal_credential,
    TerminalNotFound,
    TerminalConflict,
)


router = APIRouter(
    prefix="/admin/terminals",
    tags=["Terminal Administration"],
)

admin_only = require_roles("system_admin")


def handle_management_error(error):
    if isinstance(error, TerminalNotFound):
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    if isinstance(error, TerminalConflict):
        raise HTTPException(
            status_code=409,
            detail=str(error),
        )

    raise error


@router.post(
    "/{terminal_id}/revoke",
    response_model=TerminalRevocationResponse,
)
def revoke_terminal(
    terminal_id: int,
    admin: User = Depends(admin_only),
):
    try:
        with SessionLocal() as db:
            return revoke_terminal_credential(
                db=db,
                terminal_id=terminal_id,
                actor_id=admin.id,
            )

    except (TerminalNotFound, TerminalConflict) as error:
        handle_management_error(error)


@router.post(
    "/{terminal_id}/rotate",
    response_model=TerminalRotationResponse,
)
def rotate_terminal(
    terminal_id: int,
    response: Response,
    admin: User = Depends(admin_only),
):
    # Prevent ordinary HTTP caching of the response.
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"

    try:
        with SessionLocal() as db:
            return rotate_terminal_credential(
                db=db,
                terminal_id=terminal_id,
                actor_id=admin.id,
            )

    except (TerminalNotFound, TerminalConflict) as error:
        handle_management_error(error)
