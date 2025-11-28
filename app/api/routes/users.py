from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException
from sqlalchemy.orm import Session, joinedload
import os
import uuid
from pathlib import Path
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
    - user info (including wallet, bio, etc.)
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


# ✅ Update user profile (username, full name, profile pic, bio)
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
    if getattr(payload, "bio", None) is not None:
        current.bio = payload.bio

    db.commit()
    db.refresh(current)
    return _build_me_out(db, current)


# ✅ Upload profile picture
@router.post("/me/profile-picture", response_model=MeOut)
async def upload_profile_picture(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "File must be an image")
    
    # Create uploads directory if it doesn't exist
    upload_dir = Path("static/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    file_ext = Path(file.filename).suffix if file.filename else ".jpg"
    unique_filename = f"{uuid.uuid4().hex}{file_ext}"
    file_path = upload_dir / unique_filename
    
    # Save file
    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(500, f"Failed to save file: {str(e)}")
    
    # Update user profile_pic to relative path
    relative_path = f"uploads/{unique_filename}"
    current.profile_pic = relative_path
    
    db.commit()
    db.refresh(current)
    return _build_me_out(db, current)
