from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List

from sqlalchemy import select
from ...models.task import Task, TaskAssignment
from ...models.family_member import FamilyMember, MemberRole
from ...models.family import Family

from pydantic import BaseModel
from ...schemas.task import TaskCreate, TaskOut
from ...services.task_service import (
    create_task,
    assign_task,
    complete_assignment,
    update_task,
    list_tasks_for_user,
    list_tasks_for_family,
)
from ...services.family_service import ensure_member
from ...models.family_member import MemberRole
from ...models.user import User
from ..deps import get_db, get_current_user

router = APIRouter()


# Inline update schema (to keep schemas package untouched)
class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    points_value: Optional[int] = None

class AssignPayload(BaseModel):
    username: str
# ------------------------------------------------------------------------
#  Create a new task
# ------------------------------------------------------------------------
@router.post(
    "/families/{family_id}/tasks",
    response_model=TaskOut,
    summary="Create Family Task",
    description="""
    Create a new task within a specific family.

    **Who can use it:**  
    Any authenticated family member.

    **Body Parameters:**  
    - `title`: Task title  
    - `description` (optional): Task details  
    - `deadline` (optional): Due date  
    - `points_value`: Reward points given when completed  

    **Returns:**  
    The newly created `TaskOut` object.
    """,
)
def create_family_task(
    family_id: str,
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    member = ensure_member(db, user_id=current.id, family_id=family_id)
    if not member:
        raise HTTPException(403, "You are not a member of this family")

    t = create_task(
        db,
        family_id=family_id,
        title=payload.title,
        description=payload.description,
        deadline=payload.deadline,
        points_value=payload.points_value,
        created_by_member_id=member.id,
    )
    return t


# ------------------------------------------------------------------------
#  Assign a task
# ------------------------------------------------------------------------
@router.post(
    "/tasks/{task_id}/assign",
    response_model=dict,
    summary="Assign Task (by username)",
    description="""
    Assign a task to a family member using their username.

    Body:
    - username: the username of the user who should receive the task
    """,
)
def assign(
    task_id: str,
    payload: AssignPayload,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    # 1) Load the task
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    # 2) Load the family
    family = db.get(Family, task.family_id)
    if not family:
        raise HTTPException(404, "Family not found")

    # 3) Determine who is calling the endpoint
    caller_member = db.execute(
        select(FamilyMember).where(
            FamilyMember.user_id == current.id,
            FamilyMember.family_id == family.id,
        )
    ).scalar_one_or_none()

    is_owner = (family.owner_id == current.id)

    if not (caller_member or is_owner):
        raise HTTPException(403, "You are not a member or the owner of this family")

    # 4) Resolve assignee BY USERNAME
    username = payload.username.strip().lower()

    user = db.execute(
        select(User).where(User.username == username)
    ).scalar_one_or_none()

    if not user:
        raise HTTPException(404, "No user found with that username")

    # 5) Find the family member record for that user
    assignee = db.execute(
        select(FamilyMember).where(
            FamilyMember.user_id == user.id,
            FamilyMember.family_id == family.id,
        )
    ).scalar_one_or_none()

    if not assignee:
        raise HTTPException(404, "This user is not a member of this family")

    # 6) Permission logic
    is_self_assign = caller_member and (caller_member.id == assignee.id)

    if not is_owner:
        if not caller_member:
            raise HTTPException(403, "No family membership found")

        if not (is_self_assign or caller_member.role == MemberRole.PARENT):
            raise HTTPException(403, "Only parents or the owner can assign tasks")

    # 7) Perform assignment
    try:
        a = assign_task(db, task_id=task_id, assignee_id=assignee.id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {"assignment_id": a.id}
# ------------------------------------------------------------------------
# Complete a task
# ------------------------------------------------------------------------
@router.post(
    "/tasks/{task_id}/complete",
    response_model=dict,
    summary="Complete Task (by task ID)",
    description="Complete a task using its ID. Automatically credits the user's wallet.",
)
def complete_task(
    task_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    # 1) Load task
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    # 2) Find current user's family member record
    member = db.execute(
        select(FamilyMember).where(
            FamilyMember.user_id == current.id,
            FamilyMember.family_id == task.family_id,
        )
    ).scalar_one_or_none()

    if not member:
        raise HTTPException(403, "You are not a member of this family")

    # 3) Find the assignment for THIS user & THIS task
    assignment = db.execute(
        select(TaskAssignment).where(
            TaskAssignment.task_id == task_id,
            TaskAssignment.assignee_id == member.id
        )
    ).scalar_one_or_none()

    if not assignment:
        raise HTTPException(404, "No assignment found for this user on this task")

    # 4) Complete assignment through service (also credits wallet)
    try:
        complete_assignment(
            db,
            assignment_id=assignment.id,
            by_member_id=member.id
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {"ok": True}

# ------------------------------------------------------------------------
#  Edit an existing task
# ------------------------------------------------------------------------
@router.patch(
    "/tasks/{task_id}",
    response_model=TaskOut,
    summary="Edit Task",
    description="""
    Update details of an existing task.

    **Who can use it:**  
    - The task creator  
    - Any parent in the family  

    **Editable Fields:**  
    - `title`  
    - `description`  
    - `deadline`  
    - `points_value`
    if task is done can't edit it  

    **Returns:**  
    Updated `TaskOut` object.
    """,
)
def edit_task(
    task_id: str,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    editor_member = db.execute(
        select(FamilyMember).where(
            FamilyMember.user_id == current.id,
            FamilyMember.family_id == task.family_id,
        )
    ).scalar_one_or_none()
    if not editor_member:
        raise HTTPException(403, "You are not a member of this family")

    try:
        t = update_task(
            db,
            task_id=task.id,
            editor_member_id=editor_member.id,
            title=payload.title,
            description=payload.description,
            deadline=payload.deadline,
            points_value=payload.points_value,
        )
    except ValueError as e:
        # when locked after completion
        raise HTTPException(status_code=400, detail=str(e))

    if not t:
        raise HTTPException(403, "You cannot edit this task")
    return t
# ------------------------------------------------------------------------
# Get all tasks assigned to the current user
# ------------------------------------------------------------------------
@router.get(
    "/me/tasks",
    response_model=List[TaskOut],
    summary="Get My Tasks",
    description="""
    Retrieve all tasks assigned to the currently logged-in user,
    across all families.

    **Who can use it:**  
    - Any authenticated user.

    **Returns:**  
    List of `TaskOut` objects for all tasks assigned to this user.
    """,
)
def my_tasks(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    tasks = list_tasks_for_user(db, user_id=current.id)
    return tasks


# ------------------------------------------------------------------------
# Get all tasks in a family
# ------------------------------------------------------------------------
@router.get(
    "/families/{family_id}/tasks",
    response_model=List[TaskOut],
    summary="Get Family Tasks",
    description="""
    Retrieve all tasks that belong to a specific family.

    **Who can use it:**  
    Any member of the family.

    **Path Parameter:**  
    - `family_id`: The ID of the family  

    **Returns:**  
    List of `TaskOut` objects containing all tasks in the family.
    """,
)
def family_tasks(
    family_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    member = ensure_member(db, user_id=current.id, family_id=family_id)
    if not member:
        raise HTTPException(403, "You are not a member of this family")
    return list_tasks_for_family(db, family_id=family_id)
@router.get(
    "/me/points",
    response_model=dict,
    summary="Get My Total Points",
    description="Returns the total wallet balance of the current user across all families.",
)
def my_points(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    # Find all families where the user is a member
    members = db.execute(
        select(FamilyMember).where(FamilyMember.user_id == current.id)
    ).scalars().all()

    total = 0

    for m in members:
        if m.wallet:
            total += m.wallet.balance

    return {"total_points": total}

@router.get(
    "/me/points",
    response_model=dict,
    summary="Get My Total Points",
    description="Returns the total wallet balance of the current user across all families.",
)
def my_points(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    # Find all families where the user is a member
    members = db.execute(
        select(FamilyMember).where(FamilyMember.user_id == current.id)
    ).scalars().all()

    total = 0

    for m in members:
        if m.wallet:
            total += m.wallet.balance

    return {"total_points": total}
