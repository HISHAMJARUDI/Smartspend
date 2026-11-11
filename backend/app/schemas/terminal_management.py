from pydantic import BaseModel, Field


class TerminalRevocationResponse(BaseModel):
    terminal_id: int
    message: str


class TerminalRotationResponse(BaseModel):
    terminal_id: int
    message: str
    terminal_key: str = Field(
        description=(
            "New secret credential. "
            "Available only in this response."
        )
    )
