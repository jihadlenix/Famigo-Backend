from fastapi import APIRouter
from . import auth, users, families, tasks, rewards

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["Auth"])
router.include_router(users.router, prefix="/users", tags=["Users"])
router.include_router(families.router, prefix="/families", tags=["Families"])
router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
router.include_router(rewards.router, prefix="/rewards", tags=["Rewards"])

