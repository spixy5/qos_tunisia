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

CHANGED: `technology` on a combo is the *campaign* label, which for
mixed-coverage secteurs is "4G_3G" rather than "4G" or "3G" individually
(see file_archive/.../http_attempt/4G_3G/... and
data_ingestion/parsers.py::read_http, which just stamps the campaign's
technology string onto every row - it does not mean every row in a
"4G_3G" campaign was actually served on both). Each attempt row DOES
carry its own real serving system in `system` (parsed from "Start
system and band", e.g. "LTE FDD" / "UMTS" - see
parsers.py::_parse_system_and_band), which is what previously-missing
TD support for "4G_3G" needs: apply the 4G threshold to rows actually
served on LTE and the 3G threshold to rows served on UMTS/WCDMA within
the same campaign, instead of failing the whole combo because
"4G_3G" isn't a key in the threshold tables. Pure "4G"/"3G" combos are
unaffected - behavior for them is identical to before.
"""

from sqlalchemy import select

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

# Substrings of TestHTTPAttempt.system (itself derived from the "Start
# system and band" export column) that identify which regulatory
# threshold a given row falls under.
SYSTEM_MARKERS = {
    "4G": ("LTE",),
    "3G": ("UMTS", "WCDMA", "3G"),
}


def _max_allowed_duration(tech: str) -> float:
    file_size_megabits = FILE_SIZES_MB[tech] * 8.0
    required_mbps = REQUIRED_THROUGHPUT_MBPS[tech]
    return file_size_megabits / required_mbps


def _row_technology(system_value: str | None, techs_to_check: list[str]) -> str | None:
    """
    Resolve which of `techs_to_check` a single HTTP attempt row belongs
    to, for the purpose of picking its required-throughput threshold.

    - Single-tech combos ("4G" or "3G" campaigns): every row belongs to
      that one technology, regardless of `system` - unchanged from the
      old behavior (which never looked at `system` at all).
    - Mixed combos ("4G_3G" campaigns): inspect `system` to tell whether
      this particular row was actually served on LTE or on UMTS/WCDMA.
      Rows with an unrecognized/missing `system` are excluded from both
      numerator and denominator (not a valid throughput measurement we
      can attribute a threshold to).
    """
    if len(techs_to_check) == 1:
        return techs_to_check[0]

    if not system_value:
        return None

    system_upper = str(system_value).upper()
    for tech in techs_to_check:
        if any(marker in system_upper for marker in SYSTEM_MARKERS[tech]):
            return tech
    return None


@register_kpi
class TDKpi(BaseKPI):
    name = "TD"

    def compute(self, context: KPIContext) -> KPIComputationResult:
        db = context.db

        tech_key = (context.technology or "").upper()

        if tech_key in FILE_SIZES_MB:
            techs_to_check = [tech_key]
        elif tech_key == "4G_3G":
            techs_to_check = ["4G", "3G"]
        else:
            # Unknown campaign technology label - do not fall back.
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

        rows = db.execute(
            select(TestHTTPAttempt.system, TestHTTPAttempt.download_duration_seconds)
            .where(*filters)
        ).all()

        total = 0
        success = 0
        for system_value, duration in rows:
            row_tech = _row_technology(system_value, techs_to_check)
            if row_tech is None:
                continue
            total += 1
            if duration <= _max_allowed_duration(row_tech):
                success += 1

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