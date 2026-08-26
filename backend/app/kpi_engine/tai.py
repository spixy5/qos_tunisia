"""
TAI = Taux d'Accessibilite Internet Indoor

TAI =
    (successful outdoor HTTP measurements with estimated indoor RSRP
     >= configured threshold)
    /
    (total outdoor HTTP measurements)
    * 100

For each HTTP attempt:

1. The HTTP test must have test_status = "Success".
2. The HTTP serving_band identifies the band to evaluate.
3. Find an RSRP measurement:
       - same secteur
       - same operator
       - same band
       - "same position" means within POSITION_TOLERANCE_METERS (see
         below), using the existing geom columns via ST_DWithin
         (geography cast, so the distance is in real meters, not degrees).
       - within +/- 1 second
4. If several RSRP rows match, choose the closest in time.
5. Get taux_aff and tai_threshold from config_band_thresholds.
6. Estimate indoor RSRP:

       indoor_rsrp = outdoor_rsrp + taux_aff

7. Success if:

       indoor_rsrp >= tai_threshold

The denominator remains ALL HTTP outdoor measurements in the
(secteur, operator, technology) group.

The HTTP technology is NOT used when matching the RSRP row.
The technology is still used to separate KPI groups.
"""

from sqlalchemy import text

from app.kpi_engine.base import (
    BaseKPI,
    KPIContext,
    KPIComputationResult,
    register_kpi,
)

POSITION_TOLERANCE_METERS = 30

_QUERY = text("""
    WITH matched AS (
        SELECT
            ha.id AS attempt_id,
            ha.test_status,
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

              -- Operator must match
              AND r.operator = ha.operator

              -- HTTP serving_band must match RSRP band, tolerant of
              -- either the prefixed ('L1800') or bare ('1800') convention.
              AND regexp_replace(r.band, '^[^0-9]*', '') = regexp_replace(ha.serving_band, '^[^0-9]*', '')

              -- "same position" via real distance instead of exact float
              -- equality - geom is already a geography-castable PostGIS
              -- column on both tables, ST_DWithin uses the spatial index
              -- if present.
              AND ST_DWithin(
                    r.geom::geography,
                    ha.geom::geography,
                    :position_tolerance_m
              )

              -- Time matching window
              -- REVERTED: back to ha.time (not ha.test_start_time) - the
              -- live DB was restored from a backup that predates that
              -- rename, so TestHTTPAttempt.time is the real column again.
              AND r.time BETWEEN
                    ha.time - INTERVAL '1 second'
                AND ha.time + INTERVAL '1 second'

            -- If multiple rows match, choose the closest in time
            ORDER BY ABS(
                EXTRACT(EPOCH FROM (r.time - ha.time))
            )

            LIMIT 1

        ) nearest ON TRUE

        WHERE ha.secteur_id = :secteur_id
          AND ha.operator = :operator
          AND ha.technology = :technology
          -- Skip rows with no recorded test_status entirely (both
          -- numerator and denominator) instead of counting them as
          -- failures. These are pre-migration/legacy rows that never had
          -- this field at all - there's no real "outcome" to judge.
          AND ha.test_status IS NOT NULL
    )

    SELECT
        COUNT(*) AS total,

        COUNT(*) FILTER (
            WHERE
                LOWER(TRIM(m.test_status)) = 'success'

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
                "position_tolerance_m": POSITION_TOLERANCE_METERS,
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