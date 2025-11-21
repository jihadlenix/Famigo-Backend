from datetime import datetime
from pydantic import BaseModel
from .common import ORMModel
class InviteCreate(BaseModel):
    expires_hours: int | None = 72
class InviteOut(ORMModel):
    id: str
    family_id: str
    code: str
    expires_at: datetime | None
    used_by_user_id: str | None
    used_at: datetime | None
    revoked: bool
