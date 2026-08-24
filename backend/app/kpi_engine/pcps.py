"""
PCPSi = 100 * min(1, cuberoot( (TAO/0.95) * (TAI/0.7) * (TD/0.95) ))

REVISED formula (confirmed - do not use the old one):
  - Old: 100 * min(1, (TAO/95)*(TAI/95)*(TD/95))  [no root, all refs 0.95]
  - New: 100 * min(1, cuberoot[(TAO/0.95)*(TAI/0.7)*(TD/0.95)])

TAO/TAI/TD from the KPI engine are already 0-100 percentages, so the
0.95/0.7/0.95 fractional references translate to /95, /70, /95 here
(mathematically identical - (TAO_pct/100)/0.95 == TAO_pct/95).

Grouping is UNCHANGED - still per (secteur, operator, technology), same
as TAO/TAI/TD. The three reference constants (95/70/95) are fixed in
the formula itself now, not admin-configurable (the old shared
`pcps_reference` field is gone - see models/config_models.py).

Depends on TAO, TAI, TD already being computed for the same combo -
engine.py guarantees this via KPI_RUN_ORDER. Reports is_computed=False
(no fabricated score) until all three are actually computed - currently
that means PCPS stays "not computed" until TD.py is implemented for real
(it's a placeholder returning None - see td.py).
"""
from app.kpi_engine.base import BaseKPI, KPIContext, KPIComputationResult, register_kpi

TAO_REFERENCE = 95.0
TAI_REFERENCE = 70.0
TD_REFERENCE = 95.0


@register_kpi
class PCPSKpi(BaseKPI):
    name = "PCPS"

    def compute(self, context: KPIContext) -> KPIComputationResult:
        already = context.already_computed or {}
        tao = already.get("TAO")
        tai = already.get("TAI")
        td = already.get("TD")

        if not (tao and tai and td) or not (tao.is_computed and tai.is_computed and td.is_computed):
            return KPIComputationResult(value=None, numerator=None, denominator=None, is_computed=False)

        ratio = (tao.value / TAO_REFERENCE) * (tai.value / TAI_REFERENCE) * (td.value / TD_REFERENCE)
        cube_root = ratio ** (1.0 / 3.0)
        value = round(100 * min(1.0, cube_root), 2)

        return KPIComputationResult(value=value, numerator=None, denominator=None, is_computed=True)