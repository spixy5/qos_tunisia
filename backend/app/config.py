from pathlib import Path
from pydantic_settings import BaseSettings

# Looking at your folder tree: config.py is inside backend/app/core/config.py
# Let's map parents accurately:
# .parent = core
# .parent.parent = app
# .parent.parent.parent = backend (which contains geo_data and file_archive)
BASE_DIR = Path(__file__).resolve().parent.parent.parent /"backend"


class Settings(BaseSettings):
    # --- Database ---
    database_url: str = "postgresql+psycopg://postgres:user@localhost:5432/qos_tunisia"

    # --- Auth ---
    jwt_secret_key: str = "f58e96d8eae80fd757db8bf400ae5e09233bb1077f68165f308f4e1c6a8ccff5"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 8  # 8h session

    # --- File archiving ---
    archive_root: Path = BASE_DIR / "file_archive"

    # --- Geo reference data ---
    geojson_admin2_path: Path = BASE_DIR / "geo_data" / "tun_admin2.geojson"
    geojson_admin3_path: Path = BASE_DIR / "geo_data" / "tun_admin3.geojson"
    geojson_admin4_path: Path = BASE_DIR / "geo_data" / "tun_admin4.geojson"

    # --- CORS ---
    frontend_origin: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()