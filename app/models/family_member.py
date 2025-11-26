from __future__ import annotations
from typing import TYPE_CHECKING
from enum import StrEnum
from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import uuid4
from ..db.base_class import Base
from . import utcnow

if TYPE_CHECKING:
    from .user import User
    from .family import Family
    from .points import Wallet
    from .task import TaskAssignment
    from .reward import Redemption

class MemberRole(StrEnum):
    PARENT = "PARENT"
    CHILD = "CHILD"

class FamilyMember(Base):
    __table_args__ = (UniqueConstraint("user_id", "family_id", name="uq_member_user_family"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    family_id: Mapped[str] = mapped_column(String(36), ForeignKey("family.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id", ondelete="CASCADE"), index=True)
    role: Mapped[MemberRole] = mapped_column(default=MemberRole.CHILD)
    display_name: Mapped[str | None] = mapped_column(String(128))
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="memberships")
    family: Mapped["Family"] = relationship(back_populates="members")
    wallet: Mapped["Wallet"] = relationship(back_populates="member", uselist=False, cascade="all,delete-orphan")

    assignments: Mapped[list["TaskAssignment"]] = relationship(
        back_populates="assignee",
        cascade="all,delete-orphan",
        foreign_keys="TaskAssignment.assignee_id",
    )
    redemptions: Mapped[list["Redemption"]] = relationship(
        back_populates="requested_by",
        foreign_keys="Redemption.requested_by_member_id",
    )
