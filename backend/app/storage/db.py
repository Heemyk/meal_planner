from sqlmodel import SQLModel, Session, create_engine

from app.config import settings


engine = create_engine(settings.postgres_dsn, pool_pre_ping=True)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)
