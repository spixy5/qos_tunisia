"""
Shared helper for TAO/TAI: the admin-configurable "slow download" cutoff
(seconds). An HTTP attempt whose download_duration_seconds exceeds this
is treated as a TAO failure and excluded from TAI's numerator.
"""
from sqlalchemy.orm import Session

from app.models.config_models import DownloadDurationThreshold

DEFAULT_CUTOFF_SECONDS = 10.0


def get_duration_cutoff(db: Session) -> float:
    row = db.query(DownloadDurationThreshold).first()
    return row.cutoff_seconds if row else DEFAULT_CUTOFF_SECONDS
