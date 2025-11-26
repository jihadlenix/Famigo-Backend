from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ..core.config import settings

# Required for SQLite (otherwise "no such table" and threading errors)
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,             # set to True if you want SQL logs
    future=True,
    connect_args=connect_args
)
with engine.connect() as conn:
    print("✅ Connection OK")
# Session factory
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True
)
