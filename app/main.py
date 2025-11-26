from fastapi import FastAPI
from app.db.base import Base
from app.db.session import engine
from app.api.routes import auth, users, families, tasks, rewards


app = FastAPI(title="Famigo API", version="0.2.0")

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

# ✅ Register routes
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(families.router, prefix="/families", tags=["Families"])
app.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
# app.include_router(rewards.router, prefix="/rewards", tags=["Rewards"])
app.include_router(rewards.router, tags=["Rewards"])

