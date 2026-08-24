"""
Admin-editable KPI configuration.

REVISED: thresholds are no longer keyed by (operator, technology, band)
as a single row. Per the updated requirements:
  - TAI's Taux_aff / Seuil Indoor are keyed by BAND ONLY (same value
    across TT/OO/OR - confirmed, the source table has no operator column).
  - TD's debit exige is keyed by TECHNOLOGY ONLY (also no operator
    dimension - "TD is just per technologie").
  - PCPS's reference constants (0.95 / 0.7 / 0.95) are fixed in the new
    formula itself (see kpi_engine/pcps.py), not admin-configurable -
    the old shared `pcps_reference` field is gone.

The old single OperatorThreshold table (operator+technology+band) is
REMOVED and replaced by BandThreshold + TechnologyThreshold below, plus
ChannelBandMapping (new - resolves a raw RSRP channel number to its real
band per operator).
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, func, UniqueConstraint

from app.database import Base


class BandThreshold(Base):
    """
    TAI parameters, keyed by band only.
      taux_aff      -> Affaiblissement de penetration (dB)
      tai_threshold -> Seuil Indoor (dBm)
    Expected rows: L800, L1800, L2100, U900, U2100 (extendable later).
    """
    __tablename__ = "config_band_thresholds"

    id = Column(Integer, primary_key=True)
    band = Column(String(10), unique=True, nullable=False)
    taux_aff = Column(Float, nullable=False, default=0.0)
    tai_threshold = Column(Float, nullable=False, default=-100.0)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class TechnologyThreshold(Base):
    """
    TD (Taux de Debit) target, keyed by technology only.
    Expected rows: 4G_3G=10, 4G=30, 5G=null (placeholder, no value yet).
    """
    __tablename__ = "config_technology_thresholds"

    id = Column(Integer, primary_key=True)
    technology = Column(String(10), unique=True, nullable=False)  # 4G, 4G_3G, 5G
    debit_exige_mbps = Column(Float, nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class ChannelBandMapping(Base):
    """
    Maps a raw channel number (RSRP.xlsx's 'Ch' column, or the new HTTP
    attempt file's 'Mode(Ch)' column) to its real band, per operator. One
    row per channel number - channel numbers are unique per operator
    across all technologies/bands (confirmed from the source reference
    table, no overlaps observed).

    NOTE on the `technology` field here: this is purely descriptive
    reference metadata (genuinely "2G"/"3G"/"4G", the actual generation of
    the channel) - it is NOT the same restricted set used for the upload
    dropdown / raw_data.technology column (4G/4G_3G/5G/Unspecified) and
    is never used by the KPI engine (band lookup only needs
    operator+channel - see kpi_engine/tai.py).
    """
    __tablename__ = "config_channel_band_mapping"
    __table_args__ = (
        UniqueConstraint("operator", "channel", name="uq_operator_channel"),
    )

    id = Column(Integer, primary_key=True)
    operator = Column(String(10), nullable=False)     # TT, OO, OR
    channel = Column(Integer, nullable=False)
    technology = Column(String(10), nullable=False)    # descriptive only: "2G", "3G", or "4G"
    band = Column(String(10), nullable=False)           # L800, L1800, L2100, U900, U2100, G900, G1800


class DownloadDurationThreshold(Base):
    """
    Admin-configurable cutoff (seconds) used by TAO/TAI: an HTTP attempt
    whose download_duration_seconds exceeds this is treated as a TAO
    failure and excluded from TAI's numerator - see kpi_engine/tao.py and
    tai.py. Singleton table (single row, id=1).
    """
    __tablename__ = "config_download_duration_threshold"

    id = Column(Integer, primary_key=True)
    cutoff_seconds = Column(Float, nullable=False, default=10.0)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
