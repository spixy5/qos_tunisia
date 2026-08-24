from datetime import datetime
from pydantic import BaseModel, ConfigDict


# --- Auth ---
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


# --- Geo (for cascading dropdowns) ---
class GouvernoratOut(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class DelegationOut(BaseModel):
    id: int
    name: str
    gouvernorat_id: int
    model_config = ConfigDict(from_attributes=True)


class SecteurOut(BaseModel):
    id: int
    name: str
    delegation_id: int
    center_lat: float | None
    center_lon: float | None
    model_config = ConfigDict(from_attributes=True)


# --- Admin: thresholds ---
class BandThresholdIn(BaseModel):
    band: str
    taux_aff: float
    tai_threshold: float


class BandThresholdOut(BandThresholdIn):
    id: int
    updated_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class TechnologyThresholdIn(BaseModel):
    technology: str
    debit_exige_mbps: float | None = None


class TechnologyThresholdOut(TechnologyThresholdIn):
    id: int
    updated_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class DurationThresholdIn(BaseModel):
    cutoff_seconds: float


class DurationThresholdOut(DurationThresholdIn):
    id: int
    updated_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


# --- Upload ---
class UploadResponse(BaseModel):
    uploaded_file_id: int
    original_filename: str
    log_type: str
    operator: str
    technology: str | None
    row_count_raw: int | None
    row_count_clean: int | None
    archive_path: str | None
    majority_secteur_id: int | None


# --- Admin delete ---
class DeleteByFilePathRequest(BaseModel):
    archive_path: str


class DeleteBySiteRequest(BaseModel):
    secteur_id: int


# --- KPI / Dashboard ---
class KPIValueOut(BaseModel):
    kpi_name: str
    value: float | None
    numerator: int | None
    denominator: int | None
    is_computed: bool


class OperatorComparisonRow(BaseModel):
    operator: str
    technology: str | None
    tao: float | None
    tai: float | None
    td: float | None
    pcps: float | None


class LocationOverviewResponse(BaseModel):
    secteur_id: int
    secteur_name: str
    delegation_name: str
    gouvernorat_name: str
    overall_rating: float | None  # average PCPS across operators, null if none computed
    comparison: list[OperatorComparisonRow]


class DelegationOverviewResponse(BaseModel):
    delegation_id: int
    delegation_name: str
    gouvernorat_name: str
    secteurs_with_data: int
    overall_rating: float | None  # average PCPS across all secteurs+operators in this delegation
    comparison: list[OperatorComparisonRow]  # each row averaged across secteurs in the delegation
