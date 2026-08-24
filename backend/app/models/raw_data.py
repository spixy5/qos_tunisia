"""
Split-by-type raw tables, as required ("test_rsrp", "test_http_attempt",
"test_http_failure"). Each row keeps:
  - the resolved geo hierarchy (nullable until the spatial join step runs)
  - operator / technology / band for KPI grouping
  - a link back to the UploadedFile it came from (drives archiving + admin delete)

Kept deliberately separate rather than one unified table because the source
schemas genuinely differ (RSRP has no throughput/protocol fields, failure
files have a Status/Failure cause the attempt files don't, etc.) - see the
data inspection notes. A normalized `KPIResult` table (kpi.py) is what
downstream dashboard/reporting code actually reads from.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry

from app.database import Base


class GeoMixinColumns:
    """Not a real mixin (SQLAlchemy declarative quirks) - just documents the
    repeated column set applied identically to all 3 raw tables below."""
    pass


class TestRSRP(Base):
    __tablename__ = "test_rsrp"

    id = Column(Integer, primary_key=True)
    uploaded_file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=False)

    time = Column(DateTime, nullable=False)
    best_rsrp = Column(Float, nullable=False)        # "1. best RSRP"
    channel = Column(Integer, nullable=True)           # "Ch" -> raw channel number
    band = Column(String(10), nullable=True)            # resolved via ChannelBandMapping(operator, channel).
                                                          # Stays null if the channel isn't in the reference
                                                          # table - row is KEPT, just excluded from TAI's
                                                          # band-based pass/fail evaluation (see tai.py).
    dl_bw = Column(String(20), nullable=True)          # "DL BW", e.g. "15 MHz"
    pci = Column(Integer, nullable=True)
    to_interval = Column(Integer, nullable=True)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=True)

    # operator + technology are kept as explicit fields even for "Free
    # Tech" uploads (technology stored as "Unspecified" in that case) -
    # per requirement, technology is NOT derived from the channel lookup,
    # it's whatever was chosen at upload time, kept here "for clarity".
    operator = Column(String(10), nullable=False)
    technology = Column(String(15), nullable=True)

    gouvernorat_id = Column(Integer, ForeignKey("ref_gouvernorat.id"), nullable=True)
    delegation_id = Column(Integer, ForeignKey("ref_delegation.id"), nullable=True)
    secteur_id = Column(Integer, ForeignKey("ref_secteur.id"), nullable=True)

    uploaded_file = relationship("UploadedFile")


class TestHTTPAttempt(Base):
    __tablename__ = "test_http_attempt"

    id = Column(Integer, primary_key=True)
    uploaded_file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=False)

    event_id = Column(String(10), nullable=True)        # "DAA"
    time = Column(DateTime, nullable=False)
    system = Column(String(30), nullable=True)           # "LTE FDD" (old files) or raw code (new files)
    serving_band = Column(String(10), nullable=True)     # 1800, 2100 ... (frequency band, raw/unresolved)
    data_transfer_address = Column(String(255), nullable=True)
    application_protocol = Column(String(20), nullable=True)
    connection_timeout_ms = Column(Integer, nullable=True)
    test_end_time = Column(
    "test_end_time",
    DateTime,
    nullable=True,)

    end_system_and_band = Column(
    "end_system_and_band",
    String(100),
    nullable=True,)
    test_status = Column("test_status", String(100), nullable=True)


    # NEW (per the revised HTTP attempt file format): each attempt row now
    # carries its own RSRP reading + channel + download duration, so TAI
    # is computed entirely from this table now (no longer from TestRSRP -
    # see kpi_engine/tai.py). Nullable for backward compatibility with
    # older-format attempt files that don't have these columns.
    best_rsrp = Column(Float, nullable=True)
    channel = Column(Integer, nullable=True)
    band = Column(String(10), nullable=True)              # resolved via ChannelBandMapping(operator, channel)
    download_duration_seconds = Column(Float, nullable=True)
    pci = Column(Integer, nullable=True)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=True)

    operator = Column(String(10), nullable=False)
    technology = Column(String(15), nullable=True)
    # NOTE: no is_success flag needed - every http_attempt row IS a success
    # by definition (see kpi_engine/tao.py for the evidence). Failed tests
    # land in TestHTTPFailure instead, never both.

    gouvernorat_id = Column(Integer, ForeignKey("ref_gouvernorat.id"), nullable=True)
    delegation_id = Column(Integer, ForeignKey("ref_delegation.id"), nullable=True)
    secteur_id = Column(Integer, ForeignKey("ref_secteur.id"), nullable=True)

    uploaded_file = relationship("UploadedFile")


class TestHTTPFailure(Base):
    __tablename__ = "test_http_failure"

    id = Column(Integer, primary_key=True)
    uploaded_file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=False)

    event_id = Column(String(10), nullable=True)         # "DAF"
    event_label = Column(String(50), nullable=True)       # "HTTP failure"
    event_number = Column(Integer, nullable=True)
    measurement = Column(String(50), nullable=True)       # "test_http_4g.1"
    time = Column(DateTime, nullable=False)
    system = Column(String(30), nullable=True)
    serving_band = Column(String(10), nullable=True)
    data_transfer_address = Column(String(255), nullable=True)
    redirect_address = Column(String(255), nullable=True)
    application_protocol = Column(String(20), nullable=True)
    status = Column(String(100), nullable=True)
    failure_cause = Column(String(100), nullable=True)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=True)

    operator = Column(String(10), nullable=False)
    technology = Column(String(15), nullable=True)
    # NOTE: no matched_attempt_id needed - failure rows are standalone failed
    # test events, not duplicates of an attempt row requiring a join.

    gouvernorat_id = Column(Integer, ForeignKey("ref_gouvernorat.id"), nullable=True)
    delegation_id = Column(Integer, ForeignKey("ref_delegation.id"), nullable=True)
    secteur_id = Column(Integer, ForeignKey("ref_secteur.id"), nullable=True)

    uploaded_file = relationship("UploadedFile")