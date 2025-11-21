from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import uuid4
from ..db.base_class import Base
from . import utcnow

if TYPE_CHECKING:
    from .user import User
    from .family_member import FamilyMember
    from .task import Task
    from .reward import Reward
    from .invite import FamilyInvite

class Family(Base):
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    secret_code: Mapped[str] = mapped_column(String(12), unique=True, index=True, nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("user.id", ondelete="SET NULL"))
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    owner: Mapped["User"] = relationship(back_populates="owned_families")
    members: Mapped[list["FamilyMember"]] = relationship(back_populates="family", cascade="all,delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="family", cascade="all,delete-orphan")
    rewards: Mapped[list["Reward"]] = relationship(back_populates="family", cascade="all,delete-orphan")
    invites: Mapped[list["FamilyInvite"]] = relationship(back_populates="family", cascade="all,delete-orphan")
