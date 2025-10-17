from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...schemas.user import UserOut, UserUpdate
from ...models.user import User
from ..deps import get_db, get_current_user
router = APIRouter()
@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    return current
@router.patch("/me", response_model=UserOut)
def update_me(payload: UserUpdate, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    if payload.username is not None:
        current.username = payload.username
    if payload.full_name is not None:
        current.full_name = payload.full_name
    db.commit() 
    db.refresh(current)
    return current
