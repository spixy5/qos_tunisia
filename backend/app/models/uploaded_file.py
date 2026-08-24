import enum
from sqlalchemy import Column, Integer, String, DateTime, func, Enum, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class LogType(str, enum.Enum):
    RSRP = "rsrp"
    HTTP_ATTEMPT = "http_attempt"
    HTTP_FAILURE = "http_failure"


class UploadedFile(Base):
    """
    One row per file uploaded through the Admin UI. Drives the local archive
    path (/tunisie/{gouvernorat}/{delegation}/{secteur}/{type_de_test}/{technologie})
    and is the join key for the admin "delete by log file path" feature.
    """
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True)
    original_filename = Column(String(255), nullable=False)
    log_type = Column(Enum(LogType), nullable=False)
    operator = Column(String(10), nullable=False)          # TT, OO, OR (from upload dropdown)
    technology = Column(String(10), nullable=True)          # 4G, 3G, 4G_3G (from filename/dropdown)

    # Resolved AFTER spatial join - majority-sector rule (per agreed archiving policy)
    majority_secteur_id = Column(Integer, ForeignKey("ref_secteur.id"), nullable=True)
    archive_path = Column(String(500), nullable=True)

    row_count_raw = Column(Integer, nullable=True)
    row_count_clean = Column(Integer, nullable=True)
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    majority_secteur = relationship("Secteur")
