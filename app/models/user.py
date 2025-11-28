from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, Boolean, DateTime, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import uuid4
from ..db.base_class import Base
from . import utcnow

if TYPE_CHECKING:
    from .family import Family
    from .family_member import FamilyMember
    from .auth import RefreshToken
    from .points import Wallet  # 👈 for type hint clarity

class User(Base):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(128))
    profile_pic: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # ✅ added
    age: Mapped[int] = mapped_column(Integer, nullable=False)  # Age in years (required)

    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    memberships: Mapped[list["FamilyMember"]] = relationship(back_populates="user", cascade="all,delete-orphan")
    owned_families: Mapped[list["Family"]] = relationship(back_populates="owner")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all,delete-orphan")
    cartoon_avatar: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    wallet: Mapped["Wallet"] = relationship(
        "Wallet",
        secondary="familymember",
        primaryjoin="User.id == FamilyMember.user_id",
        secondaryjoin="FamilyMember.id == Wallet.member_id",
        viewonly=True,
        uselist=False,
    )
