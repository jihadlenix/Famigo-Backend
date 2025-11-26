from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import secrets
import logging
from ...schemas.auth import SignupIn, TokenOut
from ...schemas.user import UserOut
from ...services.user_service import create_user, authenticate, get_by_email
from ...services.security import create_access_token
from ...models.auth import RefreshToken
from ...models import utcnow
from ...core.config import settings
from ..deps import get_db

logger = logging.getLogger(__name__)

router = APIRouter()
@router.post("/signup", response_model=UserOut)
def signup(payload: SignupIn, db: Session = Depends(get_db)):
    try:
        logger.info(f"Signup attempt for email: {payload.email}, age: {payload.age}")
        logger.debug(f"Signup payload: email={payload.email}, username={payload.username}, full_name={payload.full_name}, age={payload.age}")
        
        if get_by_email(db, payload.email):
            logger.warning(f"Signup failed: Email already registered - {payload.email}")
            raise HTTPException(400, "Email already registered")
        
        logger.info(f"Creating user with email: {payload.email}, age: {payload.age}")
        user = create_user(
            db, 
            email=payload.email, 
            password=payload.password, 
            username=payload.username, 
            full_name=payload.full_name, 
            age=payload.age
        )
        logger.info(f"User created successfully: {user.id}, email: {user.email}, age: {user.age}")
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup error for email {payload.email}: {str(e)}", exc_info=True)
        raise HTTPException(500, f"Signup failed: {str(e)}")

@router.post("/token", response_model=TokenOut)
def token(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate(db, email=form.username, password=form.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials")
    access = create_access_token(user.id)
    refresh_plain = secrets.token_urlsafe(48)
    rt = RefreshToken(user_id=user.id, token=refresh_plain,
                      expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_DAYS))
    db.add(rt) 
    db.commit()
    return TokenOut(access_token=access, refresh_token=refresh_plain)

@router.post("/refresh", response_model=TokenOut)
def refresh(refresh_token: str, db: Session = Depends(get_db)):
    rt = db.query(RefreshToken).filter(
        RefreshToken.token == refresh_token,
        RefreshToken.is_revoked.is_(False)
    ).first()
    if not rt:
        raise HTTPException(401, "Invalid or expired refresh")

    # normalize tz to avoid “offset-naive vs offset-aware”
    now = datetime.now(timezone.utc)
    if rt.expires_at:
        exp = rt.expires_at
        exp = exp.replace(tzinfo=timezone.utc) if exp.tzinfo is None else exp.astimezone(timezone.utc)
        if exp < now:
            raise HTTPException(401, "Invalid or expired refresh")

    access = create_access_token(rt.user_id)
    return TokenOut(access_token=access, refresh_token=refresh_token)