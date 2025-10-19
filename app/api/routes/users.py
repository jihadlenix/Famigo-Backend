from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from ...schemas.user import UserOut, UserUpdate
from ...models.user import User
from ..deps import get_db, get_current_user

router = APIRouter()

# ✅ Get current user + wallet
@router.get("/me", response_model=UserOut)
def me(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user)
):
    # Force load wallet relationship
    user = (
        db.query(User)
        .options(joinedload(User.wallet))
        .filter(User.id == current.id)
        .first()
    )
    return user


# ✅ Update user profile (username, full name, profile pic)
@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user)
):
    if payload.username is not None:
        current.username = payload.username
    if payload.full_name is not None:
        current.full_name = payload.full_name
    if payload.profile_pic is not None:          # 👈 added line
        current.profile_pic = payload.profile_pic

    db.commit()
    db.refresh(current)
    return current
