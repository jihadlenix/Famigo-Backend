from sqlalchemy.orm import Session
from sqlalchemy import select
from ..models.task import Task, TaskAssignment, TaskStatus
from ..models.family_member import FamilyMember
from ..models.points import Wallet, Transaction, TransactionType
from ..models import utcnow

def create_task(db: Session, *, family_id: str, title: str, description: str | None, deadline, points_value: int, created_by_member_id: str | None) -> Task:
    t = Task(family_id=family_id, title=title, description=description, deadline=deadline, points_value=points_value, created_by_member_id=created_by_member_id)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t

def assign_task(db: Session, *, task_id: str, assignee_id: str) -> TaskAssignment:
    a = TaskAssignment(task_id=task_id, assignee_id=assignee_id)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a

def complete_assignment(db: Session, *, assignment_id: str, by_member_id: str | None) -> TaskAssignment | None:
    a = db.get(TaskAssignment, assignment_id)
    if not a: 
        return None
    if by_member_id and a.assignee_id != by_member_id: 
        return None
    a.is_completed = True
    a.completed_at = utcnow()
    db.commit()
    db.refresh(a)
    return a

def approve_assignment(db: Session, *, assignment_id: str, by_parent_member_id: str | None) -> TaskAssignment | None:
    a = db.get(TaskAssignment, assignment_id)
    if not a: 
        return None
    task = db.get(Task, a.task_id)
    assignee = db.get(FamilyMember, a.assignee_id)
    if not task or not assignee: 
        return None
    a.approved_by_member_id = by_parent_member_id
    a.approved_at = utcnow()
    wallet = db.execute(select(Wallet).where(Wallet.member_id==assignee.id)).scalar_one()
    wallet.balance += task.points_value
    txn = Transaction(wallet_id=wallet.id, amount=task.points_value, type=TransactionType.EARN,
                      reason=f"Task '{task.title}' approved", task_assignment_id=a.id, created_by_member_id=by_parent_member_id)
    db.add(txn)
    db.commit()
    db.refresh(a)
    task_done = all(x.approved_at is not None for x in task.assignments)
    task.status = TaskStatus.DONE if task_done else TaskStatus.IN_PROGRESS
    db.commit()
    return a
