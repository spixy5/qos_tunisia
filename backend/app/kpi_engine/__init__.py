"""
Importing this package registers every KPI implementation into KPI_REGISTRY
(base.py) via their @register_kpi decorator. To add a new KPI later:
  1. Create app/kpi_engine/my_new_kpi.py implementing BaseKPI + @register_kpi
  2. Add an import line below
  3. Add it to KPI_RUN_ORDER in engine.py if it has dependencies on others
No other file needs to change.
"""
from app.kpi_engine.tao import TAOKpi    # noqa: F401
from app.kpi_engine.tai import TAIKpi    # noqa: F401
from app.kpi_engine.td import TDKpi      # noqa: F401
from app.kpi_engine.pcps import PCPSKpi  # noqa: F401
