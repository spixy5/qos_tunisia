from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.geo import Gouvernorat, Delegation, Secteur
from app.models.kpi import KPIResult, KPIName
# CHANGED: TestHTTPFailure no longer exists - failure rows now live inside
# TestHTTPAttempt itself (test_status = "Success"/"Fail"), per the new
# unified "Home operator" export format.
from app.models.raw_data import TestRSRP, TestHTTPAttempt
from app.models.config_models import BandThreshold
from app.schemas.schemas import GouvernoratOut, DelegationOut, SecteurOut, \
    LocationOverviewResponse, DelegationOverviewResponse, OperatorComparisonRow

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

OPERATORS = ["TT", "OO", "OR"]

# Shared level -> FK column mappings, used by raw-logs and bad-rsrp-points.
LEVEL_FK_RSRP = {
    "gouvernorat": TestRSRP.gouvernorat_id,
    "delegation": TestRSRP.delegation_id,
    "secteur": TestRSRP.secteur_id,
}
LEVEL_FK_ATTEMPT = {
    "gouvernorat": TestHTTPAttempt.gouvernorat_id,
    "delegation": TestHTTPAttempt.delegation_id,
    "secteur": TestHTTPAttempt.secteur_id,
}


def _band_threshold(db: Session, band: str | None) -> BandThreshold | None:
    """TAI parameters are keyed by band only (no operator/technology
    dimension) - see models/config_models.py:BandThreshold."""
    if band is None:
        return None
    return db.query(BandThreshold).filter_by(band=band).one_or_none()


def _band_threshold_by_serving_band(db: Session, serving_band: str | None) -> BandThreshold | None:
    """Resolve a threshold row from an HTTP attempt's serving_band field.
    ASSUMPTION: serving_band values match BandThreshold.band values
    exactly. Verify this holds for the new unified export format —
    if serving_band uses a different naming scheme, this will always
    miss and silently fall back to defaults (taux_aff=0.0, threshold=-100.0)."""
    if serving_band is None:
        return None
    return db.query(BandThreshold).filter_by(band=serving_band).one_or_none()


@router.get("/area-quality")
def area_quality(level: str = Query(..., pattern="^(gouvernorat|delegation|secteur)$"),
                  id: int = Query(...), operator: str | None = Query(None),
                  db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    fk_col = {
        "gouvernorat": TestRSRP.gouvernorat_id,
        "delegation": TestRSRP.delegation_id,
        "secteur": TestRSRP.secteur_id,
    }[level]

    base_filters = [fk_col == id]
    if operator and operator != "ALL":
        base_filters.append(TestRSRP.operator == operator)

    bands_present = (
        db.query(TestRSRP.band).filter(*base_filters, TestRSRP.band.is_not(None)).distinct().all()
    )

    total_all = 0
    success_all = 0
    for (band,) in bands_present:
        threshold_row = _band_threshold(db, band)
        taux_aff = threshold_row.taux_aff if threshold_row else 0.0
        threshold = threshold_row.tai_threshold if threshold_row else -100.0

        band_filters = base_filters + [TestRSRP.band == band]
        total = db.query(func.count(TestRSRP.id)).filter(*band_filters).scalar()
        success = db.query(func.count(TestRSRP.id)).filter(
            *band_filters, (TestRSRP.best_rsrp + taux_aff) > threshold
        ).scalar()
        total_all += total
        success_all += success

    quality_pct = round((success_all / total_all) * 100, 2) if total_all else None

    return {
        "level": level, "id": id, "operator": operator or "ALL",
        "quality_pct": quality_pct, "sample_count": total_all,
    }


@router.get("/rsrp-trend")
def rsrp_trend(level: str = Query(..., pattern="^(gouvernorat|delegation|secteur)$"),
               id: int = Query(...), operator: str | None = Query(None),
               bucket: str = Query("hour", pattern="^(hour|day)$"),
               db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    fk_col = {
        "gouvernorat": TestRSRP.gouvernorat_id,
        "delegation": TestRSRP.delegation_id,
        "secteur": TestRSRP.secteur_id,
    }[level]

    q = db.query(
        func.date_trunc(bucket, TestRSRP.time).label("bucket"),
        func.avg(TestRSRP.best_rsrp).label("avg_rsrp"),
        func.count(TestRSRP.id).label("sample_count"),
    ).filter(fk_col == id)

    if operator and operator != "ALL":
        q = q.filter(TestRSRP.operator == operator)

    rows = q.group_by("bucket").order_by("bucket").all()

    fmt = "%Y-%m-%d %H:%M" if bucket == "hour" else "%Y-%m-%d"
    return [
        {"bucket": r.bucket.strftime(fmt), "avgRsrp": round(r.avg_rsrp, 1), "sampleCount": r.sample_count}
        for r in rows
    ]


# ---- Raw log drill-down (union of RSRP + HTTP attempt rows, each tagged
# by log type). CHANGED: there is no separate http_failure table anymore -
# a "Fail" HTTP result is a TestHTTPAttempt row with test_status = "Fail"
# rather than a different table. log_type still accepts "http_failure" as
# a query value (so the frontend doesn't need to change) but it's now
# just an alias meaning "http_attempt rows where test_status = Fail". ----

@router.get("/raw-logs")
def raw_logs(level: str = Query(..., pattern="^(gouvernorat|delegation|secteur)$"),
             id: int = Query(...), operator: str | None = Query(None),
             result: str | None = Query(None, pattern="^(Pass|Fail)$"),
             log_type: str | None = Query(None, pattern="^(rsrp|http_attempt|http_failure)$"),
             limit: int = Query(1500, le=5000),
             db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """
    IMPORTANT: result/log_type filtering happens HERE (server-side, per
    operator+technology threshold combo) rather than being applied
    client-side after an arbitrary "most recent N rows" fetch.
    """
    rsrp_fk = {"gouvernorat": TestRSRP.gouvernorat_id, "delegation": TestRSRP.delegation_id,
               "secteur": TestRSRP.secteur_id}[level]
    attempt_fk = {"gouvernorat": TestHTTPAttempt.gouvernorat_id, "delegation": TestHTTPAttempt.delegation_id,
                  "secteur": TestHTTPAttempt.secteur_id}[level]

    secteur_cache: dict[int, str | None] = {}

    def secteur_name(sid: int | None) -> str | None:
        if sid is None:
            return None
        if sid not in secteur_cache:
            s = db.query(Secteur).get(sid)
            secteur_cache[sid] = s.name if s else None
        return secteur_cache[sid]

    want_rsrp = log_type in (None, "rsrp")
    # CHANGED: attempt rows can now be Pass OR Fail (test_status), so this
    # branch is the only source of Fail rows now. "http_failure" is
    # treated as an alias for "http_attempt rows with test_status = Fail"
    # so old frontend query params keep working unchanged.
    want_attempt = log_type in (None, "http_attempt", "http_failure")

    results = []

    if want_rsrp:
        base_filters = [rsrp_fk == id]
        if operator and operator != "ALL":
            base_filters.append(TestRSRP.operator == operator)
        base_filters.append(TestRSRP.band.is_not(None))

        combos = db.query(TestRSRP.operator, TestRSRP.technology, TestRSRP.band).filter(*base_filters).distinct().all()
        for op, tech, band in combos:
            remaining = limit - len(results)
            if remaining <= 0:
                break
            threshold_row = _band_threshold(db, band)
            taux_aff = threshold_row.taux_aff if threshold_row else 0.0
            threshold = threshold_row.tai_threshold if threshold_row else -100.0

            combo_filters = base_filters + [TestRSRP.operator == op, TestRSRP.technology == tech, TestRSRP.band == band]
            if result == "Pass":
                combo_filters.append((TestRSRP.best_rsrp + taux_aff) > threshold)
            elif result == "Fail":
                combo_filters.append((TestRSRP.best_rsrp + taux_aff) <= threshold)

            rows = db.query(TestRSRP).filter(*combo_filters).order_by(TestRSRP.time.desc()).limit(remaining).all()
            for r in rows:
                passed = (r.best_rsrp + taux_aff) > threshold
                results.append({
                    "id": f"rsrp_{r.id}", "logType": "rsrp",
                    "timestamp": r.time.strftime("%Y-%m-%d %H:%M:%S"),
                    "operator": r.operator, "technology": r.technology, "secteurName": secteur_name(r.secteur_id),
                    "rsrp": r.best_rsrp, "httpStatusLabel": None, "result": "Pass" if passed else "Fail",
                })

    if want_attempt:
        remaining = limit - len(results)
        if remaining > 0:
            attempt_q = db.query(TestHTTPAttempt).filter(attempt_fk == id)
            if operator and operator != "ALL":
                attempt_q = attempt_q.filter(TestHTTPAttempt.operator == operator)
            # CHANGED: filter by test_status instead of assuming every
            # attempt row is a Pass.
            if result == "Pass":
                attempt_q = attempt_q.filter(func.lower(func.trim(TestHTTPAttempt.test_status)) == "success")
            elif result == "Fail" or log_type == "http_failure":
                # FIXED: was checking == "fail", but the parser normalizes
                # failed statuses to "Failure" (see _normalize_status),
                # not "Fail" - "failure".lower() never equals "fail", so
                # this filter matched zero rows even when real failures
                # existed. Treat anything that isn't "success" as a
                # failure instead, matching the is_success check below.
                attempt_q = attempt_q.filter(func.lower(func.trim(TestHTTPAttempt.test_status)) != "success")

            for r in attempt_q.order_by(TestHTTPAttempt.test_start_time.desc()).limit(remaining).all():
                is_success = (r.test_status or "").strip().lower() == "success"
                results.append({
                    "id": f"attempt_{r.id}", "logType": "http_attempt",
                    "timestamp": r.test_start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "operator": r.operator, "technology": r.technology, "secteurName": secteur_name(r.secteur_id),
                    "rsrp": None,
                    "httpStatusLabel": "Succes" if is_success else (r.test_status or "Echec (cause inconnue)"),
                    "result": "Pass" if is_success else "Fail",
                })

    results.sort(key=lambda x: x["timestamp"], reverse=True)
    return results[:limit]


@router.get("/bad-rsrp-points")
def bad_rsrp_points(level: str = Query(..., pattern="^(gouvernorat|delegation|secteur)$"),
                     id: int = Query(...), operator: str | None = Query(None),
                     technology: str | None = Query(None),
                     limit: int = Query(2000, le=5000),
                     db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """
    Returns EVERY point (both passing and failing), not just failures -
    each one tagged with status: "good" | "bad". Endpoint path/name kept
    as-is (avoids a breaking frontend URL change) but the response shape
    changed: previously this only ever returned failing points, so a
    place with 100% quality correctly showed nothing on the map, which
    looked broken even though it wasn't. Now the map can render both.

    - RSRP rows: status "bad" if (best_rsrp + taux_aff) <= tai_threshold
      for their resolved band, else "good".
    - HTTP attempt rows: status "bad" if test_status is an explicit
      failure, OR - when a signal reading is present (best_rsrp/best_rscp)
      - it fails the same band-threshold check via serving_band. "good"
      otherwise.

    `operator`/`technology` are optional filters; omitted or "ALL" means
    every operator/technology for this place.
    """
    rsrp_fk = LEVEL_FK_RSRP[level]
    attempt_fk = LEVEL_FK_ATTEMPT[level]

    points = []

    # --- RSRP points (both good and bad) ---------------------------------
    rsrp_base_filters = [rsrp_fk == id]
    if operator and operator != "ALL":
        rsrp_base_filters.append(TestRSRP.operator == operator)
    if technology and technology != "ALL":
        rsrp_base_filters.append(TestRSRP.technology == technology)

    bands_present = (
        db.query(TestRSRP.band).filter(*rsrp_base_filters).distinct().all()
    )

    for (band,) in bands_present:
        if len(points) >= limit:
            break
        threshold_row = _band_threshold(db, band) if band is not None else None
        taux_aff = threshold_row.taux_aff if threshold_row else 0.0
        threshold = threshold_row.tai_threshold if threshold_row else -100.0

        band_filters = list(rsrp_base_filters)
        if band is not None:
            band_filters.append(TestRSRP.band == band)
        else:
            band_filters.append(TestRSRP.band.is_(None))

        rows = (
            db.query(TestRSRP.latitude, TestRSRP.longitude, TestRSRP.best_rsrp,
                     TestRSRP.operator, TestRSRP.technology)
            .filter(*band_filters)
            .filter(TestRSRP.latitude.is_not(None), TestRSRP.longitude.is_not(None))
            .limit(limit - len(points))
            .all()
        )
        for r in rows:
            passed = (r.best_rsrp + taux_aff) > threshold
            points.append({
                "lat": r.latitude, "lon": r.longitude, "rsrp": r.best_rsrp,
                "operator": r.operator, "technology": r.technology, "logType": "rsrp",
                "status": "good" if passed else "bad",
            })

    # --- HTTP attempt points (both good and bad) --------------------------
    if len(points) < limit:
        attempt_base_filters = [attempt_fk == id]
        if operator and operator != "ALL":
            attempt_base_filters.append(TestHTTPAttempt.operator == operator)
        if technology and technology != "ALL":
            attempt_base_filters.append(TestHTTPAttempt.technology == technology)

        attempt_rows = (
            db.query(TestHTTPAttempt)
            .filter(*attempt_base_filters)
            .filter(TestHTTPAttempt.latitude.is_not(None), TestHTTPAttempt.longitude.is_not(None))
            .limit(limit - len(points))
            .all()
        )

        for r in attempt_rows:
            if len(points) >= limit:
                break

            is_explicit_fail = (r.test_status or "").strip().lower() not in ("success", "")
            signal = r.best_rsrp if r.best_rsrp is not None else r.best_rscp

            is_bad_signal = False
            if signal is not None:
                threshold_row = _band_threshold_by_serving_band(db, r.serving_band)
                taux_aff = threshold_row.taux_aff if threshold_row else 0.0
                threshold = threshold_row.tai_threshold if threshold_row else -100.0
                is_bad_signal = (signal + taux_aff) <= threshold

            is_bad = is_explicit_fail or is_bad_signal
            points.append({
                "lat": r.latitude, "lon": r.longitude, "rsrp": signal,
                "operator": r.operator, "technology": r.technology, "logType": "http_attempt",
                "status": "bad" if is_bad else "good",
            })

    return points[:limit]


@router.get("/gouvernorats", response_model=list[GouvernoratOut])
def list_gouvernorats(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Gouvernorat).order_by(Gouvernorat.name).all()


@router.get("/delegations", response_model=list[DelegationOut])
def list_delegations(gouvernorat_id: int = Query(...), db: Session = Depends(get_db),
                      _: User = Depends(get_current_user)):
    return db.query(Delegation).filter_by(gouvernorat_id=gouvernorat_id).order_by(Delegation.name).all()


@router.get("/secteurs", response_model=list[SecteurOut])
def list_secteurs(delegation_id: int = Query(...), db: Session = Depends(get_db),
                   _: User = Depends(get_current_user)):
    return db.query(Secteur).filter_by(delegation_id=delegation_id).order_by(Secteur.name).all()


@router.get("/boundary")
def get_boundary(level: str = Query(..., pattern="^(gouvernorat|delegation|secteur)$"),
                  id: int = Query(...), db: Session = Depends(get_db),
                  _: User = Depends(get_current_user)):
    model_cls = {"gouvernorat": Gouvernorat, "delegation": Delegation, "secteur": Secteur}[level]
    obj = db.query(model_cls).get(id)
    if obj is None or obj.geom is None:
        raise HTTPException(404, "Boundary not found")

    shapely_geom = to_shape(obj.geom)
    return {
        "type": "Feature",
        "properties": {"id": obj.id, "name": obj.name},
        "geometry": mapping(shapely_geom),
    }


@router.get("/delegation-overview", response_model=DelegationOverviewResponse)
def delegation_overview(delegation_id: int = Query(...), db: Session = Depends(get_db),
                         _: User = Depends(get_current_user)):
    delegation = db.query(Delegation).get(delegation_id)
    if delegation is None:
        raise HTTPException(404, "Delegation not found")

    secteur_ids = [row[0] for row in db.query(Secteur.id).filter_by(delegation_id=delegation_id).all()]
    secteurs_with_data = 0
    comparison: list[OperatorComparisonRow] = []
    pcps_values: list[float] = []

    if secteur_ids:
        kpi_rows = db.query(KPIResult).filter(KPIResult.secteur_id.in_(secteur_ids)).all()
        secteurs_with_data = len({r.secteur_id for r in kpi_rows})

        grouped: dict[tuple[str, str | None], dict[str, list[KPIResult]]] = {}
        for row in kpi_rows:
            key = (row.operator, row.technology)
            grouped.setdefault(key, {}).setdefault(row.kpi_name.value, []).append(row)

        def _avg(kpi_rows_for_name: list[KPIResult]) -> float | None:
            vals = [r.value for r in kpi_rows_for_name if r.is_computed == "true" and r.value is not None]
            return round(sum(vals) / len(vals), 2) if vals else None

        for (operator, technology), kpis in grouped.items():
            tao = _avg(kpis.get("TAO", []))
            tai = _avg(kpis.get("TAI", []))
            td = _avg(kpis.get("TD", []))
            pcps = _avg(kpis.get("PCPS", []))

            comparison.append(OperatorComparisonRow(
                operator=operator, technology=technology, tao=tao, tai=tai, td=td, pcps=pcps,
            ))
            if pcps is not None:
                pcps_values.append(pcps)

    overall_rating = round(sum(pcps_values) / len(pcps_values), 2) if pcps_values else None

    return DelegationOverviewResponse(
        delegation_id=delegation.id, delegation_name=delegation.name,
        gouvernorat_name=delegation.gouvernorat.name if delegation.gouvernorat else "",
        secteurs_with_data=secteurs_with_data, overall_rating=overall_rating, comparison=comparison,
    )


@router.get("/location-overview", response_model=LocationOverviewResponse)
def location_overview(secteur_id: int = Query(...), db: Session = Depends(get_db),
                       _: User = Depends(get_current_user)):
    secteur = db.query(Secteur).get(secteur_id)
    if secteur is None:
        raise HTTPException(404, "Secteur not found")

    comparison: list[OperatorComparisonRow] = []
    pcps_values: list[float] = []

    kpi_rows = db.query(KPIResult).filter_by(secteur_id=secteur_id).all()
    grouped: dict[tuple[str, str | None], dict[str, KPIResult]] = {}
    for row in kpi_rows:
        key = (row.operator, row.technology)
        grouped.setdefault(key, {})[row.kpi_name.value] = row

    for (operator, technology), kpis in grouped.items():
        tao = kpis.get("TAO")
        tai = kpis.get("TAI")
        td = kpis.get("TD")
        pcps = kpis.get("PCPS")

        comparison.append(OperatorComparisonRow(
            operator=operator, technology=technology,
            tao=tao.value if tao else None,
            tai=tai.value if tai else None,
            td=td.value if (td and td.is_computed == "true") else None,
            pcps=pcps.value if (pcps and pcps.is_computed == "true") else None,
        ))
        if pcps and pcps.is_computed == "true" and pcps.value is not None:
            pcps_values.append(pcps.value)

    overall_rating = round(sum(pcps_values) / len(pcps_values), 2) if pcps_values else None

    return LocationOverviewResponse(
        secteur_id=secteur.id, secteur_name=secteur.name,
        delegation_name=secteur.delegation_name, gouvernorat_name=secteur.gouvernorat_name,
        overall_rating=overall_rating, comparison=comparison,
    )


@router.get("/map-points")
def map_points(kpi_name: str = Query("PCPS", pattern="^(TAO|TAI|TD|PCPS)$"),
               db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.query(KPIResult, Secteur).join(Secteur, KPIResult.secteur_id == Secteur.id).filter(
        KPIResult.kpi_name == KPIName(kpi_name)
    ).all()

    return [
        {
            "secteur_id": s.id, "secteur_name": s.name, "operator": kr.operator,
            "technology": kr.technology, "value": kr.value, "is_computed": kr.is_computed == "true",
            "lat": s.center_lat, "lon": s.center_lon,
        }
        for kr, s in rows
    ]