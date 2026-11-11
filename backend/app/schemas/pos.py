from pydantic import BaseModel, Field


class PurchaseCreate(BaseModel):
    card_credential: str = Field(
        min_length=47,
        max_length=47,
        pattern=r"^SC1\.[A-Za-z0-9_-]{43}$",
    )

    amount: int = Field(gt=0)

    idempotency_key: str = Field(
        min_length=8,
        max_length=100,
    )


class PurchaseResponse(BaseModel):
    transaction_id: int
    amount: int
    balance: int
    status: str = "completed"
