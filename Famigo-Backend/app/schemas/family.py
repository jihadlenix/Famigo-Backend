from typing import List
from pydantic import BaseModel
from .common import ORMModel
from .member import MemberOut 
class FamilyCreate(BaseModel):
    name: str
class FamilyOut(ORMModel):
    id: str
    name: str
    secret_code: str
    owner_id: str | None
    members: List[MemberOut] = []
