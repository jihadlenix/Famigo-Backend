from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...schemas.family import FamilyCreate, FamilyOut
from ...schemas.member import MemberOut
from ...schemas.invite import InviteCreate, InviteOut
from ...services.family_service import create_family, list_user_families, get_family, ensure_member, join_by_secret, create_invite
from ...services.family_service import accept_invite
from ...models.family_member import MemberRole
from ...models.user import User
from ..deps import get_db, get_current_user
router = APIRouter()

@router.post("/", response_model=FamilyOut)
def create(payload: FamilyCreate, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    fam = create_family(db, owner_user_id=current.id, name=payload.name)
    return fam

@router.get("/my", response_model=list[FamilyOut])
def my_families(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    return list_user_families(db, user_id=current.id)

@router.get("/{family_id}", response_model=FamilyOut)
def get_one(family_id: str, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    fam = get_family(db, family_id)
    if not fam: 
        raise HTTPException(404, "Family not found")
    if not ensure_member(db, user_id=current.id, family_id=fam.id):
        raise HTTPException(403, "Not a member of this family")
    return fam

@router.post("/{family_id}/invite", response_model=InviteOut)
def make_invite(family_id: str, payload: InviteCreate, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    member = ensure_member(db, user_id=current.id, family_id=family_id)
    if not member or member.role != MemberRole.PARENT:
        raise HTTPException(403, "Only parents can create invites")
    inv = create_invite(db, family_id=family_id, created_by_member_id=member.id, expires_hours=payload.expires_hours)
    return inv

@router.post("/join/secret/{code}", response_model=MemberOut)
def join_secret(code: str, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    m = join_by_secret(db, user_id=current.id, code=code)
    if not m: 
        raise HTTPException(400, "Invalid code or already a member")
    return m

@router.post("/join/invite/{code}", response_model=MemberOut)
def join_invite(code: str, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    m = accept_invite(db, code=code, user_id=current.id)
    if not m: 
        raise HTTPException(400, "Invalid/expired invite or already a member")
    return m
