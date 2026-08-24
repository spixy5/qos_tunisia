"""
Creates the first Admin user, seeds BandThreshold (TAI parameters, from
the operator-provided reference table) and TechnologyThreshold (TD
targets). Idempotent - safe to re-run; existing rows are left alone so it
never clobbers values already customized via the Admin settings panel.

Usage:
    python -m app.scripts.seed_initial_data
"""
import logging

from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.config_models import BandThreshold, TechnologyThreshold, DownloadDurationThreshold
from app.auth.security import hash_password

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "changeme123"  # CHANGE IMMEDIATELY after first login

# band -> (taux_aff dB, tai_threshold dBm) - from the operator-provided
# "Bandes de frequences / Affaiblissement de penetration / Seuil Indoor" table
BAND_THRESHOLDS = {
    "L800": (9.0, -96.0),
    "L1800": (11.0, -94.0),
    "L2100": (12.0, -93.0),
    "U900": (9.0, -89.0),
    "U2100": (12.0, -86.0),
}

# technology -> debit exige (Mbps). 5G intentionally left unset (None)
# until a value is provided.
TECHNOLOGY_THRESHOLDS = {
    "4G_3G": 10.0,
    "4G": 30.0,
    "5G": None,
}


def main():
    db = SessionLocal()
    try:
        if not db.query(User).filter_by(username=DEFAULT_ADMIN_USERNAME).first():
            db.add(User(
                username=DEFAULT_ADMIN_USERNAME,
                hashed_password=hash_password(DEFAULT_ADMIN_PASSWORD),
                role=UserRole.ADMIN,
            ))
            logger.info("Created default admin user '%s' / '%s' - CHANGE THIS PASSWORD",
                        DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD)

        for band, (taux_aff, tai_threshold) in BAND_THRESHOLDS.items():
            if not db.query(BandThreshold).filter_by(band=band).first():
                db.add(BandThreshold(band=band, taux_aff=taux_aff, tai_threshold=tai_threshold))

        for technology, debit_exige in TECHNOLOGY_THRESHOLDS.items():
            if not db.query(TechnologyThreshold).filter_by(technology=technology).first():
                db.add(TechnologyThreshold(technology=technology, debit_exige_mbps=debit_exige))

        if not db.query(DownloadDurationThreshold).first():
            db.add(DownloadDurationThreshold(cutoff_seconds=10.0))

        db.commit()
        logger.info("Seeding complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
