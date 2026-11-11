from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditEventResponse(BaseModel):
    id: int
    actor_id: int | None
    school_id: int | None
    action: str
    entity_type: str
    entity_id: int | None
    outcome: str
    details: dict[str, Any] | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
