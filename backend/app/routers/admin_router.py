from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.auth.dependencies import require_admin
from app.models.user import User
from app.models.config_models import BandThreshold, TechnologyThreshold, ChannelBandMapping, \
    DownloadDurationThreshold
from app.models.uploaded_file import UploadedFile
from app.models.raw_data import TestRSRP, TestHTTPAttempt, TestHTTPFailure
from app.models.geo import Gouvernorat, Delegation, Secteur
from app.archiving.file_archiver import delete_archived_file
from app.kpi_engine.engine import run_kpi_engine
from app.schemas.schemas import BandThresholdIn, BandThresholdOut, TechnologyThresholdIn, \
    TechnologyThresholdOut, DurationThresholdIn, DurationThresholdOut, DeleteByFilePathRequest, \
    DeleteBySiteRequest, GouvernoratOut, DelegationOut, SecteurOut

router = APIRouter(prefix="/admin", tags=["admin"])


# ---- Variable Control ----
# TAI's Taux_aff / Seuil Indoor: keyed by BAND ONLY (no operator dimension
# - confirmed, the source reference table has no operator column).
# TD's debit exige: keyed by TECHNOLOGY ONLY (also no operator dimension).

@router.get("/thresholds/bands", response_model=list[BandThresholdOut])
def list_band_thresholds(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(BandThreshold).order_by(BandThreshold.band).all()


@router.put("/thresholds/bands", response_model=BandThresholdOut)
def upsert_band_threshold(payload: BandThresholdIn, db: Session = Depends(get_db),
                           _: User = Depends(require_admin)):
    existing = db.query(BandThreshold).filter_by(band=payload.band).one_or_none()
    if existing:
        existing.taux_aff = payload.taux_aff
        existing.tai_threshold = payload.tai_threshold
        row = existing
    else:
        row = BandThreshold(**payload.model_dump())
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/thresholds/technologies", response_model=list[TechnologyThresholdOut])
def list_technology_thresholds(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(TechnologyThreshold).order_by(TechnologyThreshold.technology).all()


@router.put("/thresholds/technologies", response_model=TechnologyThresholdOut)
def upsert_technology_threshold(payload: TechnologyThresholdIn, db: Session = Depends(get_db),
                                 _: User = Depends(require_admin)):
    existing = db.query(TechnologyThreshold).filter_by(technology=payload.technology).one_or_none()
    if existing:
        existing.debit_exige_mbps = payload.debit_exige_mbps
        row = existing
    else:
        row = TechnologyThreshold(**payload.model_dump())
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---- Download duration cutoff (TAO/TAI "slow attempt" threshold) ----
# Singleton setting - single row, created on first PUT if it doesn't exist.

@router.get("/thresholds/duration", response_model=DurationThresholdOut)
def get_duration_threshold(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    row = db.query(DownloadDurationThreshold).first()
    if row is None:
        row = DownloadDurationThreshold(cutoff_seconds=10.0)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.put("/thresholds/duration", response_model=DurationThresholdOut)
def upsert_duration_threshold(payload: DurationThresholdIn, db: Session = Depends(get_db),
                               _: User = Depends(require_admin)):
    row = db.query(DownloadDurationThreshold).first()
    if row:
        row.cutoff_seconds = payload.cutoff_seconds
    else:
        row = DownloadDurationThreshold(cutoff_seconds=payload.cutoff_seconds)
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---- Channel -> band reference table (read-only via API for now; edit
# by re-running scripts/seed_channel_bands.py if the mapping changes) ----

@router.get("/channel-bands")
def list_channel_bands(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    rows = db.query(ChannelBandMapping).order_by(
        ChannelBandMapping.operator, ChannelBandMapping.band, ChannelBandMapping.channel
    ).all()
    return [
        {"id": r.id, "operator": r.operator, "channel": r.channel, "technology": r.technology, "band": r.band}
        for r in rows
    ]


# ---- Locations that actually have data (drives admin dropdowns, per the
# "only show places with data" request - based on the raw measurement
# tables, which is the authoritative signal of where real data lives,
# distinct from a file's single majority-sector archive location) ----

def _secteur_ids_with_data(db: Session) -> set[int]:
    ids: set[int] = set()
    for model in (TestRSRP, TestHTTPAttempt, TestHTTPFailure):
        rows = db.execute(select(model.secteur_id).where(model.secteur_id.is_not(None)).distinct()).scalars().all()
        ids.update(rows)
    return ids


@router.get("/locations/gouvernorats", response_model=list[GouvernoratOut])
def locations_gouvernorats(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    ids = _secteur_ids_with_data(db)
    if not ids:
        return []
    return (
        db.query(Gouvernorat)
        .join(Delegation, Delegation.gouvernorat_id == Gouvernorat.id)
        .join(Secteur, Secteur.delegation_id == Delegation.id)
        .filter(Secteur.id.in_(ids))
        .distinct()
        .order_by(Gouvernorat.name)
        .all()
    )


@router.get("/locations/delegations", response_model=list[DelegationOut])
def locations_delegations(gouvernorat_id: int = Query(...), db: Session = Depends(get_db),
                           _: User = Depends(require_admin)):
    ids = _secteur_ids_with_data(db)
    if not ids:
        return []
    return (
        db.query(Delegation)
        .join(Secteur, Secteur.delegation_id == Delegation.id)
        .filter(Secteur.id.in_(ids), Delegation.gouvernorat_id == gouvernorat_id)
        .distinct()
        .order_by(Delegation.name)
        .all()
    )


@router.get("/locations/secteurs", response_model=list[SecteurOut])
def locations_secteurs(delegation_id: int = Query(...), db: Session = Depends(get_db),
                        _: User = Depends(require_admin)):
    ids = _secteur_ids_with_data(db)
    if not ids:
        return []
    return (
        db.query(Secteur)
        .filter(Secteur.id.in_(ids), Secteur.delegation_id == delegation_id)
        .order_by(Secteur.name)
        .all()
    )


# ---- Uploaded file listing (drives the "delete by file" dropdown, built
# directly from the archiving records rather than free-text path entry) ----

@router.get("/files")
def list_uploaded_files(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    files = db.query(UploadedFile).order_by(UploadedFile.uploaded_at.desc()).all()
    return [
        {
            "id": f.id,
            "original_filename": f.original_filename,
            "log_type": f.log_type.value,
            "operator": f.operator,
            "technology": f.technology,
            "archive_path": f.archive_path,
            "majority_secteur_name": f.majority_secteur.name if f.majority_secteur else None,
            "row_count_clean": f.row_count_clean,
            "uploaded_at": f.uploaded_at,
        }
        for f in files
    ]


# ---- Manual KPI recompute (no upload needed) - use after changing
# thresholds/formulas, or any time results look stale ----

@router.post("/recompute-kpis")
def recompute_kpis(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return run_kpi_engine(db)


# ---- Data deletion ----

RAW_MODELS_BY_TYPE = {"rsrp": TestRSRP, "http_attempt": TestHTTPAttempt, "http_failure": TestHTTPFailure}


@router.delete("/data/by-file-path")
def delete_by_file_path(payload: DeleteByFilePathRequest, db: Session = Depends(get_db),
                         _: User = Depends(require_admin)):
    uploaded_file = db.query(UploadedFile).filter_by(archive_path=payload.archive_path).one_or_none()
    if uploaded_file is None:
        raise HTTPException(404, "No uploaded file found with that archive path")

    model_cls = RAW_MODELS_BY_TYPE[uploaded_file.log_type.value]
    deleted_rows = db.query(model_cls).filter_by(uploaded_file_id=uploaded_file.id).delete()

    delete_archived_file(payload.archive_path)
    db.delete(uploaded_file)
    db.commit()

    run_kpi_engine(db)
    return {"deleted_rows": deleted_rows, "archive_file_removed": True}


@router.delete("/data/by-site")
def delete_by_site(payload: DeleteBySiteRequest, db: Session = Depends(get_db),
                    _: User = Depends(require_admin)):
    """Deletes all measurement rows (all 3 raw tables) for a given Secteur
    (Site Name = adm4_name, per agreed definition)."""
    total_deleted = 0
    for model_cls in (TestRSRP, TestHTTPAttempt, TestHTTPFailure):
        total_deleted += db.query(model_cls).filter_by(secteur_id=payload.secteur_id).delete()

    db.commit()
    run_kpi_engine(db)
    return {"deleted_rows": total_deleted, "secteur_id": payload.secteur_id}
