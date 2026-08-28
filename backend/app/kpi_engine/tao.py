from sqlalchemy import select, func

from app.kpi_engine.base import (
    BaseKPI,
    KPIContext,
    KPIComputationResult,
    register_kpi,
)
from app.models.raw_data import TestHTTPAttempt


@register_kpi
class TAOKpi(BaseKPI):
    name = "TAO"

    def compute(self, context: KPIContext) -> KPIComputationResult:
        db = context.db

        filters = [
            TestHTTPAttempt.secteur_id == context.secteur_id,
            TestHTTPAttempt.operator == context.operator,
            TestHTTPAttempt.technology == context.technology,
            TestHTTPAttempt.test_start_time.is_not(None),
            TestHTTPAttempt.test_end_time.is_not(None),
        ]

        # Total HTTP outdoor measurements
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

        # Successful HTTP measurements: difference between end time and start time < 10 seconds
        time_diff = func.extract(
            "epoch", TestHTTPAttempt.test_end_time - TestHTTPAttempt.test_start_time
        )

        success = db.execute(
            select(func.count(TestHTTPAttempt.id)).where(
                *filters,
                time_diff < 10,
            )
        ).scalar_one()

        value = round((success / total) * 100, 2)

        return KPIComputationResult(
            value=value,
            numerator=success,
            denominator=total,
            is_computed=True,
        )