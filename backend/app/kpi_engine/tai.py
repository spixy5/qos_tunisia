"""
TAI = Taux d'Accessibilite Internet Indoor

TAI =
    (successful outdoor HTTP measurements with estimated indoor RSRP
     >= configured threshold, based on time difference < 10 seconds)
    /
    (total outdoor HTTP measurements)
    * 100

For each HTTP attempt:
1. Instead of relying solely on test_status = 'Success', success is defined
   by checking that (test_end_time - test_start_time) < 10 seconds.
2. The HTTP serving_band identifies the band to evaluate.
3. Find an RSRP measurement within TIME_TOLERANCE_SECONDS matching
   secteur, operator, and band.
4. Estimate indoor RSRP: indoor_rsrp = outdoor_rsrp + taux_aff
5. Success if: indoor_rsrp >= tai_threshold AND time difference < 10 seconds.
"""

from sqlalchemy import text

from app.kpi_engine.base import (
    BaseKPI,
    KPIContext,
    KPIComputationResult,
    register_kpi,
)

TIME_TOLERANCE_SECONDS = 60

_QUERY = text("""
    WITH matched AS (
        SELECT
            ha.id AS attempt_id,
            ha.test_start_time,
            ha.test_end_time,
            ha.serving_band,

            nearest.best_rsrp,
            nearest.band

        FROM test_http_attempt ha

        LEFT JOIN LATERAL (
            SELECT
                r.best_rsrp,
                r.band

            FROM test_rsrp r

            WHERE r.secteur_id = ha.secteur_id
              AND r.operator = ha.operator
              AND regexp_replace(r.band, '^[^0-9]*', '') = regexp_replace(ha.serving_band, '^[^0-9]*', '')
              AND r.time BETWEEN
                    ha.test_start_time - (:time_tolerance_s || ' seconds')::INTERVAL
                AND ha.test_start_time + (:time_tolerance_s || ' seconds')::INTERVAL

            ORDER BY ABS(
                EXTRACT(EPOCH FROM (r.time - ha.test_start_time))
            )

            LIMIT 1

        ) nearest ON TRUE

        WHERE ha.secteur_id = :secteur_id
          AND ha.operator = :operator
          AND ha.technology = :technology
          AND ha.test_start_time IS NOT NULL
          AND ha.test_end_time IS NOT NULL
    )

    SELECT
        COUNT(*) AS total,

        COUNT(*) FILTER (
            WHERE
                EXTRACT(EPOCH FROM (m.test_end_time - m.test_start_time)) < 10

                AND m.best_rsrp IS NOT NULL
                AND m.band IS NOT NULL

                AND (
                    m.best_rsrp + COALESCE(bt.taux_aff, 0)
                ) >= COALESCE(bt.tai_threshold, -100)
        ) AS success

    FROM matched m

    LEFT JOIN config_band_thresholds bt
        ON regexp_replace(bt.band, '^[^0-9]*', '') = regexp_replace(m.serving_band, '^[^0-9]*', '')
""")


@register_kpi
class TAIKpi(BaseKPI):
    name = "TAI"

    def compute(self, context: KPIContext) -> KPIComputationResult:

        row = context.db.execute(
            _QUERY,
            {
                "secteur_id": context.secteur_id,
                "operator": context.operator,
                "technology": context.technology,
                "time_tolerance_s": TIME_TOLERANCE_SECONDS,
            },
        ).one()

        total = row.total
        success = row.success

        if total == 0:
            return KPIComputationResult(
                value=None,
                numerator=0,
                denominator=0,
                is_computed=False,
            )

        value = round((success / total) * 100, 2)

        return KPIComputationResult(
            value=value,
            numerator=success,
            denominator=total,
            is_computed=True,
        )