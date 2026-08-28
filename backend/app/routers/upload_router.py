import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import require_admin
from app.models.user import User
from app.data_ingestion.upload_service import process_upload
from app.kpi_engine.engine import run_kpi_engine
from app.schemas.schemas import UploadResponse

router = APIRouter(prefix="/admin/upload", tags=["admin-upload"])

ALLOWED_LOG_TYPES = {"rsrp", "http_attempt"}
ALLOWED_OPERATORS = {"TT", "OO", "OR"}
ALLOWED_TECHNOLOGIES = {"4G", "4G_3G", "5G", "Unspecified"}


@router.post("", response_model=UploadResponse)
def upload_file(
    file: UploadFile = File(...),
    log_type: str = Form(...),
    operator: str = Form(...),
    technology: str | None = Form(None),
    recompute_kpis: bool = Form(True),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    if log_type not in ALLOWED_LOG_TYPES:
        raise HTTPException(400, f"log_type must be one of {sorted(ALLOWED_LOG_TYPES)}")
    if operator not in ALLOWED_OPERATORS:
        raise HTTPException(400, f"operator must be one of {sorted(ALLOWED_OPERATORS)}")
    if technology is not None and technology not in ALLOWED_TECHNOLOGIES:
        raise HTTPException(400, f"technology must be one of {sorted(ALLOWED_TECHNOLOGIES)}")
    if technology == "Unspecified" and log_type != "rsrp":
        raise HTTPException(400, "'Unspecified' (Free Tech) is only valid for RSRP uploads")
    if not file.filename.lower().endswith((".xlsx", ".csv")):
        raise HTTPException(400, "Only .xlsx or .csv files are accepted")

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        uploaded_file = process_upload(
            db=db, temp_file_path=tmp_path, original_filename=file.filename,
            log_type=log_type, operator=operator, technology=technology,
            uploaded_by_user_id=current_admin.id,
        )
        if recompute_kpis:
            run_kpi_engine(db)
    finally:
        tmp_path.unlink(missing_ok=True)

    return UploadResponse(
        uploaded_file_id=uploaded_file.id,
        original_filename=uploaded_file.original_filename,
        log_type=uploaded_file.log_type.value,
        operator=uploaded_file.operator,
        technology=uploaded_file.technology,
        row_count_raw=uploaded_file.row_count_raw,
        row_count_clean=uploaded_file.row_count_clean,
        archive_path=uploaded_file.archive_path,
        majority_secteur_id=uploaded_file.majority_secteur_id,
    )
