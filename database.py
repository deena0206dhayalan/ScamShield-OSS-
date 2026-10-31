from sqlmodel import SQLModel, create_engine

DB_FILE = "scamshield.db"

# check_same_thread=False: FastAPI serves sync endpoints from a thread pool
engine = create_engine(
    f"sqlite:///{DB_FILE}",
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
