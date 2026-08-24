import enum
from sqlalchemy import Column, Integer, String, Float, DateTime, func, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class KPIName(str, enum.Enum):
    TAO = "TAO"
    TAI = "TAI"
    TD = "TD"
    PCPS = "PCPS"


class KPIResult(Base):
    """
    One row per (secteur, operator, technology, kpi_name), recomputed each
    time the KPI engine runs. This is what the dashboard/API queries -
    raw tables are never queried directly by the frontend.
    """
    __tablename__ = "kpi_results"
    __table_args__ = (
        UniqueConstraint("secteur_id", "operator", "technology", "kpi_name",
                          name="uq_kpi_secteur_operator_tech_kpiname"),
    )

    id = Column(Integer, primary_key=True)
    secteur_id = Column(Integer, ForeignKey("ref_secteur.id"), nullable=False)
    operator = Column(String(10), nullable=False)
    technology = Column(String(10), nullable=True)

    kpi_name = Column(Enum(KPIName), nullable=False)
    value = Column(Float, nullable=True)          # null = not computed (e.g. TD until success-log arrives)
    numerator = Column(Integer, nullable=True)
    denominator = Column(Integer, nullable=True)
    is_computed = Column(String(5), nullable=False, default="true")  # 'false' for TD placeholder rows

    computed_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    secteur = relationship("Secteur")
