"""
Converts raw Lat/Lon columns into geometries and resolves
Gouvernorat / Delegation / Secteur via point-in-polygon join against
ref_secteur (which already carries its own parent names, so a single join
against the finest level resolves the whole hierarchy - no need to join
against ref_gouvernorat/ref_delegation separately).
"""
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.geo import Secteur


def _load_secteur_geodataframe(db: Session) -> gpd.GeoDataFrame:
    """Pulls ref_secteur into a GeoDataFrame once per ingestion batch."""
    rows = db.execute(
        select(Secteur.id, Secteur.name, Secteur.delegation_name,
               Secteur.gouvernorat_name, Secteur.geom)
    ).all()

    if not rows:
        raise RuntimeError(
            "ref_secteur is empty - run `python -m app.scripts.init_geo_reference` "
            "to load the GeoJSON boundaries before ingesting measurement files."
        )

    import shapely.wkb as wkb
    records = []
    for r in rows:
        geom = wkb.loads(bytes(r.geom.data)) if hasattr(r.geom, "data") else wkb.loads(r.geom, hex=True)
        records.append({
            "secteur_id": r.id,
            "secteur_name": r.name,
            "delegation_name": r.delegation_name,
            "gouvernorat_name": r.gouvernorat_name,
            "geometry": geom,
        })

    return gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")


def spatial_join_points(df: pd.DataFrame, db: Session,
                         lat_col: str = "latitude", lon_col: str = "longitude") -> pd.DataFrame:
    """
    Takes a cleaned dataframe with lat_col/lon_col and returns it with
    secteur_id / secteur_name / delegation_name / gouvernorat_name appended.
    Rows that fall outside all known polygons (e.g. bad GPS, offshore points)
    get NaN geo columns - caller decides whether to drop or keep them.
    """
    secteurs_gdf = _load_secteur_geodataframe(db)

    points_gdf = gpd.GeoDataFrame(
        df.copy(),
        geometry=[Point(xy) for xy in zip(df[lon_col], df[lat_col])],
        crs="EPSG:4326",
    )

    joined = gpd.sjoin(points_gdf, secteurs_gdf[["secteur_id", "secteur_name",
                                                   "delegation_name", "gouvernorat_name", "geometry"]],
                        how="left", predicate="within")

    joined = joined.drop(columns=["index_right", "geometry"], errors="ignore")
    return pd.DataFrame(joined)


def majority_secteur_id(df: pd.DataFrame) -> int | None:
    """
    Implements the agreed archiving rule: one raw file -> archived under the
    sector containing the MAJORITY of its points (DB rows still keep their
    own accurate per-row secteur_id regardless of this).
    """
    if "secteur_id" not in df.columns or df["secteur_id"].dropna().empty:
        return None
    return int(df["secteur_id"].value_counts().idxmax())
