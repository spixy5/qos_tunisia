"""
Central application settings, loaded from environment variables (.env supported).
Nothing business-specific lives here (KPI thresholds live in the DB / config/ json
so they can be edited by the Admin at runtime) - this file is purely infra config.
"""
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # --- Database ---
    database_url: str = "postgresql+psycopg://postgres:user@localhost:5432/qos_tunisia"

    # --- Auth ---
    jwt_secret_key: str = "f58e96d8eae80fd757db8bf400ae5e09233bb1077f68165f308f4e1c6a8ccff5"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 8  # 8h session

    # --- File archiving ---
    # Root of the local archive hierarchy:
    # /{archive_root}/tunisie/{gouvernorat}/{delegation}/{secteur}/{type_de_test}/{technologie}/
    archive_root: Path = Path("./file_archive")

    # --- Geo reference data ---
    geojson_admin2_path: Path = Path("./geo_data/tun_admin2.geojson")  # Gouvernorat
    geojson_admin3_path: Path = Path("./geo_data/tun_admin3.geojson")  # Delegation
    geojson_admin4_path: Path = Path("./geo_data/tun_admin4.geojson")  # Secteur

    # --- CORS ---
    frontend_origin: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()
