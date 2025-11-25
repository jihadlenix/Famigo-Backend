from pydantic import BaseModel, EmailStr
from typing import Optional

class SignupIn(BaseModel):
    email: EmailStr
    password: str
    username: str | None = None
    full_name: str | None = None
    age: int  # Age in years (required)
class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None
