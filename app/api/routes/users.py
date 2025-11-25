from fastapi import APIRouter, Depends, Form, UploadFile, File
from sqlalchemy.orm import Session, joinedload

from typing import List

from ...schemas.user import UserOut, UserUpdate, MeOut
from ...schemas.family import FamilyOut
from ...models.user import User
from ..deps import get_db, get_current_user
from ...services.family_service import list_user_families

router = APIRouter()


def _build_me_out(db: Session, user: User) -> MeOut:
    """
    Helper to build the MeOut response:
    - user info (including wallet, etc.)
    - families this user belongs to
    """
    # load all families for this user
    families = list_user_families(db, user_id=user.id)

    user_out = UserOut.from_orm(user)
    families_out: List[FamilyOut] = [FamilyOut.from_orm(f) for f in families]

    return MeOut(**user_out.dict(), families=families_out)


# ✅ Get current user + wallet + families
@router.get("/me", response_model=MeOut)
def me(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    # Force load wallet relationship
    user = (
        db.query(User)
        .options(joinedload(User.wallet))
        .filter(User.id == current.id)
        .first()
    )
    return _build_me_out(db, user)


# ✅ Update user profile (username, full name, profile pic, age)
@router.patch("/me", response_model=MeOut)
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if payload.username is not None:
        current.username = payload.username
    if payload.full_name is not None:
        current.full_name = payload.full_name
    if payload.profile_pic is not None:
        current.profile_pic = payload.profile_pic
    if payload.age is not None:
        current.age = payload.age

    db.commit()
    db.refresh(current)
    return _build_me_out(db, current)
