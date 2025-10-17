from sqlalchemy import String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import uuid4

from app.models.family import Family
from ..db.base_class import Base

class FamilyInvite(Base):
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    family_id: Mapped[str] = mapped_column(String(36), ForeignKey("family.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    created_by_member_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("familymember.id", ondelete="SET NULL"))
    expires_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    used_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("user.id", ondelete="SET NULL"))
    used_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    family: Mapped["Family"] = relationship(back_populates="invites")
