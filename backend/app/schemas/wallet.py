from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WalletResponse(BaseModel):
    id: int
    student_id: int
    balance: int
    currency: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TransactionResponse(BaseModel):
    id: int
    wallet_id: int
    amount: int
    currency: str
    transaction_type: str
    status: str
    terminal_id: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
