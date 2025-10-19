from pydantic import BaseModel, EmailStr
from typing import Optional
from .common import ORMModel


# ✅ Wallet schema (no changes)
class WalletOut(ORMModel):
    id: str
    balance: int


# ✅ User output schema (returned by GET /users/me)
class UserOut(ORMModel):
    id: str
    email: EmailStr
    username: Optional[str] = None
    full_name: Optional[str] = None
    profile_pic: Optional[str] = None      # 👈 added line
    is_active: bool
    wallet: Optional[WalletOut] = None     # existing wallet field


# ✅ Schema for PATCH /users/me updates
class UserUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    profile_pic: Optional[str] = None      # 👈 added line
