from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from ..models.task import Task, TaskAssignment, TaskStatus
from ..models.family_member import FamilyMember
from ..models.points import Wallet, Transaction, TransactionType
from ..models import utcnow

from sqlalchemy import select, and_, distinct
from typing import Optional
from ..models.family_member import MemberRole

def _get_task(db: Session, task_id: str) -> Task | None:
    return db.get(Task, task_id)

def _get_member(db: Session, member_id: str) -> FamilyMember | None:
    return db.get(FamilyMember, member_id)

def _get_wallet(db: Session, member_id: str) -> Wallet | None:
    return db.execute(select(Wallet).where(Wallet.member_id == member_id)).scalar_one_or_none()

def create_task(
    db: Session, *,
    family_id: str,
    title: str,
    description: str | None,
    deadline,
    points_value: int,
    created_by_member_id: str | None
) -> Task:
    t = Task(
        family_id=family_id,
        title=title,
        description=description,
        deadline=deadline,
        points_value=points_value,
        created_by_member_id=created_by_member_id,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t

def assign_task(db: Session, *, task_id: str, assignee_id: str) -> TaskAssignment:
    task = _get_task(db, task_id)
    assignee = _get_member(db, assignee_id)
    if not task or not assignee:
        raise ValueError("Task or assignee not found")
    # must be same family
    if assignee.family_id != task.family_id:
        raise ValueError("Assignee is not in the same family as the task")
    # idempotent: avoid duplicate (task_id, assignee_id)
    existing = db.execute(
        select(TaskAssignment).where(
            and_(TaskAssignment.task_id == task_id, TaskAssignment.assignee_id == assignee_id)
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    a = TaskAssignment(task_id=task_id, assignee_id=assignee_id)
    db.add(a)
    if task.status == TaskStatus.OPEN:
        task.status = TaskStatus.IN_PROGRESS
    db.commit()
    db.refresh(a)
    return a

def complete_assignment(db: Session, *, assignment_id: str, by_member_id: str) -> TaskAssignment | None:
    a = db.get(TaskAssignment, assignment_id)
    if not a: 
        return None
    # only the assignee can complete
    if a.assignee_id != by_member_id: 
        return None
    if a.is_completed:
        # already completed -> idempotent
        return a

    # mark completed
    a.is_completed = True
    a.completed_at = utcnow()

    # credit points immediately to the assignee's wallet
    task = _get_task(db, a.task_id)
    wallet = _get_wallet(db, a.assignee_id)
    if task and wallet and task.points_value:
        wallet.balance += task.points_value
        txn = Transaction(
            wallet_id=wallet.id,
            amount=task.points_value,
            type=TransactionType.EARN,
            reason=f"Task '{task.title}' completed",
            task_assignment_id=a.id,
            created_by_member_id=by_member_id,
        )
        db.add(txn)

    db.commit()
    db.refresh(a)

    # if ALL assignments are completed, mark the task DONE; else IN_PROGRESS
    if task:
        all_completed = all(x.is_completed for x in task.assignments)
        task.status = TaskStatus.DONE if all_completed else TaskStatus.IN_PROGRESS
        db.commit()

    return a

# --- NEW: update task with permissions (creator OR parent in same family) ---
def update_task(
    db: Session,
    *,
    task_id: str,
    editor_member_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    deadline = None,
    points_value: Optional[int] = None,
) -> Task | None:
    task = db.get(Task, task_id)
    if not task:
        return None

    editor = db.get(FamilyMember, editor_member_id)
    if not editor or editor.family_id != task.family_id:
        # must be in same family
        return None

    is_creator = (task.created_by_member_id == editor_member_id)
    is_parent = (editor.role == MemberRole.PARENT)
    if not (is_creator or is_parent):
        # only creator or any parent in the family can edit
        return None
    
    any_completed = any(a.is_completed for a in task.assignments)
    if any_completed or task.status == TaskStatus.DONE:
        raise ValueError("Task is locked after completion and cannot be edited.")

    if title is not None:
        task.title = title
    if description is not None:
        task.description = description
    if deadline is not None:
        task.deadline = deadline
    if points_value is not None:
        task.points_value = points_value

    db.commit()
    db.refresh(task)
    return task

# --- NEW: list all tasks assigned to a user's memberships (across families) ---
def list_tasks_for_user(db: Session, *, user_id: str) -> list[Task]:
    stmt = (
        select(Task)
        .join(TaskAssignment, TaskAssignment.task_id == Task.id)
        .join(FamilyMember, FamilyMember.id == TaskAssignment.assignee_id)
        .where(FamilyMember.user_id == user_id)
        .distinct()  # <-- distinct on the whole rowset
    )
    return db.execute(stmt).scalars().all()

# --- NEW: list all tasks in a family (visible to any member) ---
def list_tasks_for_family(db: Session, *, family_id: str) -> list[Task]:
    return db.execute(select(Task).where(Task.family_id == family_id)).scalars().all()