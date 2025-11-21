from app.db.session import engine
from app.db.base import Base
def init():
    Base.metadata.create_all(bind=engine)
if __name__ == "__main__":
    init()
    print("Database schema created.")
