from pydantic import BaseModel
from datetime import datetime
from .common import ORMModel
class RewardCreate(BaseModel):
    title: str
    description: str | None = None
    cost_points: int
class RewardOut(ORMModel):
    id: str
    family_id: str
    title: str
    description: str | None = None
    cost_points: int
    is_active: bool
class RedemptionOut(ORMModel):
    id: str
    reward_id: str
    requested_by_member_id: str
    approved_by_member_id: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    redeemed_at: datetime | None
