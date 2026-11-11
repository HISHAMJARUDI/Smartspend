from pydantic import BaseModel, EmailStr, Field


class StudentCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    school_id: int = Field(gt=0)
    student_number: str = Field(
        min_length=1, max_length=50
    )
    class_name: str | None = Field(
        default=None, max_length=50
    )
    parent_id: int = Field(gt=0)


class StudentResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    school_id: int
    student_number: str
    class_name: str | None
    parent_id: int
    wallet_id: int
    wallet_balance: int
    currency: str
