"""
Base interface every KPI module implements, so new formulas can be dropped
in later (per the requirement: "inject new mathematical formulas later
without breaking the pipeline") without touching engine.py's orchestration
logic - engine.py only ever calls `.compute(context)` on whatever is
registered in KPI_REGISTRY.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class KPIComputationResult:
    value: float | None       # None = not computed (e.g. TD before success-log exists)
    numerator: int | None
    denominator: int | None
    is_computed: bool = True


class BaseKPI(ABC):
    name: str  # matches models.kpi.KPIName value, e.g. "TAO"

    @abstractmethod
    def compute(self, context: "KPIContext") -> KPIComputationResult:
        """context carries the DB session + secteur_id + operator + technology
        for that combination. Each KPI looks up its own config independently
        now (band for TAI, technology for TD) - see the individual modules."""
        raise NotImplementedError


@dataclass
class KPIContext:
    db: object            # sqlalchemy Session (typed loosely to avoid circular import)
    secteur_id: int
    operator: str
    technology: str | None
    # Populated on demand by engine.py once TAO/TAI are computed, since PCPS
    # depends on them and TD depends on nothing else here.
    already_computed: dict[str, "KPIComputationResult"] | None = None


KPI_REGISTRY: dict[str, type[BaseKPI]] = {}


def register_kpi(cls: type[BaseKPI]) -> type[BaseKPI]:
    KPI_REGISTRY[cls.name] = cls
    return cls
