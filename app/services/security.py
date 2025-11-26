from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
import jwt
from ..core.config import settings
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(p: str) -> str:
    # Ensure bcrypt compatibility (72-byte limit)
    p = p.encode("utf-8")[:72].decode("utf-8", errors="ignore")
    return pwd_context.hash(p)



def verify_password(p: str, hashed: str) -> bool:
    return pwd_context.verify(p, hashed)

def create_access_token(sub: str, minutes: int | None = None) -> str:
    exp_min = minutes if minutes is not None else settings.ACCESS_TOKEN_MIN
    expire = datetime.now(timezone.utc) + timedelta(minutes=exp_min)
    payload = {"sub": sub, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
