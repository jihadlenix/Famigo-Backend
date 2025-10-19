from fastapi import FastAPI
from app.db.base import Base
from app.db.session import engine
from .api.routes import auth, users, families, tasks, rewards
app = FastAPI(title="Famigo API", version="0.2.0")

# Create tables once at app startup
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(families.router, prefix="/families", tags=["families"])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(rewards.router, prefix="/rewards", tags=["rewards"])
