from sqlalchemy import text

from sqlmodel import SQLModel, Session, create_engine

from app.config import settings


engine = create_engine(settings.postgres_dsn, pool_pre_ping=True)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate_recipe_meal_type()
    _migrate_recipe_allergens()


def _migrate_recipe_meal_type() -> None:
    """Add meal_type column if missing (for existing deployments)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE recipe ADD COLUMN IF NOT EXISTS meal_type VARCHAR(32) DEFAULT 'entree'"))
            conn.commit()
    except Exception:
        pass


def _migrate_recipe_allergens() -> None:
    """Add allergens JSON column if missing (for existing deployments)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE recipe ADD COLUMN IF NOT EXISTS allergens JSONB DEFAULT NULL"))
            conn.commit()
    except Exception:
        pass


def get_session() -> Session:
    return Session(engine)
