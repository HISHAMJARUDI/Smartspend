from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CardIssueRequest(BaseModel):
    student_id: int = Field(gt=0)


class CardResponse(BaseModel):
    id: int
    student_id: int
    status: str
    issued_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CardActionResponse(BaseModel):
    message: str
    card: CardResponse
