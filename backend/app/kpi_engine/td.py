"""
TD = Taux de Debit Conforme (per INT Decision Coll/Reg/2025/16, Annexe A section 2.2.1)

TD =
    (HTTP measurements where measured throughput >= regulatory required throughput)
    /
    (total valid throughput measurements)
    * 100

Required throughput thresholds by technology:
    - 4G: 30 Mbps (File size: 225 Mo)
    - 3G: 10 Mbps (File size: 20 Mo)

Grouping:
    (secteur, operator, technology)
"""

from sqlalchemy import select, func

from app.kpi_engine.base import (
    BaseKPI,
    KPIContext,
    KPIComputationResult,
    register_kpi,
)
from app.models.raw_data import TestHTTPAttempt


FILE_SIZES_MB = {
    "4G": 225.0,
    "3G": 20.0,
}

REQUIRED_THROUGHPUT_MBPS = {
    "4G": 30.0,
    "3G": 10.0,
}


@register_kpi
class TDKpi(BaseKPI):
    name = "TD"

    def compute(self, context: KPIContext) -> KPIComputationResult:
        db = context.db

        tech_key = (context.technology or "").upper()

        # If technology is not found in mapping, do not fall back; return 0/is_computed=False
        if tech_key not in FILE_SIZES_MB or tech_key not in REQUIRED_THROUGHPUT_MBPS:
            return KPIComputationResult(
                value=None,
                numerator=0,
                denominator=0,
                is_computed=False,
            )

        filters = [
            TestHTTPAttempt.secteur_id == context.secteur_id,
            TestHTTPAttempt.operator == context.operator,
            TestHTTPAttempt.technology == context.technology,
            TestHTTPAttempt.download_duration_seconds.is_not(None),
            TestHTTPAttempt.download_duration_seconds > 0,
        ]

        # Total valid throughput measurements
        total = db.execute(
            select(func.count(TestHTTPAttempt.id)).where(*filters)
        ).scalar_one()

        if total == 0:
            return KPIComputationResult(
                value=None,
                numerator=0,
                denominator=0,
                is_computed=False,
            )

        file_size_mb = FILE_SIZES_MB[tech_key]
        file_size_megabits = file_size_mb * 8.0
        required_mbps = REQUIRED_THROUGHPUT_MBPS[tech_key]

        max_allowed_duration = file_size_megabits / required_mbps

        # Success = measurements where the download duration is fast enough
        # to meet or exceed the regulatory throughput threshold.
        success = db.execute(
            select(func.count(TestHTTPAttempt.id)).where(
                *filters,
                TestHTTPAttempt.download_duration_seconds <= max_allowed_duration,
            )
        ).scalar_one()

        value = round((success / total) * 100, 2)

        return KPIComputationResult(
            value=value,
            numerator=success,
            denominator=total,
            is_computed=True,
        )