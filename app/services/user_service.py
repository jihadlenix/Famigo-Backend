from sqlalchemy.orm import Session
from sqlalchemy import select
from ..models.user import User
from .security import hash_password, verify_password

def create_user(db: Session, *, email: str, password: str, username: str | None, full_name: str | None) -> User:
    user = User(email=email, username=username, full_name=full_name, hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()

def authenticate(db: Session, email: str, password: str) -> User | None:
    user = get_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password): 
        return None
    return user
