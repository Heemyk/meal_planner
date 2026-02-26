from sqlalchemy import text

from sqlmodel import SQLModel, Session, create_engine

from app.config import settings


engine = create_engine(settings.postgres_dsn, pool_pre_ping=True)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate_recipe_meal_type()
    _migrate_recipe_allergens()
    _migrate_sku_base_unit()
    _migrate_ingredient_sku_unavailable()


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


def _migrate_sku_base_unit() -> None:
    """Add quantity_in_base_unit, size_display to sku if missing."""
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE sku ADD COLUMN IF NOT EXISTS quantity_in_base_unit DOUBLE PRECISION DEFAULT NULL"))
            conn.execute(text("ALTER TABLE sku ADD COLUMN IF NOT EXISTS size_display VARCHAR(64) DEFAULT NULL"))
            conn.commit()
    except Exception:
        pass


def _migrate_ingredient_sku_unavailable() -> None:
    """Add sku_unavailable to ingredient if missing (tracks count=0 SKU fetch)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE ingredient ADD COLUMN IF NOT EXISTS sku_unavailable BOOLEAN DEFAULT FALSE"))
            conn.commit()
            # Backfill: mark ingredients with 0 valid SKUs as unavailable
            conn.execute(text("""
                UPDATE ingredient SET sku_unavailable = true
                WHERE id IN (
                    SELECT i.id FROM ingredient i
                    LEFT JOIN sku s ON s.ingredient_id = i.id AND s.expires_at > now()
                    WHERE s.id IS NULL
                    AND i.sku_unavailable = false
                )
            """))
            conn.commit()
    except Exception:
        pass


def get_session() -> Session:
    return Session(engine)
