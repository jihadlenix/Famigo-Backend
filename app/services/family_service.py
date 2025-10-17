import secrets
from datetime import timedelta, timezone, datetime
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..models.family import Family
from ..models.family_member import FamilyMember, MemberRole
from ..models.points import Wallet
from ..models.invite import FamilyInvite


def _code(n=12) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(n))

def create_family(db: Session, *, owner_user_id: str, name: str) -> Family:
    fam = Family(name=name, secret_code=_code(), owner_id=owner_user_id)
    db.add(fam)
    db.commit() 
    db.refresh(fam)
    member = FamilyMember(family_id=fam.id, user_id=owner_user_id, role=MemberRole.PARENT)
    db.add(member)
    db.commit() 
    db.refresh(member)
    db.add(Wallet(member_id=member.id))
    db.commit()
    return fam

def list_user_families(db: Session, *, user_id: str) -> list[Family]:
    q = select(Family).join(Family.members).where(FamilyMember.user_id==user_id)
    return list(db.execute(q).scalars())

def get_family(db: Session, family_id: str) -> Family | None:
    return db.get(Family, family_id)

def ensure_member(db: Session, *, user_id: str, family_id: str) -> FamilyMember | None:
    return db.execute(select(FamilyMember).where(FamilyMember.user_id==user_id, FamilyMember.family_id==family_id)).scalar_one_or_none()

def join_by_secret(db: Session, *, user_id: str, code: str) -> FamilyMember | None:
    fam = db.execute(select(Family).where(Family.secret_code==code)).scalar_one_or_none()
    if not fam: 
        return None
    if ensure_member(db, user_id=user_id, family_id=fam.id):
        return None
    member = FamilyMember(family_id=fam.id, user_id=user_id, role=MemberRole.CHILD)
    db.add(member)
    db.commit()
    db.refresh(member)
    db.add(Wallet(member_id=member.id))
    db.commit()
    return member

def create_invite(db: Session, *, family_id: str, created_by_member_id: str, expires_hours: int | None) -> FamilyInvite:
    inv = FamilyInvite(family_id=family_id, code=_code(10), created_by_member_id=created_by_member_id)
    if expires_hours:
        inv.expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv

def accept_invite(db: Session, *, code: str, user_id: str) -> FamilyMember | None:
    inv = db.execute(select(FamilyInvite).where(FamilyInvite.code==code)).scalar_one_or_none()
    if not inv or inv.revoked: 
        return None
    if inv.expires_at and inv.expires_at < datetime.now(timezone.utc): 
        return None
    if inv.used_by_user_id: 
        return None
    existing = ensure_member(db, user_id=user_id, family_id=inv.family_id)
    if existing: 
        return None
    member = FamilyMember(family_id=inv.family_id, user_id=user_id)
    db.add(member)
    db.commit()
    db.refresh(member)
    db.add(Wallet(member_id=member.id))
    db.commit()
    inv.used_by_user_id = user_id
    inv.used_at = datetime.now(timezone.utc)
    db.commit()
    return member
