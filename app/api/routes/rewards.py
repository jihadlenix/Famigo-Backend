from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

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
    return rewards
