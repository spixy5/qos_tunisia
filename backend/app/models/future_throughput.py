"""
PLACEHOLDER - not wired into the ingestion pipeline yet.

Once the real "download completed successfully" export is provided (with
actual duration/bytes fields), this table will store it and
kpi_engine/td.py will be switched from `NotComputed` to a real
implementation. Kept here now so the schema migration is a pure additive
change later - no other table needs to change to support TD.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry

from app.database import Base


class TestHTTPSuccessLog(Base):
    __tablename__ = "test_http_success"

    id = Column(Integer, primary_key=True)
    uploaded_file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=False)

    event_id = Column(String(10), nullable=True)
    time_start = Column(DateTime, nullable=True)
    time_end = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    bytes_transferred = Column(Integer, nullable=True)
    throughput_mbps = Column(Float, nullable=True)   # computed = bytes*8 / duration, or provided directly

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=True)

    operator = Column(String(10), nullable=False)
    technology = Column(String(10), nullable=True)

    gouvernorat_id = Column(Integer, ForeignKey("ref_gouvernorat.id"), nullable=True)
    delegation_id = Column(Integer, ForeignKey("ref_delegation.id"), nullable=True)
    secteur_id = Column(Integer, ForeignKey("ref_secteur.id"), nullable=True)

    uploaded_file = relationship("UploadedFile")
