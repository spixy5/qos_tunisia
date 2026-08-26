"""
Orchestrates the full automated pipeline triggered by a single file upload:

  1. Parse (data_ingestion/parsers.py) - standardize columns per log type
  2. Clean (preprocessing/cleaning.py) - dedup, drop null/invalid GPS
  3. Spatial join (spatial_mapping/spatial_join.py) - resolve gouvernorat/
     delegation/secteur per row
  4. Insert cleaned+joined rows into the appropriate split table
     (test_rsrp / test_http_attempt)
  5. Archive a copy of the ORIGINAL raw file under the majority-sector path
  6. Re-run the KPI engine for affected combinations

Steps 1-5 happen synchronously in this function; step 6 is left as an
explicit follow-up call from the router so a slow KPI recompute doesn't
block the upload response (kept simple/synchronous here - swap for a
background task queue like Celery/RQ if upload volume grows).

NOTE: there is deliberately no attempt<->failure matching step here.
Inspection of the real sample files showed http_attempt and http_failure
are not duplicate logs needing a join - each test cycle produces exactly
one row in one of the two files (see kpi_engine/tao.py for the evidence).
TAO/TAI compute directly from row counts in the two tables.
"""
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.data_ingestion.parsers import parse_uploaded_file
from app.data_ingestion.channel_band_lookup import attach_band_column
from app.preprocessing.cleaning import clean_dataframe
from app.spatial_mapping.spatial_join import spatial_join_points, majority_secteur_id
from app.archiving.file_archiver import archive_file
from app.models.uploaded_file import UploadedFile, LogType
from app.models.geo import Secteur
from app.models.raw_data import TestRSRP, TestHTTPAttempt

logger = logging.getLogger(__name__)

ROW_MODEL = {
    "rsrp": TestRSRP,
    "http_attempt": TestHTTPAttempt,
}

RSRP_COLS = ["time", "best_rsrp", "channel", "band", "dl_bw", "pci", "to_interval",
             "latitude", "longitude", "operator", "technology",
             "secteur_id", "delegation_id", "gouvernorat_id"]  # gouvernorat_id/delegation_id filled below
HTTP_ATTEMPT_COLS = [
    "time",
    "test_end_time",
    "system",
    "serving_band",
    "application_protocol",
    "test_status",
    "download_duration_seconds",
    "best_rsrp",
    "best_rscp",
    "channel",
    "band",
    "redirect_address",
    "failure_cause",
    "latitude",
    "longitude",
    "operator",
    "technology",
    "secteur_id",
    "delegation_id",
    "gouvernorat_id",
]

COLS_BY_TYPE = {"rsrp": RSRP_COLS, "http_attempt": HTTP_ATTEMPT_COLS}

_HTTP_DEBUG_PREVIEW_COLS = ["test_status", "test_end_time", "download_duration_seconds"]


def _attach_gouvernorat_delegation_ids(df: pd.DataFrame, db: Session) -> pd.DataFrame:
    """spatial_join_points resolves secteur_id/name + delegation_name/gouvernorat_name
    (strings). Raw tables store FK ids for gouvernorat/delegation too, so resolve
    those ids here via the Secteur -> Delegation -> Gouvernorat chain, keyed by secteur_id."""
    if "secteur_id" not in df.columns:
        df["delegation_id"] = None
        df["gouvernorat_id"] = None
        return df

    secteur_ids = [int(s) for s in df["secteur_id"].dropna().unique()]
    if not secteur_ids:
        df["delegation_id"] = None
        df["gouvernorat_id"] = None
        return df

    secteurs = db.query(Secteur).filter(Secteur.id.in_(secteur_ids)).all()
    deleg_by_secteur = {s.id: s.delegation_id for s in secteurs}
    gov_by_secteur = {s.id: s.delegation.gouvernorat_id for s in secteurs}

    df["delegation_id"] = df["secteur_id"].map(deleg_by_secteur)
    df["gouvernorat_id"] = df["secteur_id"].map(gov_by_secteur)
    return df


def process_upload(db: Session, temp_file_path: Path, original_filename: str,
                    log_type: str, operator: str, technology: str | None,
                    uploaded_by_user_id: int | None) -> UploadedFile:
    # 1. Parse
    df = parse_uploaded_file(temp_file_path, log_type, operator, technology)
    raw_rows = len(df)

    if log_type in ("rsrp", "http_attempt"):
        df = attach_band_column(df, operator, db)

    logger.info(
        "BEFORE CLEAN HTTP columns: %s",
        df.columns.tolist()
    )

    if log_type == "http_attempt":
        preview_cols = [c for c in _HTTP_DEBUG_PREVIEW_COLS if c in df.columns]
        logger.info(
            "BEFORE CLEAN HTTP VALUES:\n%s",
            df[preview_cols].head(10).to_string()
        )
    # 2. Clean
    df, clean_stats = clean_dataframe(df)
    if log_type == "http_attempt":
        preview_cols = [c for c in _HTTP_DEBUG_PREVIEW_COLS if c in df.columns]
        logger.info(
            "AFTER CLEAN HTTP VALUES:\n%s",
            df[preview_cols].head(10).to_string()
        )

    # 3. Spatial join
    if not df.empty:
        df = spatial_join_points(df, db)
        df = _attach_gouvernorat_delegation_ids(df, db)
    else:
        df["secteur_id"] = None
        df["delegation_id"] = None
        df["gouvernorat_id"] = None

    # 4. Create UploadedFile record first (rows need its id as FK)
    uploaded_file = UploadedFile(
        original_filename=original_filename,
        log_type=LogType(log_type),
        operator=operator,
        technology=technology,
        row_count_raw=raw_rows,
        row_count_clean=len(df),
        uploaded_by_user_id=uploaded_by_user_id,
    )
    db.add(uploaded_file)
    db.flush()

    # 5. Insert cleaned+joined rows into the correct split table
    model_cls = ROW_MODEL[log_type]
    keep_cols = [c for c in COLS_BY_TYPE[log_type] if c in df.columns]
    records = df[keep_cols].astype(object).where(pd.notnull(df[keep_cols]), None).to_dict(orient="records")
    for rec in records:
        rec["uploaded_file_id"] = uploaded_file.id
        db.add(model_cls(**rec))

    # 6. Archive the ORIGINAL raw file under majority-sector path
    maj_secteur_id = majority_secteur_id(df)
    if maj_secteur_id is not None:
        secteur = db.query(Secteur).get(maj_secteur_id)
        archive_path = archive_file(
            source_path=temp_file_path,
            gouvernorat=secteur.gouvernorat_name,
            delegation=secteur.delegation_name,
            secteur=secteur.name,
            type_de_test=log_type,
            technologie=technology,
            original_filename=original_filename,
        )
        uploaded_file.majority_secteur_id = maj_secteur_id
        uploaded_file.archive_path = archive_path
    else:
        logger.warning("No sector resolved for upload %s - file not archived, only DB rows inserted "
                        "(if any survived cleaning)", original_filename)

    db.commit()

    logger.info("Upload processed: %s (%s/%s) - raw=%d clean=%d stats=%s",
                original_filename, operator, technology, raw_rows, len(df), clean_stats)
    return uploaded_file