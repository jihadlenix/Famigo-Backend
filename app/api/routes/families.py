from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.family import Family
from app.models.points import Wallet
from ...schemas.family import FamilyCreate, FamilyOut
from ...schemas.member import MemberOut
from ...schemas.invite import InviteCreate, InviteOut
from ...services.family_service import create_family, list_user_families, get_family, ensure_member, join_by_secret, create_invite
from ...services.family_service import accept_invite
from ...models.family_member import FamilyMember, MemberRole
from ...models.user import User
from ..deps import get_db, get_current_user
router = APIRouter()

@router.post("/", response_model=FamilyOut)
def create(payload: FamilyCreate, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    fam = create_family(db, owner_user_id=current.id, name=payload.name)
    print(f"Family created: {fam.id}")
    return fam

@router.get("/my", response_model=list[FamilyOut])
def my_families(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    return list_user_families(db, user_id=current.id)

@router.get("/{family_id}", response_model=FamilyOut)
def get_one(family_id: str, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    from sqlalchemy.orm import joinedload
    fam = db.query(Family).options(
        joinedload(Family.members).joinedload(FamilyMember.wallet),
        joinedload(Family.members).joinedload(FamilyMember.user)
    ).filter(Family.id == family_id).first()
    if not fam: 
        raise HTTPException(404, "Family not found")
    if not ensure_member(db, user_id=current.id, family_id=fam.id):
        raise HTTPException(403, "Not a member of this family")
    
    # Build members with wallet balance, username, and profile_pic
    members_out = []
    for member in fam.members:
        wallet_balance = member.wallet.balance if member.wallet else 0
        # Get user info for username, profile_pic, full_name, and email (loaded via joinedload)
        user = member.user
        username = user.username if user else None
        profile_pic = user.profile_pic if user else None
        full_name = user.full_name if user else None
        email = user.email if user else None
        
        member_dict = {
            "id": member.id,
            "family_id": member.family_id,
            "user_id": member.user_id,
            "role": member.role.value,
            "display_name": member.display_name,
            "avatar_url": member.avatar_url,
            "wallet_balance": wallet_balance,
            "username": username,
            "profile_pic": profile_pic,
            "full_name": full_name,
            "email": email,
        }
        members_out.append(MemberOut(**member_dict))
    
    return FamilyOut(
        id=fam.id,
        name=fam.name,
        secret_code=fam.secret_code,
        owner_id=fam.owner_id,
        members=members_out
    )

@router.post("/{family_id}/invite", response_model=InviteOut)
def make_invite(family_id: str, payload: InviteCreate, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    member = ensure_member(db, user_id=current.id, family_id=family_id)
    if not member or member.role != MemberRole.PARENT:
        raise HTTPException(403, "Only parents can create invites")
    inv = create_invite(db, family_id=family_id, created_by_member_id=member.id, expires_hours=payload.expires_hours)
    return inv

@router.post("/join/secret/{code}", response_model=MemberOut)
def join_secret(code: str, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    # normalize code to be forgiving
    code = code.strip().upper()

    fam = db.execute(select(Family).where(Family.secret_code == code)).scalar_one_or_none()
    if not fam:
        raise HTTPException(404, "Invalid secret code")

    if ensure_member(db, user_id=current.id, family_id=fam.id):
        raise HTTPException(409, "Already a member of this family")

    m = FamilyMember(family_id=fam.id, user_id=current.id, role=MemberRole.CHILD)
    db.add(m); db.flush()                 # get m.id without a full commit
    db.add(Wallet(member_id=m.id))        # create wallet now
    db.commit(); db.refresh(m)

    return m

@router.post("/join/invite/{code}", response_model=MemberOut)
def join_invite(code: str, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    m = accept_invite(db, code=code, user_id=current.id)
    if not m: 
        raise HTTPException(400, "Invalid/expired invite or already a member")
    return m
