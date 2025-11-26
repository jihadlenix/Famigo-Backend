from __future__ import annotations
from sqlalchemy import String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import uuid4
from ..db.base_class import Base
from . import utcnow

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .user import User

class RefreshToken(Base):
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id", ondelete="CASCADE"), index=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))


    user: Mapped["User"] = relationship(back_populates="refresh_tokens")
