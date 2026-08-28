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
block the upload response.
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

# CHANGED: added rscp/sc - both exist on the model and are produced by
# the parser, but were missing from this list, so they were silently
# never being inserted despite being present in every RSRP row's data.
RSRP_COLS = [
    "time", "best_rsrp", "channel", "band", "dl_bw", "pci", "to_interval",
    "rscp", "sc",
    "latitude", "longitude", "operator", "technology",
    "secteur_id", "delegation_id", "gouvernorat_id",
]

# CHANGED: test_http_attempt no longer has channel/band/redirect_address/
# failure_cause at all (see models.py) - keeping them here was harmless
# only because `keep_cols` filters to columns present in the dataframe,
# but it's misleading to list columns that don't exist on the table.
# Also: "time" -> "test_start_time" to match the actual column name.
HTTP_ATTEMPT_COLS = [
    "test_start_time",
    "test_end_time",
    "system",
    "serving_band",
    "application_protocol",
    "test_status",
    "download_duration_seconds",
    "best_rsrp",
    "best_rscp",
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

    # CHANGED: only rsrp has channel/band to resolve now - test_http_attempt
    # dropped both columns entirely, so calling this for "http" was dead
    # weight (or worse, relied on it silently no-op'ing on a missing
    # `channel` column).
    if log_type == "rsrp":
        df = attach_band_column(df, operator, db)

    logger.info("BEFORE CLEAN %s columns: %s", log_type, df.columns.tolist())

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