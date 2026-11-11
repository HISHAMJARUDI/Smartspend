from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.core.dependencies import require_roles
from app.models.user import User
from app.schemas.card import (
    CardIssueRequest,
    CardResponse,
    CardActionResponse,
)
from app.services.card_service import (
    issue_card,
    list_student_cards,
    block_card,
    replace_card,
    CardNotFound,
    CardConflict,
)


router = APIRouter(
    prefix="/cards",
    tags=["Card Management"],
)

admin_only = require_roles("system_admin")


def handle_error(error: Exception):
    if isinstance(error, CardNotFound):
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    if isinstance(error, CardConflict):
        raise HTTPException(
            status_code=409,
            detail=str(error),
        )

    raise error


@router.post(
    "/issue",
    response_model=CardActionResponse,
    status_code=201,
)
def issue_student_card(
    payload: CardIssueRequest,
    admin: User = Depends(admin_only),
):
    try:
        with SessionLocal() as db:
            card = issue_card(db, payload.student_id, actor_id=admin.id)

            return {
                "message": "Card issued successfully",
                "card": card,
            }

    except (CardNotFound, CardConflict) as error:
        handle_error(error)


@router.get(
    "/student/{student_id}",
    response_model=list[CardResponse],
)
def get_student_cards(
    student_id: int,
    admin: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    try:
        return list_student_cards(db, student_id)

    except CardNotFound as error:
        handle_error(error)


@router.post(
    "/{card_id}/block",
    response_model=CardActionResponse,
)
def block_student_card(
    card_id: int,
    admin: User = Depends(admin_only),
):
    try:
        with SessionLocal() as db:
            card = block_card(db, card_id, actor_id=admin.id)

            return {
                "message": "Card blocked successfully",
                "card": card,
            }

    except (CardNotFound, CardConflict) as error:
        handle_error(error)


@router.post(
    "/{card_id}/replace",
    response_model=CardActionResponse,
    status_code=201,
)
def replace_student_card(
    card_id: int,
    admin: User = Depends(admin_only),
):
    try:
        with SessionLocal() as db:
            card = replace_card(db, card_id, actor_id=admin.id)

            return {
                "message": "Replacement card issued",
                "card": card,
            }

    except (CardNotFound, CardConflict) as error:
        handle_error(error)
