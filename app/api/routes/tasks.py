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
    "/tasks/{task_id}/assign/{assignee_member_id}",
    response_model=dict,
    summary="Assign Task",
    description="""
    Assign a task to a family member.

    **Who can use it:**  
    - Parents can assign tasks to any child.  
    - Members can assign tasks to themselves (self-assign).

    **Path Parameters:**  
    - `task_id`: ID of the task  
    - `assignee_member_id`: Family member who will perform the task  

    **Returns:**  
    The new assignment ID (`assignment_id`).
    """,
)
def assign(
    task_id: str,
    assignee_member_id: str,   # can be FamilyMember.id or User.id
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    # 1) Load task and its family
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    family = db.get(Family, task.family_id)
    if not family:
        raise HTTPException(404, "Family not found")

    # 2) Resolve caller (must be member or owner)
    caller_member = db.execute(
        select(FamilyMember).where(
            FamilyMember.user_id == current.id,
            FamilyMember.family_id == family.id,
        )
    ).scalar_one_or_none()
    is_owner = (family.owner_id == current.id)
    if not (caller_member or is_owner):
        raise HTTPException(403, "You are not a member or owner of this family")

    # 3) Resolve ASSIGNEE: accept FamilyMember.id OR User.id
    assignee = db.get(FamilyMember, assignee_member_id)
    if not assignee:
        # maybe a user_id was provided – map it to the family member
        assignee = db.execute(
            select(FamilyMember).where(
                FamilyMember.user_id == assignee_member_id,
                FamilyMember.family_id == family.id,
            )
        ).scalar_one_or_none()

    if not assignee:
        raise HTTPException(404, "Assignee not found in this family")

    # 4) Permission checks:
    #    - owner can assign anyone
    #    - parents can assign anyone
    #    - members can only self-assign
    is_self_assign = caller_member and (caller_member.id == assignee.id)

    if not is_owner:
        if not caller_member:
            raise HTTPException(403, "No family membership found")
        if not (is_self_assign or caller_member.role == MemberRole.PARENT):
            raise HTTPException(403, "Only parents or the owner can assign tasks")

    # 5) Do assignment (service already checks same-family & idempotency)
    try:
        a = assign_task(db, task_id=task_id, assignee_id=assignee.id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {"assignment_id": a.id}

# ------------------------------------------------------------------------
# Complete a task
# ------------------------------------------------------------------------
@router.post(
    "/assignments/{assignment_id}/complete",
    response_model=dict,
    summary="Complete Task",
    description="""
    Mark a task assignment as completed by the assignee.

    When completed, the user's wallet is automatically **credited**
    with the task's reward points.

    **Who can use it:**  
    - Only the assignee of the task.

    **Path Parameters:**  
    - `assignment_id`: The assignment to mark as complete  

    **Returns:**  
    `{ "ok": true }` on success.
    """,
)
def complete(
    assignment_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    # 1) Load assignment and related task
    assignment = db.get(TaskAssignment, assignment_id)
    if not assignment:
        raise HTTPException(404, "Assignment not found")

    task = db.get(Task, assignment.task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    # 2) Find the caller's member record in the SAME family as the task
    caller_member = db.execute(
        select(FamilyMember).where(
            FamilyMember.user_id == current.id,
            FamilyMember.family_id == task.family_id,
        )
    ).scalar_one_or_none()

    if not caller_member:
        raise HTTPException(403, "You are not a member of this family")

    # 3) Only the assignee can complete their own assignment
    if assignment.assignee_id != caller_member.id:
        raise HTTPException(403, "Only the assignee can complete this task")

    # 4) Complete (this will also credit wallet immediately per your service)
    a = complete_assignment(
        db, assignment_id=assignment_id, by_member_id=caller_member.id
    )
    if not a:
        raise HTTPException(400, "Cannot complete assignment")

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
