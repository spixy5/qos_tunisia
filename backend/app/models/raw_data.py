from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry

from app.database import Base


class TestRSRP(Base):
    __tablename__ = "test_rsrp"

    id = Column(Integer, primary_key=True)
    uploaded_file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=False)

    # One row = one technology's reading (4G or 3G) - the combined scanner
    # file is split into two rows per source row by the parser, so these
    # generic fields hold "the reading" for whichever `technology` this
    # row is, rather than having separate _4g/_3g suffixed columns.
    time = Column(DateTime, nullable=False)
    best_rsrp = Column(Float, nullable=False)        # 4G row: "RSRP". 3G row: "RSCP" (also duplicated into rscp below)
    channel = Column(Integer, nullable=True)          # 4G row: "Ch_4G". 3G row: "Ch_3G"

    # ADDED: resolved via ChannelBandMapping(operator, channel). Was
    # missing from this table entirely even though TAI needs it to match
    # against test_http_attempt.serving_band - filled downstream by
    # attach_band_column(), not by the parser itself.
    band = Column(String(10), nullable=True)

    dl_bw = Column(String(20), nullable=True)          # "DL BW" - 4G row only, null on 3G rows
    pci = Column(Integer, nullable=True)                # "PCI" - 4G row only, null on 3G rows
    to_interval = Column(Integer, nullable=True)

    # 3G-specific columns from the combined scanner export. Null on 4G
    # rows. rscp duplicates the value already in best_rsrp on 3G rows
    # (kept as its own column since some queries reference it by name),
    # sc (Scrambling Code) has no other home - it's not the same thing as pci.
    rscp = Column(Float, nullable=True)
    sc = Column(Integer, nullable=True)

    # CHANGED: nullable=True (was False). Confirmed against the real
    # SCANNER_OR.xlsx file: GPS is captured alongside the 3G reading only
    # - rows with no 3G fix (RSCP null) have no Lat./Lon. at all (5/420
    # rows in the sample checked, GPS null in exactly and only those
    # rows). A split-out 4G-only row for one of those source rows
    # therefore genuinely has no GPS to store; forcing NOT NULL would
    # either crash that insert or require silently dropping valid RSRP
    # readings for no good reason.
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=True)

    operator = Column(String(10), nullable=False)
    technology = Column(String(20), nullable=True)

    gouvernorat_id = Column(Integer, ForeignKey("ref_gouvernorat.id"), nullable=True)
    delegation_id = Column(Integer, ForeignKey("ref_delegation.id"), nullable=True)
    secteur_id = Column(Integer, ForeignKey("ref_secteur.id"), nullable=True)

    uploaded_file = relationship("UploadedFile")


class TestHTTPAttempt(Base):
    __tablename__ = "test_http_attempt"

    id = Column(Integer, primary_key=True)
    uploaded_file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=False)

    test_start_time = Column("test_start_time", DateTime, nullable=False)   # "Test start time"
    test_end_time = Column("test_end_time", DateTime, nullable=True)        # "Test end time"

    system = Column(String(30), nullable=True)             # parsed from "Start system and band"
    serving_band = Column(String(10), nullable=True)        # parsed from "Start system and band"
    application_protocol = Column(String(20), nullable=True)  # "Test protocol"

    test_status = Column("test_status", String(100), nullable=True)  # "Test status"

    best_rsrp = Column(Float, nullable=True)      # "AvgRSRP"
    best_rscp = Column(Float, nullable=True)      # "AvgRSCP"
    download_duration_seconds = Column(Float, nullable=True)  # computed as test_end_time - test_start_time

    latitude = Column(Float, nullable=False)      # "Test start latitude"
    longitude = Column(Float, nullable=False)     # "Test start longitude"
    geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=True)

    operator = Column(String(10), nullable=False)
    technology = Column(String(20), nullable=True)

    gouvernorat_id = Column(Integer, ForeignKey("ref_gouvernorat.id"), nullable=True)
    delegation_id = Column(Integer, ForeignKey("ref_delegation.id"), nullable=True)
    secteur_id = Column(Integer, ForeignKey("ref_secteur.id"), nullable=True)

    uploaded_file = relationship("UploadedFile")

    # No channel/band columns here - unlike test_rsrp, the "Home operator"
    # HTTP export has separate best_rsrp/best_rscp columns already, so
    # there's no single-field reuse problem requiring a row split, and
    # no channel data is provided by this export at all.