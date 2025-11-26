from pydantic import BaseModel, EmailStr
from typing import List, Optional
from .common import ORMModel
from .family import FamilyOut 

# ✅ Wallet schema (no changes)
class WalletOut(ORMModel):
    id: str
    balance: int


class UserOut(ORMModel):
    id: str
    email: EmailStr
    username: Optional[str] = None
    full_name: Optional[str] = None
    profile_pic: Optional[str] = None      # 👈 added line
    age: int                                # Age in years (required)
    is_active: bool
    wallet: Optional[WalletOut] = None     # existing wallet field
    bio: Optional[str] = None

class UserUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    profile_pic: Optional[str] = None      
    bio: Optional[str] = None

class MeOut(UserOut):
    families: List[FamilyOut] = []   # 👈 NEW FIELD
    profile_pic: Optional[str] = None      # 👈 added line
    age: Optional[int] = None              # Age in years
