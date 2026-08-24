"""
One-time (idempotent) loader that populates ref_gouvernorat / ref_delegation /
ref_secteur from the provided GeoJSON files.

Confirmed source structure (see project notes):
  tun_admin2.geojson -> 24 features  -> Gouvernorat (property 'adm2_name')
  tun_admin3.geojson -> 264 features -> Delegation  (property 'adm3_name', parent 'adm2_name')
  tun_admin4.geojson -> 2084 features -> Secteur    (property 'adm4_name', parents 'adm3_name'/'adm2_name')

We only need to actually read tun_admin4.geojson for the Secteur table since
every admin4 feature already carries its parent adm3_name/adm2_name - but we
also load admin2/admin3 separately to get their own (coarser) polygons for
the map highlighting feature (a Governorate click needs the Governorate's
own outline, not the union of its sectors).

Run via: python -m app.scripts.init_geo_reference
"""
import json
import logging
from pathlib import Path

from shapely.geometry import shape, MultiPolygon
from geoalchemy2.shape import from_shape
from sqlalchemy.orm import Session

from app.models.geo import Gouvernorat, Delegation, Secteur

logger = logging.getLogger(__name__)


def _to_multipolygon(geom):
    """
    Admin boundary files sometimes mix Polygon and MultiPolygon geometries
    for the same admin level (confirmed: tun_admin4.geojson does this, even
    though admin2/admin3 happen to be consistently MultiPolygon). All geo.py
    columns are declared MULTIPOLYGON, so normalize here rather than at the
    DB level - avoids a per-row "Geometry type does not match column type"
    insert failure.
    """
    if geom.geom_type == "Polygon":
        return MultiPolygon([geom])
    return geom  # already MultiPolygon (or something else - let it fail loudly if so)


def _load_features(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["features"]


def load_gouvernorats(db: Session, geojson_path: Path) -> dict[str, Gouvernorat]:
    """Loads tun_admin2.geojson. Returns {pcode: Gouvernorat} for reuse by delegations loader."""
    features = _load_features(geojson_path)
    pcode_map: dict[str, Gouvernorat] = {}

    for feat in features:
        props = feat["properties"]
        pcode = props["adm2_pcode"]

        existing = db.query(Gouvernorat).filter_by(pcode=pcode).one_or_none()
        geom = from_shape(_to_multipolygon(shape(feat["geometry"])), srid=4326)

        if existing:
            existing.name = props["adm2_name"]
            existing.geom = geom
            pcode_map[pcode] = existing
        else:
            gov = Gouvernorat(pcode=pcode, name=props["adm2_name"], geom=geom)
            db.add(gov)
            db.flush()  # get gov.id
            pcode_map[pcode] = gov

    db.commit()
    logger.info("Loaded %d gouvernorats", len(pcode_map))
    return pcode_map


def load_delegations(db: Session, geojson_path: Path,
                      gouvernorat_by_pcode: dict[str, Gouvernorat]) -> dict[str, Delegation]:
    """Loads tun_admin3.geojson. Returns {pcode: Delegation}."""
    features = _load_features(geojson_path)
    pcode_map: dict[str, Delegation] = {}

    for feat in features:
        props = feat["properties"]
        pcode = props["adm3_pcode"]
        parent_gov = gouvernorat_by_pcode.get(props["adm2_pcode"])
        if parent_gov is None:
            logger.warning("Delegation %s references unknown gouvernorat %s",
                            pcode, props["adm2_pcode"])
            continue

        existing = db.query(Delegation).filter_by(pcode=pcode).one_or_none()
        geom = from_shape(_to_multipolygon(shape(feat["geometry"])), srid=4326)

        if existing:
            existing.name = props["adm3_name"]
            existing.gouvernorat_id = parent_gov.id
            existing.geom = geom
            pcode_map[pcode] = existing
        else:
            deleg = Delegation(pcode=pcode, name=props["adm3_name"],
                                gouvernorat_id=parent_gov.id, geom=geom)
            db.add(deleg)
            db.flush()
            pcode_map[pcode] = deleg

    db.commit()
    logger.info("Loaded %d delegations", len(pcode_map))
    return pcode_map


def load_secteurs(db: Session, geojson_path: Path,
                   delegation_by_pcode: dict[str, Delegation]) -> int:
    """Loads tun_admin4.geojson -> ref_secteur (the level the KPI/archiving/spatial join operate on)."""
    features = _load_features(geojson_path)
    count = 0

    for feat in features:
        props = feat["properties"]
        pcode = props["adm4_pcode"]
        parent_deleg = delegation_by_pcode.get(props["adm3_pcode"])
        if parent_deleg is None:
            logger.warning("Secteur %s references unknown delegation %s",
                            pcode, props["adm3_pcode"])
            continue

        existing = db.query(Secteur).filter_by(pcode=pcode).one_or_none()
        geom = from_shape(_to_multipolygon(shape(feat["geometry"])), srid=4326)

        fields = dict(
            name=props["adm4_name"],
            delegation_id=parent_deleg.id,
            gouvernorat_name=props["adm2_name"],
            delegation_name=props["adm3_name"],
            center_lat=props.get("center_lat"),
            center_lon=props.get("center_lon"),
            geom=geom,
        )

        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(Secteur(pcode=pcode, **fields))
        count += 1

    db.commit()
    logger.info("Loaded %d secteurs", count)
    return count


def load_all_geo_reference(db: Session, admin2_path: Path, admin3_path: Path, admin4_path: Path):
    govs = load_gouvernorats(db, admin2_path)
    delegs = load_delegations(db, admin3_path, govs)
    load_secteurs(db, admin4_path, delegs)
