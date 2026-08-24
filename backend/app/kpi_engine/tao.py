"""
TAO = Taux d'Accessibilite Internet Outdoor

TAO = (successful HTTP measurements / total HTTP measurements) * 100

For the new HTTP format:
    Test status = "Success"  -> successful measurement
    Any other status          -> failed measurement

The KPI is calculated independently for:
    (secteur, operator, technology)

TestHTTPFailure is NOT used for TAO because success/failure is now
explicitly represented by TestHTTPAttempt.test_status.
"""

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

        # Successful HTTP measurements
        success = db.execute(
            select(func.count(TestHTTPAttempt.id)).where(
                *filters,
                func.lower(func.trim(TestHTTPAttempt.test_status))
                == "success",
            )
        ).scalar_one()

        value = round((success / total) * 100, 2)

        return KPIComputationResult(
            value=value,
            numerator=success,
            denominator=total,
            is_computed=True,
        )