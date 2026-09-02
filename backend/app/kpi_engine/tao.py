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
            # Removed: TestHTTPAttempt.test_end_time.is_not(None)
            # Same bug as tai.py (see chat): a failed test has no
            # test_end_time by definition, so this filter silently
            # dropped real failures from the denominator instead of
            # counting them as non-successes. The success filter below
            # already excludes them correctly on its own - a NULL
            # test_end_time makes time_diff NULL, and "NULL < 10" is
            # NULL (not true), so it's never counted as a success.
            # Both TAO and TAI need this fix together, or their
            # denominators stop matching each other for the same
            # underlying attempts.
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
                TestHTTPAttempt.test_end_time.is_not(None),
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