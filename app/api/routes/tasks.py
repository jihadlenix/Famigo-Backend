from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models.task import Task, TaskAssignment
from ...models.family_member import FamilyMember, MemberRole
from ...models.family import Family
from ...models.user import User
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
from ..deps import get_db, get_current_user
from ...services.ai_service import classify_task, suggest_assignments

router = APIRouter()


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    points_value: Optional[int] = None

class TaskClassifyRequest(BaseModel):
    title: str
    description: Optional[str] = None


class AssignTaskBody(BaseModel):
    member_id: str


#  Create a new task in a family

@router.post(
    "/families/{family_id}/tasks",
    response_model=TaskOut,
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

    # Classify task using AI
    classification = classify_task(payload.title, payload.description)
    
    t = create_task(
        db,
        family_id=family_id,
        title=payload.title,
        description=payload.description,
        deadline=payload.deadline,
        points_value=payload.points_value,
        created_by_member_id=member.id,
        category=classification.get("category"),  # Add category from AI classification
    )
    return t


# ------------------------------------------------------------------------
#  Assign a task to a family member (by member_id)
# ------------------------------------------------------------------------
@router.post(
    "/tasks/{task_id}/assign",
    response_model=dict,
)
def assign(
    task_id: str,
    body: AssignTaskBody,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    family = db.get(Family, task.family_id)
    if not family:
        raise HTTPException(404, "Family not found")

    caller_member = db.execute(
        select(FamilyMember).where(
            FamilyMember.user_id == current.id,
            FamilyMember.family_id == family.id,
        )
    ).scalar_one_or_none()
    is_owner = family.owner_id == current.id

    if not (caller_member or is_owner):
        raise HTTPException(403, "You are not a member or owner of this family")

    assignee = db.get(FamilyMember, body.member_id)
    if not assignee or assignee.family_id != family.id:
        raise HTTPException(404, "Assignee not found in this family")

    is_self_assign = caller_member and caller_member.id == assignee.id

    if not is_owner:
        if not caller_member:
            raise HTTPException(403, "No family membership found")

        if not (is_self_assign or caller_member.role == MemberRole.PARENT):
            raise HTTPException(403, "Only parents, owner, or self-assign can assign tasks")

    try:
        a = assign_task(db, task_id=task_id, assignee_id=assignee.id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {"assignment_id": a.id}


# ------------------------------------------------------------------------
# Complete a task for the current user
# ------------------------------------------------------------------------
@router.post(
    "/tasks/{task_id}/complete",
    response_model=dict,
)
def complete_for_current_user(
    task_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    caller_member = db.execute(
        select(FamilyMember).where(
            FamilyMember.user_id == current.id,
            FamilyMember.family_id == task.family_id,
        )
    ).scalar_one_or_none()

    if not caller_member:
        raise HTTPException(403, "You are not a member of this family")

    assignment = db.execute(
        select(TaskAssignment).where(
            TaskAssignment.task_id == task.id,
            TaskAssignment.assignee_id == caller_member.id,
            TaskAssignment.completed_at.is_(None),
        )
    ).scalar_one_or_none()

    if not assignment:
        raise HTTPException(404, "No active assignment for you on this task")

    a = complete_assignment(db, assignment_id=assignment.id, by_member_id=caller_member.id)
    if not a:
        raise HTTPException(400, "Cannot complete assignment")

    return {"ok": True}


# ------------------------------------------------------------------------
# Edit an existing task
# ------------------------------------------------------------------------
@router.patch(
    "/tasks/{task_id}",
    response_model=TaskOut,
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
)
def my_tasks(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    return list_tasks_for_user(db, user_id=current.id)


# ------------------------------------------------------------------------
# Get all tasks for a family
# ------------------------------------------------------------------------
@router.get(
    "/families/{family_id}/tasks",
    response_model=List[TaskOut],
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


# ------------------------------------------------------------------------
# Classify a task (AI endpoint)
# ------------------------------------------------------------------------
@router.post(
    "/classify",
    summary="Classify Task",
    description="""
    Classify a task into categories (chores, homework, creative, physical, social, other)
    using AI. This helps suggest age-appropriate assignments.
    
    **Who can use it:**  
    Any authenticated user.
    
    **Body Parameters:**  
    - `title`: Task title (required)
    - `description`: Optional task description
    
    **Returns:**  
    Classification result with category, confidence, and age suggestions.
    """,
)
def classify_task_endpoint(
    payload: TaskClassifyRequest,
    current: User = Depends(get_current_user),
):
    result = classify_task(payload.title, payload.description)
    return result


# ------------------------------------------------------------------------
# Get assignment suggestions for a task
# ------------------------------------------------------------------------
@router.get(
    "/{task_id}/suggestions",
    summary="Get Assignment Suggestions",
    description="""
    Get AI-powered suggestions for which family members are best suited
    for a task based on category and age appropriateness.
    
    **Who can use it:**  
    Any member of the family that owns the task.
    
    **Path Parameter:**  
    - `task_id`: ID of the task
    
    **Returns:**  
    List of suggested family members sorted by suitability score.
    """,
)
def get_task_suggestions(
    task_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    
    # Verify user is a member of the family
    member = ensure_member(db, user_id=current.id, family_id=task.family_id)
    if not member:
        raise HTTPException(403, "You are not a member of this family")
    
    # Get all family members
    family_members = db.execute(
        select(FamilyMember).where(FamilyMember.family_id == task.family_id)
    ).scalars().all()
    
    # Convert to dict format for AI service
    members_data = []
    for fm in family_members:
        members_data.append({
            "id": fm.id,
            "role": fm.role.value if hasattr(fm.role, 'value') else str(fm.role),
            "display_name": fm.display_name,
            "full_name": fm.user.full_name if fm.user else None,
            "age": fm.user.age if fm.user else None,  # Get age from User model
        })
    
    # Get category from task (or classify if not set)
    category = task.category
    if not category:
        classification = classify_task(task.title, task.description)
        category = classification.get("category", "other")
    
    # Get suggestions
    suggestions = suggest_assignments(category, members_data)
    
    return {
        "task_id": task_id,
        "task_title": task.title,
        "category": category,
        "suggestions": suggestions
    }


# ------------------------------------------------------------------------
# Get total points of current user
# ------------------------------------------------------------------------
@router.get(
    "/me/points",
    response_model=dict,
)
def my_points(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    members = db.execute(
        select(FamilyMember).where(FamilyMember.user_id == current.id)
    ).scalars().all()

    total = 0
    for m in members:
        if m.wallet:
            total += m.wallet.balance

    return {"total_points": total}
