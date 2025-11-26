from sqlalchemy.orm import Session
from sqlalchemy import select
import logging
from ..models.user import User
from .security import hash_password, verify_password

logger = logging.getLogger(__name__)

def create_user(db: Session, *, email: str, password: str, username: str | None, full_name: str | None, age: int) -> User:
    try:
        logger.info(f"Creating user: email={email}, age={age}, username={username}, full_name={full_name}")
        user = User(email=email, username=username, full_name=full_name, age=age, hashed_password=hash_password(password))
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"User created successfully: id={user.id}, email={user.email}, age={user.age}")
        return user
    except Exception as e:
        logger.error(f"Error creating user with email {email}: {str(e)}", exc_info=True)
        db.rollback()
        raise

def get_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()

def authenticate(db: Session, email: str, password: str) -> User | None:
    user = get_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password): 
        return None
    return user
