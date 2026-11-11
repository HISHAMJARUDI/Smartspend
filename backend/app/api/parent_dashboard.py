from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User
from app.schemas.wallet import TransactionResponse
from app.schemas.parent_dashboard import ChildWalletResponse
from app.services.parent_dashboard_service import (
    list_parent_children,
    get_child_transactions,
    ChildAccessDenied,
)


router = APIRouter(
    prefix="/parents/me",
    tags=["Parent Dashboard"],
)

parent_only = require_roles("parent")


@router.get(
    "/children",
    response_model=list[ChildWalletResponse],
)
def read_my_children(
    parent: User = Depends(parent_only),
    db: Session = Depends(get_db),
):
    return list_parent_children(db, parent.id)


@router.get(
    "/children/{student_id}/transactions",
    response_model=list[TransactionResponse],
)
def read_child_transactions(
    student_id: int,
    parent: User = Depends(parent_only),
    db: Session = Depends(get_db),
):
    try:
        return get_child_transactions(
            db,
            parent_user_id=parent.id,
            student_id=student_id,
        )

    except ChildAccessDenied as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )
