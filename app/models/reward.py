from enum import StrEnum
from uuid import uuid4

from sqlalchemy import String, DateTime, ForeignKey, Integer, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .family import Family
from .family_member import FamilyMember
from ..db.base_class import Base
from . import utcnow


class Reward(Base):
    __tablename__ = "reward"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    family_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("family.id", ondelete="CASCADE"),
        index=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cost_points: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    family: Mapped["Family"] = relationship(back_populates="rewards")
    redemptions: Mapped[list["Redemption"]] = relationship(
        back_populates="reward",
        cascade="all,delete-orphan",
    )


class RedemptionStatus(StrEnum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REDEEMED = "REDEEMED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class Redemption(Base):
    __tablename__ = "redemption"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    reward_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("reward.id", ondelete="CASCADE"),
        index=True,
    )

    requested_by_member_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("familymember.id", ondelete="CASCADE"),
        index=True,
    )

    approved_by_member_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("familymember.id", ondelete="SET NULL"),
    )

    status: Mapped[RedemptionStatus] = mapped_column(
        default=RedemptionStatus.REQUESTED,
        index=True,
    )

    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    redeemed_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))

    reward: Mapped["Reward"] = relationship(back_populates="redemptions")
    requested_by: Mapped["FamilyMember"] = relationship(
        back_populates="redemptions",
        foreign_keys=[requested_by_member_id],
    )
    approved_by: Mapped["FamilyMember | None"] = relationship(
        foreign_keys=[approved_by_member_id]
    )
