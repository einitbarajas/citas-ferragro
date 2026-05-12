from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    id: int
    actor_id: str
    appointment_id: int
    action: str
    description: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
