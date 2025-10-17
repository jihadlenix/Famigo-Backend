from sqlalchemy.orm import Session
from sqlalchemy import select
from ..models.reward import Reward, Redemption, RedemptionStatus
from ..models.points import Wallet, Transaction, TransactionType
from ..models import utcnow

def create_reward(db: Session, *, family_id: str, title: str, description: str | None, cost_points: int) -> Reward:
    r = Reward(family_id=family_id, title=title, description=description, cost_points=cost_points)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r

def request_redemption(db: Session, *, reward_id: str, request_by_member_id: str | None) -> Redemption | None:
    reward = db.get(Reward, reward_id)
    if not reward or not reward.is_active:
        return None
    red = Redemption(reward_id=reward_id, requested_by_member_id=request_by_member_id)
    db.add(red)
    db.commit()
    db.refresh(red)
    return red

def approve_redemption(db: Session, *, redemption_id: str, approved_by_member_id: str | None) -> Redemption | None:
    red = db.get(Redemption, redemption_id)
    if not red or red.status != RedemptionStatus.REQUESTED:
        return None
    reward = db.get(Reward, red.reward_id)
    wallet = db.execute(select(Wallet).where(Wallet.member_id==red.requested_by_member_id)).scalar_one()
    if wallet.balance < reward.cost_points:
        return None
    wallet.balance -= reward.cost_points
    txn = Transaction(wallet_id=wallet.id, amount=-reward.cost_points, type=TransactionType.SPEND,
                      reason=f"Redeem '{reward.title}'", redemption_id=red.id, created_by_member_id=approved_by_member_id)
    db.add(txn)
    red.approved_by_member_id = approved_by_member_id
    red.status = RedemptionStatus.APPROVED
    red.updated_at = utcnow()
    db.commit()
    db.refresh(red)
    return red

def deliver_redemption(db: Session, *, redemption_id: str) -> Redemption | None:
    red = db.get(Redemption, redemption_id)
    if not red or red.status != RedemptionStatus.APPROVED:
        return None
    red.status = RedemptionStatus.REDEEMED
    red.redeemed_at = utcnow()
    red.updated_at = red.redeemed_at
    db.commit()
    db.refresh(red)
    return red
