from pydantic import BaseModel, EmailStr, Field


class ParentCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    phone: str | None = Field(
        default=None, max_length=30
    )
    password: str = Field(min_length=12, max_length=128)
