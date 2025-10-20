from fastapi import APIRouter, Depends, Form, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from ...schemas.user import UserOut
from ...models.user import User
from ..deps import get_db, get_current_user
from app.utils.avatar_generator import generate_cartoon_avatar

import os, shutil
from uuid import uuid4
import traceback

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
async def update_me(
    username: str = Form(None),
    full_name: str = Form(None),
    profile_pic: UploadFile = File(None),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    print("\n🟢 [DEBUG] Entered /me PATCH endpoint")

    # --- Update text fields ---
    if username:
        print(f"🟡 Updating username → {username}")
        current.username = username
    if full_name:
        print(f"🟡 Updating full name → {full_name}")
        current.full_name = full_name

    # --- Handle image upload ---
    if profile_pic:
        print(f"🟡 Received uploaded file: {profile_pic.filename}")

        upload_dir = "static/uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_ext = profile_pic.filename.split(".")[-1]
        new_filename = f"{uuid4().hex}.{file_ext}"
        file_path = os.path.join(upload_dir, new_filename)

        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(profile_pic.file, buffer)
            print(f"✅ [DEBUG] Saved uploaded image at: {file_path}")
        except Exception as e:
            print(f"❌ [ERROR] Failed saving uploaded image: {e}")
            raise

        # Save normal profile picture URL
        profile_pic_url = f"/{file_path}"
        current.profile_pic = profile_pic_url
        print(f"🟢 [DEBUG] profile_pic_url set to: {profile_pic_url}")

        # --- Cartoon generation ---
        try:
            print("🎨 [DEBUG] Sending image to Hugging Face Space...")
            cartoon_url = generate_cartoon_avatar(file_path)
            current.cartoon_avatar = cartoon_url
            print(f"✅ [DEBUG] Cartoon avatar generated successfully → {cartoon_url}")
        except Exception as e:
            print("❌ [ERROR] Failed to cartoonize image:")
            traceback.print_exc()
    else:
        print("🟡 [DEBUG] No profile picture uploaded")

    # --- Commit DB changes ---
    try:
        db.commit()
        db.refresh(current)
        print("✅ [DEBUG] Database updated and user refreshed\n")
    except Exception as e:
        print(f"❌ [ERROR] Database commit failed: {e}")
        traceback.print_exc()

    return current
