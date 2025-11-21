from enum import StrEnum
from sqlalchemy import String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import uuid4

from app.models.family_member import FamilyMember
from ..db.base_class import Base
from . import utcnow

class Wallet(Base):
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    member_id: Mapped[str] = mapped_column(String(36), ForeignKey("familymember.id", ondelete="CASCADE"), unique=True, index=True)
    balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    member: Mapped["FamilyMember"] = relationship(back_populates="wallet")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="wallet", cascade="all,delete-orphan")

class TransactionType(StrEnum):
    EARN = "EARN"
    SPEND = "SPEND"
    ADJUST = "ADJUST"

class Transaction(Base):
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    wallet_id: Mapped[str] = mapped_column(String(36), ForeignKey("wallet.id", ondelete="CASCADE"), index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[TransactionType] = mapped_column()
    reason: Mapped[str | None] = mapped_column(Text)
    task_assignment_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("taskassignment.id", ondelete="SET NULL"))
    redemption_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("redemption.id", ondelete="SET NULL"))
    created_by_member_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("familymember.id", ondelete="SET NULL"))
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    wallet: Mapped["Wallet"] = relationship(back_populates="transactions")
