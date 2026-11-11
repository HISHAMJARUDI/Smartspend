from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User
from app.schemas.wallet import (
    WalletResponse,
    TransactionResponse,
)
from app.services.wallet_query_service import (
    get_student_wallet,
    get_wallet_transactions,
    WalletNotFound,
)


router = APIRouter(
    prefix="/wallets",
    tags=["Student Wallet"],
)

student_only = require_roles("student")


@router.get("/me", response_model=WalletResponse)
def read_my_wallet(
    student_user: User = Depends(student_only),
    db: Session = Depends(get_db),
):
    try:
        return get_student_wallet(db, student_user.id)

    except WalletNotFound as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )


@router.get(
    "/me/transactions",
    response_model=list[TransactionResponse],
)
def read_my_transactions(
    student_user: User = Depends(student_only),
    db: Session = Depends(get_db),
):
    try:
        wallet = get_student_wallet(
            db, student_user.id
        )

        return get_wallet_transactions(db, wallet.id)

    except WalletNotFound as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )
