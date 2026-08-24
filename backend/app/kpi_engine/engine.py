"""
Orchestrates the modular KPI engine: for every (secteur, operator,
technology) combination present in the data, run each registered KPI in
dependency order (TAO, TAI, TD before PCPS) and upsert the result into
kpi_results.

Adding a new KPI later = create app/kpi_engine/<name>.py implementing
BaseKPI + @register_kpi, import it in __init__.py, done - this function
never needs to change.

NOTE: there is no shared "threshold_row" lookup here anymore. Each KPI
now looks up its own config independently, since they're keyed
differently: TAI by band (per RSRP row - see tai.py), TD by technology
(see td.py, still a placeholder), TAO/PCPS need no threshold lookup at
all. The old single OperatorThreshold(operator+technology+band) row is
gone.
"""
import logging
from sqlalchemy import select, distinct
from sqlalchemy.orm import Session

from app.kpi_engine.base import KPI_REGISTRY, KPIContext
from app.models.raw_data import TestHTTPAttempt
from app.models.kpi import KPIResult, KPIName

logger = logging.getLogger(__name__)

# TD/PCPS depend on TAO/TAI being computed first within the same pass.
KPI_RUN_ORDER = ["TAO", "TAI", "TD", "PCPS"]


def _distinct_combinations(db: Session) -> list[tuple[int, str, str | None]]:
    """
    TAI is computed entirely from TestHTTPAttempt now (each attempt row
    carries its own RSRP/channel/band - see kpi_engine/tai.py), so a
    combo only needs to exist here if there's HTTP attempt data. RSRP.xlsx
    uploads (TestRSRP) independently feed the map/trend chart via direct
    queries in dashboard_router.py, not through this KPI engine at all.
    """
    rows = db.execute(
        select(distinct(TestHTTPAttempt.secteur_id), TestHTTPAttempt.operator, TestHTTPAttempt.technology)
        .where(TestHTTPAttempt.secteur_id.is_not(None))
    ).all()
    return [(r[0], r[1], r[2]) for r in rows]


def run_kpi_engine(db: Session) -> dict:
    combinations = _distinct_combinations(db)
    results_count = 0

    for secteur_id, operator, technology in combinations:
        context = KPIContext(
            db=db, secteur_id=secteur_id, operator=operator,
            technology=technology, already_computed={},
        )

        for kpi_name in KPI_RUN_ORDER:
            kpi_cls = KPI_REGISTRY.get(kpi_name)
            if kpi_cls is None:
                continue
            result = kpi_cls().compute(context)
            context.already_computed[kpi_name] = result

            existing = db.execute(
                select(KPIResult).where(
                    KPIResult.secteur_id == secteur_id,
                    KPIResult.operator == operator,
                    KPIResult.technology == technology,
                    KPIResult.kpi_name == KPIName(kpi_name),
                )
            ).scalar_one_or_none()

            if existing:
                existing.value = result.value
                existing.numerator = result.numerator
                existing.denominator = result.denominator
                existing.is_computed = "true" if result.is_computed else "false"
            else:
                db.add(KPIResult(
                    secteur_id=secteur_id, operator=operator, technology=technology,
                    kpi_name=KPIName(kpi_name), value=result.value,
                    numerator=result.numerator, denominator=result.denominator,
                    is_computed="true" if result.is_computed else "false",
                ))
            results_count += 1

    db.commit()
    logger.info("KPI engine run complete: %d combinations, %d KPI rows upserted",
                len(combinations), results_count)
    return {"combinations": len(combinations), "kpi_rows_upserted": results_count}
