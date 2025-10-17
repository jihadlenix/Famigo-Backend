from pydantic import BaseModel, EmailStr
from .common import ORMModel
class UserOut(ORMModel):
    id: str
    email: EmailStr
    username: str | None = None
    full_name: str | None = None
    is_active: bool
class UserUpdate(BaseModel):
    username: str | None = None
    full_name: str | None = None
