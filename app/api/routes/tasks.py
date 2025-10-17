from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...schemas.task import TaskCreate, TaskOut
from ...services.task_service import create_task, assign_task, complete_assignment, approve_assignment
from ...services.family_service import ensure_member
from ...models.family_member import MemberRole
from ...models.user import User
from ..deps import get_db, get_current_user
router = APIRouter()

@router.post("/families/{family_id}/tasks", response_model=TaskOut)
def create_family_task(family_id: str, payload: TaskCreate, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    member = ensure_member(db, user_id=current.id, family_id=family_id)
    if not member or member.role != MemberRole.PARENT:
        raise HTTPException(403, "Only parents can create tasks")
    t = create_task(db, family_id=family_id, title=payload.title, description=payload.description, deadline=payload.deadline, points_value=payload.points_value, created_by_member_id=member.id)
    return t

@router.post("/tasks/{task_id}/assign/{assignee_member_id}", response_model=dict)
def assign(task_id: str, assignee_member_id: str, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    a = assign_task(db, task_id=task_id, assignee_id=assignee_member_id)
    return {"assignment_id": a.id}

@router.post("/assignments/{assignment_id}/complete", response_model=dict)
def complete(assignment_id: str, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    # simplified: caller must be the assignee; you'd map user->member in your app logic
    a = complete_assignment(db, assignment_id=assignment_id, by_member_id=None)
    if not a:
        raise HTTPException(400, "Cannot complete assignment")
    return {"ok": True}

@router.post("/assignments/{assignment_id}/approve", response_model=dict)
def approve(assignment_id: str, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    a = approve_assignment(db, assignment_id=assignment_id, by_parent_member_id=None)
    if not a:
        raise HTTPException(400, "Cannot approve assignment")
    return {"ok": True}
