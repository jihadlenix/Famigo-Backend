from pydantic import BaseModel, EmailStr
class SignupIn(BaseModel):
    email: EmailStr
    password: str
    username: str | None = None
    full_name: str | None = None
class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None
