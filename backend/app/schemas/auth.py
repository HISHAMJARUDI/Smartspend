from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: str | None
    phone: str | None
    role: str
    school_id: int | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
