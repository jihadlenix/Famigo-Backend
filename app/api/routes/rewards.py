from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ...schemas.reward import RewardCreate, RewardOut, RedemptionOut
from ...services.reward_service import (
    create_reward,
    request_redemption,
    approve_redemption,
    deliver_redemption,
)
from ...services.family_service import ensure_member
from ...models.family_member import MemberRole
from ...models.user import User

# MODELS
from ...models.reward import Reward, Redemption, RedemptionStatus
from ...models.points import Wallet      # <-- Wallet is defined in points.py

from ..deps import get_db, get_current_user


router = APIRouter()


@router.post("/families/{family_id}/rewards", response_model=RewardOut)
def create_family_reward(
    family_id: str,
    payload: RewardCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    member = ensure_member(db, user_id=current.id, family_id=family_id)
    if not member or member.role != MemberRole.PARENT:
        raise HTTPException(403, "Only parents can create rewards")

    r = create_reward(
        db,
        family_id=family_id,
        title=payload.title,
        description=payload.description,
        cost_points=payload.cost_points,
    )
    return r


@router.post("/rewards/{reward_id}/redeem")
def redeem_now(
    reward_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    # 1) Load reward
    reward = db.get(Reward, reward_id)
    if not reward:
        raise HTTPException(404, "Reward not found")

    # 2) Ensure current user is member of this family
    member = ensure_member(db, user_id=current.id, family_id=reward.family_id)
    if not member:
        raise HTTPException(403, "You are not a member of this family")

    # 2.5) Only children can redeem rewards, not parents
    if member.role == MemberRole.PARENT:
        raise HTTPException(403, "Parents cannot redeem rewards")

    # 3) Load this member's wallet
    wallet = db.query(Wallet).filter(Wallet.member_id == member.id).first()
    if not wallet:
        raise HTTPException(404, "Wallet not found")

    # 4) Check enough points
    if wallet.balance < reward.cost_points:
        raise HTTPException(400, "Not enough points")

    # 5) Deduct and create redemption
    wallet.balance -= reward.cost_points

    red = Redemption(
        reward_id=reward.id,
        requested_by_member_id=member.id,
        approved_by_member_id=member.id,  # auto-approve
        status=RedemptionStatus.REDEEMED,
        redeemed_at=datetime.now(timezone.utc),
    )

    db.add(red)
    db.commit()
    db.refresh(red)
    db.refresh(wallet)

    return {
        "success": True,
        "remaining_points": wallet.balance,
    }


@router.post("/redemptions/{redemption_id}/approve", response_model=RedemptionOut)
def approve(
    redemption_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    red = approve_redemption(
        db,
        redemption_id=redemption_id,
        approved_by_member_id=None,
    )
    if not red:
        raise HTTPException(400, "Cannot approve redemption")
    return red


@router.post("/redemptions/{redemption_id}/deliver", response_model=RedemptionOut)
def deliver(
    redemption_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    red = deliver_redemption(db, redemption_id=redemption_id)
    if not red:
        raise HTTPException(400, "Cannot deliver redemption")
    return red


@router.get("/families/{family_id}/members/{member_id}/redemptions", response_model=list[RedemptionOut])
def get_member_redemptions(
    family_id: str,
    member_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """
    Get all redeemed items for a specific family member.
    Parents can view their children's redemptions.
    """
    # Ensure current user is a member of the family
    current_member = ensure_member(db, user_id=current.id, family_id=family_id)
    if not current_member:
        raise HTTPException(403, "You are not a member of this family")
    
    # Get the target member
    from ...models.family_member import FamilyMember
    target_member = db.get(FamilyMember, member_id)
    if not target_member or target_member.family_id != family_id:
        raise HTTPException(404, "Member not found in this family")
    
    # Only allow if:
    # 1. Viewing own redemptions, OR
    # 2. Current user is a parent viewing a child's redemptions
    if current_member.id != member_id:
        if current_member.role != MemberRole.PARENT or target_member.role != MemberRole.CHILD:
            raise HTTPException(403, "You can only view your own redemptions or your children's redemptions")
    
    # Get all redeemed items for this member with reward info
    from sqlalchemy.orm import joinedload
    redemptions = db.query(Redemption).options(
        joinedload(Redemption.reward)
    ).filter(
        and_(
            Redemption.requested_by_member_id == member_id,
            Redemption.status == RedemptionStatus.REDEEMED
        )
    ).order_by(Redemption.redeemed_at.desc()).all()
    
    # Build response with reward title
    result = []
    for red in redemptions:
        red_dict = {
            "id": red.id,
            "reward_id": red.reward_id,
            "requested_by_member_id": red.requested_by_member_id,
            "approved_by_member_id": red.approved_by_member_id,
            "status": red.status,
            "created_at": red.created_at,
            "updated_at": red.updated_at,
            "redeemed_at": red.redeemed_at,
            "reward_title": red.reward.title if red.reward else None,
        }
        result.append(RedemptionOut(**red_dict))
    
    return result


@router.get("/families/{family_id}/rewards", response_model=list[RewardOut])
def list_family_rewards(
    family_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    member = ensure_member(db, user_id=current.id, family_id=family_id)
    if not member:
        raise HTTPException(403, "You are not a member of this family")

    rewards = db.query(Reward).filter(Reward.family_id == family_id).all()
    
    # Check which rewards have been redeemed by this member
    reward_ids = [r.id for r in rewards]
    redeemed_reward_ids = set()
    if reward_ids:
        redemptions = db.query(Redemption).filter(
            and_(
                Redemption.reward_id.in_(reward_ids),
                Redemption.requested_by_member_id == member.id,
                Redemption.status == RedemptionStatus.REDEEMED
            )
        ).all()
        redeemed_reward_ids = {r.reward_id for r in redemptions}
    
    # Build response with is_redeemed flag
    result = []
    for reward in rewards:
        reward_dict = {
            "id": reward.id,
            "family_id": reward.family_id,
            "title": reward.title,
            "description": reward.description,
            "cost_points": reward.cost_points,
            "is_active": reward.is_active,
            "is_redeemed": reward.id in redeemed_reward_ids,
        }
        result.append(RewardOut(**reward_dict))
    
    return result
