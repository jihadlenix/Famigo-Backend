from enum import StrEnum
from sqlalchemy import String, DateTime, ForeignKey, Integer, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import uuid4

from app.models.family import Family
from app.models.family_member import FamilyMember
from ..db.base_class import Base
from . import utcnow
class TaskStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    EXPIRED = "EXPIRED"

class Task(Base):
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    family_id: Mapped[str] = mapped_column(String(36), ForeignKey("family.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    deadline: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    status: Mapped[TaskStatus] = mapped_column(default=TaskStatus.OPEN, index=True)
    points_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by_member_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("familymember.id", ondelete="SET NULL"))
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    family: Mapped["Family"] = relationship(back_populates="tasks")
    created_by: Mapped["FamilyMember | None"] = relationship(foreign_keys=[created_by_member_id])
    assignments: Mapped[list["TaskAssignment"]] = relationship(back_populates="task", cascade="all,delete-orphan")

class TaskAssignment(Base):
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("task.id", ondelete="CASCADE"), index=True)
    assignee_id: Mapped[str] = mapped_column(String(36), ForeignKey("familymember.id", ondelete="CASCADE"), index=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    completed_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    approved_by_member_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("familymember.id", ondelete="SET NULL"))
    approved_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    task: Mapped["Task"] = relationship(back_populates="assignments")
    assignee: Mapped["FamilyMember"] = relationship(back_populates="assignments", foreign_keys=[assignee_id])
    approved_by: Mapped["FamilyMember | None"] = relationship(foreign_keys=[approved_by_member_id])
