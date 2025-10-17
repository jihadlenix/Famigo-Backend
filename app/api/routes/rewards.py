from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...schemas.reward import RewardCreate, RewardOut, RedemptionOut
from ...services.reward_service import create_reward, request_redemption, approve_redemption, deliver_redemption
from ...services.family_service import ensure_member
from ...models.family_member import MemberRole
from ...models.user import User
from ..deps import get_db, get_current_user
router = APIRouter()
@router.post("/families/{family_id}/rewards", response_model=RewardOut)
def create_family_reward(family_id: str, payload: RewardCreate, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    member = ensure_member(db, user_id=current.id, family_id=family_id)
    if not member or member.role != MemberRole.PARENT:
        raise HTTPException(403, "Only parents can create rewards")
    r = create_reward(db, family_id=family_id, title=payload.title, description=payload.description, cost_points=payload.cost_points)
    return r

@router.post("/rewards/{reward_id}/redeem", response_model=RedemptionOut)
def redeem(reward_id: str, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    red = request_redemption(db, reward_id=reward_id, request_by_member_id=None)
    if not red: 
        raise HTTPException(400, "Cannot request redemption")
    return red

@router.post("/redemptions/{redemption_id}/approve", response_model=RedemptionOut)
def approve(redemption_id: str, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    red = approve_redemption(db, redemption_id=redemption_id, approved_by_member_id=None)
    if not red: 
        raise HTTPException(400, "Cannot approve redemption")
    return red

@router.post("/redemptions/{redemption_id}/deliver", response_model=RedemptionOut)
def deliver(redemption_id: str, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    red = deliver_redemption(db, redemption_id=redemption_id)
    if not red: 
        raise HTTPException(400, "Cannot deliver redemption")
    return red
