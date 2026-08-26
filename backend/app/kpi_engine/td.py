"""
TD = Taux de Debit Conforme

TD =
    (measurements where measured throughput > required throughput)
    /
    (total valid throughput measurements)
    * 100

The HTTP test file is fixed at 2 MB.

2 MB * 8 = 16 megabits

Therefore:

    throughput_mbps = 16 / duration_seconds

where:

    duration_seconds = test_end_time - test_start_time

The comparison is strictly:

    throughput_mbps > debit_exige_mbps

Grouping:
    (secteur, operator, technology)
"""

from sqlalchemy import select, func, extract

from app.kpi_engine.base import (
    BaseKPI,
    KPIContext,
    KPIComputationResult,
    register_kpi,
)
from app.models.raw_data import TestHTTPAttempt
from app.models.config_models import TechnologyThreshold


FILE_SIZE_MB = 2.0
FILE_SIZE_MEGABITS = FILE_SIZE_MB * 8.0


@register_kpi
class TDKpi(BaseKPI):
    name = "TD"

    def compute(self, context: KPIContext) -> KPIComputationResult:

        db = context.db

        # Required throughput for this technology
        threshold_row = (
            db.query(TechnologyThreshold)
            .filter_by(technology=context.technology)
            .one_or_none()
        )

        if (
            threshold_row is None
            or threshold_row.debit_exige_mbps is None
        ):
            return KPIComputationResult(
                value=None,
                numerator=None,
                denominator=None,
                is_computed=False,
            )

        debit_exige_mbps = threshold_row.debit_exige_mbps

        filters = [
            TestHTTPAttempt.secteur_id == context.secteur_id,
            TestHTTPAttempt.operator == context.operator,
            TestHTTPAttempt.technology == context.technology,

            # Reverted: the live DB is back on `time`, not
            # `test_start_time` (restored from a backup that predates
            # that rename) - this filter and the duration calc below
            # both need to match.
            TestHTTPAttempt.time.is_not(None),
            TestHTTPAttempt.test_end_time.is_not(None),

            # End must be after start
            TestHTTPAttempt.test_end_time > TestHTTPAttempt.time,
        ]

        # Duration in seconds
        duration_seconds = (
            extract(
                "epoch",
                TestHTTPAttempt.test_end_time
                - TestHTTPAttempt.time,
            )
        )

        # Total valid throughput measurements
        total = db.execute(
            select(func.count(TestHTTPAttempt.id)).where(
                *filters
            )
        ).scalar_one()

        if total == 0:
            return KPIComputationResult(
                value=None,
                numerator=0,
                denominator=0,
                is_computed=False,
            )

        # Throughput:
        #
        # 16 megabits / duration
        #
        # throughput > required
        #
        # 16 / duration > required
        #
        # equivalent to:
        #
        # duration < 16 / required

        max_duration_for_success = (
            FILE_SIZE_MEGABITS / debit_exige_mbps
        )

        success = db.execute(
            select(func.count(TestHTTPAttempt.id)).where(
                *filters,
                duration_seconds < max_duration_for_success,
            )
        ).scalar_one()

        value = round((success / total) * 100, 2)

        return KPIComputationResult(
            value=value,
            numerator=success,
            denominator=total,
            is_computed=True,
        )