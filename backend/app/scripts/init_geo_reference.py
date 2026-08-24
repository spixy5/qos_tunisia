"""
Loads tun_admin2/3/4.geojson into ref_gouvernorat / ref_delegation / ref_secteur.
Idempotent - safe to re-run if the boundary files are updated.

Usage:
    python -m app.scripts.init_geo_reference
"""
import logging

from app.database import SessionLocal
from app.config import settings
from app.spatial_mapping.geo_loader import load_all_geo_reference

logging.basicConfig(level=logging.INFO)


def main():
    db = SessionLocal()
    try:
        load_all_geo_reference(
            db,
            admin2_path=settings.geojson_admin2_path,
            admin3_path=settings.geojson_admin3_path,
            admin4_path=settings.geojson_admin4_path,
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
