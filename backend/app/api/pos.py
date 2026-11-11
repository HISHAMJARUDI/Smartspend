from fastapi import (
    APIRouter, Depends, Header, HTTPException
)
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal, settings
from app.core.dependencies import require_roles
from app.core.terminal_auth import get_current_terminal
from app.models.user import User
from app.models.canteen_terminal import CanteenTerminal
from app.schemas.pos import PurchaseCreate, PurchaseResponse
from app.services.wallet_service import (
    process_scanned_card_purchase,
    PaymentError,
)
from app.services.audit_service import record_audit_event


router = APIRouter(
    prefix="/pos",
    tags=["Canteen POS"],
)


@router.post(
    "/purchases",
    response_model=PurchaseResponse,
    status_code=201,
)
def create_purchase(
    payload: PurchaseCreate,
    attendant: User = Depends(
        require_roles("canteen")
    ),
    terminal: CanteenTerminal = Depends(
        get_current_terminal
    ),
    terminal_key: str | None = Header(
        default=None,
        alias="X-Terminal-Key",
    ),
):
    if not settings.DEMO_POS_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="Demo POS is disabled",
        )

    if attendant.school_id != terminal.school_id:
        raise HTTPException(
            status_code=403,
            detail="Attendant not authorized for terminal school",
        )

    try:
        with SessionLocal() as db:
            result = process_scanned_card_purchase(
                db=db,
                card_credential=payload.card_credential,
                terminal_id=terminal.id,
                attendant_id=attendant.id,
                amount=payload.amount,
                key=payload.idempotency_key,
                terminal_key=terminal_key,
            )

        return PurchaseResponse(**result)

    except PaymentError as error:
        # Fixed server-controlled categories only.
        # Never record raw credentials or request bodies.
        reason_codes = {
            "Invalid card credential": "invalid_card",
            "Invalid or blocked card": "blocked_or_invalid_card",
            "Insufficient balance": "insufficient_balance",
            "Transaction key already used": "duplicate_request",
            "Unauthorized canteen terminal": "unauthorized_terminal",
            "Unauthorized attendant": "unauthorized_attendant",
            "Invalid student": "invalid_student",
            "Wallet unavailable": "wallet_unavailable",
            "Invalid terminal credentials": "unauthorized_terminal",
        }

        reason_code = reason_codes.get(
            str(error),
            "other_payment_rejection",
        )

        # The financial transaction has already rolled back.
        # Record the denied request in a separate transaction.
        with SessionLocal.begin() as audit_db:
            record_audit_event(
                audit_db,
                action="pos.purchase_rejected",
                entity_type="canteen_terminal",
                entity_id=terminal.id,
                actor_id=attendant.id,
                school_id=attendant.school_id,
                outcome="denied",
                details={
                    "reason_code": reason_code,
                    "terminal_id": terminal.id,
                },
            )

        raise HTTPException(
            status_code=(
                401
                if str(error) == "Invalid terminal credentials"
                else 400
            ),
            detail=str(error),
        )

    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Duplicate or conflicting transaction",
        )
