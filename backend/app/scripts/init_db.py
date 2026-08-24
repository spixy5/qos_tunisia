"""
Creates all tables (run once after enabling the PostGIS extension).

Usage:
    python -m app.scripts.init_db
"""
import logging
from sqlalchemy import text

from app.database import engine, Base
import app.models  # noqa: F401 - registers all models on Base.metadata

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()
    logger.info("PostGIS extension ensured.")

    Base.metadata.create_all(bind=engine)
    logger.info("All tables created.")


if __name__ == "__main__":
    main()
