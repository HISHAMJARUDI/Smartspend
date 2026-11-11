from pydantic import BaseModel, EmailStr, Field, model_validator


class NewParentInput(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)


class StudentCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    school_id: int = Field(gt=0)
    student_number: str = Field(min_length=1, max_length=50)
    class_name: str | None = Field(default=None, max_length=50)

    # Existing parent, or details for a new parent.
    parent_id: int | None = Field(default=None, gt=0)
    new_parent: NewParentInput | None = None

    # Legacy fields remain optional for compatibility.
    # Students do not need interactive login credentials.
    email: EmailStr | None = None
    password: str | None = Field(
        default=None, min_length=12, max_length=128
    )

    @model_validator(mode="after")
    def validate_parent_choice(self):
        if (self.parent_id is None) == (self.new_parent is None):
            raise ValueError(
                "Provide either parent_id or new_parent, not both"
            )
        return self


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
