from pydantic import BaseModel


class ChildWalletResponse(BaseModel):
    student_id: int
    full_name: str
    student_number: str
    class_name: str | None
    school_id: int
    wallet_id: int
    balance: int
    currency: str
