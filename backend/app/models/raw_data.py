"""
Split-by-type raw tables, as required ("test_rsrp", "test_http_attempt").
Each row keeps:
  - the resolved geo hierarchy (nullable until the spatial join step runs)
  - operator / technology / band for KPI grouping
  - a link back to the UploadedFile it came from (drives archiving + admin delete)

NOTE (schema change): TestHTTPFailure has been removed. The radio team's
new unified HTTP export carries both successful and failed test rows in a
single file, distinguished by `test_status`, so a separate failure table
is no longer needed. The fields from the old failure table that still
carry useful information (`failure_cause`, `redirect_address`) have been
folded into TestHTTPAttempt below.

A normalized `KPIResult` table (kpi.py) is what downstream
dashboard/reporting code actually reads from.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry

from app.database import Base


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
    # Widened 10 -> 20: 'Unspecified' (the "Free Tech" upload value) is 11
    # chars and was getting truncated by Postgres on insert.
    technology = Column(String(20), nullable=True)

    gouvernorat_id = Column(Integer, ForeignKey("ref_gouvernorat.id"), nullable=True)
    delegation_id = Column(Integer, ForeignKey("ref_delegation.id"), nullable=True)
    secteur_id = Column(Integer, ForeignKey("ref_secteur.id"), nullable=True)

    uploaded_file = relationship("UploadedFile")


class TestHTTPAttempt(Base):
    __tablename__ = "test_http_attempt"

    id = Column(Integer, primary_key=True)
    uploaded_file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=False)

    # Back to `time` - the live DB was restored from a backup that
    # predates the test_start_time rename, so the ORM has to match what's
    # actually there again.
    time = Column("time", DateTime, nullable=False)
    test_end_time = Column("test_end_time", DateTime, nullable=True)

    system = Column(String(30), nullable=True)            # "LTE FDD" or raw code
    serving_band = Column(String(10), nullable=True)       # 1800, 2100 ... (frequency band, raw/unresolved)
    application_protocol = Column(String(20), nullable=True)

    # Carries success/failure/timeout status for this row. Replaces the old
    # separate TestHTTPFailure table + implicit "every attempt row is a
    # success" assumption - both outcomes now live in this one table.
    test_status = Column("test_status", String(100), nullable=True)

    # --- Merged in from the old TestHTTPFailure table ------------------


    # RSRP/RSCP + channel + duration live directly on the attempt row -
    # TAI is computed entirely from this table (see kpi_engine/tai.py).
    best_rsrp = Column(Float, nullable=True)
    best_rscp = Column(Float, nullable=True)   # NEW: 3G equivalent reading, new export only
    channel = Column(Integer, nullable=True)
    band = Column(String(10), nullable=True)   # resolved via ChannelBandMapping(operator, channel)
    download_duration_seconds = Column(Float, nullable=True)  # computed as test_end_time - test_start_time

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=True)

    operator = Column(String(10), nullable=False)
    # Widened 10 -> 20, same reason as TestRSRP.technology above.
    technology = Column(String(20), nullable=True)

    gouvernorat_id = Column(Integer, ForeignKey("ref_gouvernorat.id"), nullable=True)
    delegation_id = Column(Integer, ForeignKey("ref_delegation.id"), nullable=True)
    secteur_id = Column(Integer, ForeignKey("ref_secteur.id"), nullable=True)

    uploaded_file = relationship("UploadedFile")

    # Dropped vs the old model: event_id, data_transfer_address,
    # connection_timeout_ms, pci, end_system_and_band - all were only
    # populated by old-format exports that no longer need supporting.