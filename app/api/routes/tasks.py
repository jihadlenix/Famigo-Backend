from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List

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
    assignee_member_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    caller = ensure_member(
        db,
        user_id=current.id,
        family_id=None,
        require_same_family_for_task_id=task_id,
    )
    if not caller:
        raise HTTPException(403, "You are not a member of this family")

    is_self_assign = (caller.id == assignee_member_id)
    if not is_self_assign and caller.role != MemberRole.PARENT:
        raise HTTPException(403, "Only parents can assign tasks to other members")

    try:
        a = assign_task(db, task_id=task_id, assignee_id=assignee_member_id)
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
    assignee = ensure_member(
        db,
        user_id=current.id,
        family_id=None,
        require_same_family_for_assignment_id=assignment_id,
    )
    if not assignee:
        raise HTTPException(403, "You are not a member of this family")

    a = complete_assignment(db, assignment_id=assignment_id, by_member_id=assignee.id)
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
    editor = ensure_member(
        db,
        user_id=current.id,
        family_id=None,
        require_same_family_for_task_id=task_id,
    )
    if not editor:
        raise HTTPException(403, "You are not a member of this family")

    t = update_task(
        db,
        task_id=task_id,
        editor_member_id=editor.id,
        title=payload.title,
        description=payload.description,
        deadline=payload.deadline,
        points_value=payload.points_value,
    )
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
