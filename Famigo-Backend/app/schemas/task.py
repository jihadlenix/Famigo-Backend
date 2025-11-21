from pydantic import BaseModel
from datetime import datetime
from .common import ORMModel
class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    deadline: datetime | None = None
    points_value: int = 0
class TaskOut(ORMModel):
    id: str
    family_id: str
    title: str
    description: str | None = None
    deadline: datetime | None = None
    status: str
    points_value: int
