"""
Automated cleaning pipeline, triggered on every upload before the spatial
join runs. Deliberately generic (works on any of the 3 log types) since it
only touches lat/lon + generic duplicate rules - the per-type column
renaming happens in data_ingestion/parsers.py BEFORE this runs, so by the
time we get here every dataframe already has standardized `latitude` /
`longitude` columns.
"""
import logging
import pandas as pd

logger = logging.getLogger(__name__)


def clean_dataframe(df: pd.DataFrame, lat_col: str = "latitude",
                     lon_col: str = "longitude") -> tuple[pd.DataFrame, dict]:
    """
    Returns (cleaned_df, stats) where stats reports what was dropped, so the
    ingestion endpoint can surface it to the Admin (row_count_raw vs
    row_count_clean on UploadedFile).
    """
    stats = {"raw_rows": len(df)}

    # 1. Drop exact duplicates
    before = len(df)
    df = df.drop_duplicates()
    stats["duplicates_dropped"] = before - len(df)

    # 2. Drop rows with null/invalid GPS
    before = len(df)
    df = df.dropna(subset=[lat_col, lon_col])
    df = df[
        df[lat_col].apply(lambda v: isinstance(v, (int, float)) and -90 <= v <= 90) &
        df[lon_col].apply(lambda v: isinstance(v, (int, float)) and -180 <= v <= 180)
    ]
    stats["invalid_gps_dropped"] = before - len(df)

    # 3. Tunisia bounding-box sanity filter (catches obviously wrong points,
    #    e.g. a swapped lat/lon that still passes the -90/-180 range check)
    before = len(df)
    df = df[(df[lat_col].between(30.0, 38.0)) & (df[lon_col].between(7.0, 12.0))]
    stats["out_of_tunisia_bbox_dropped"] = before - len(df)

    stats["clean_rows"] = len(df)
    logger.info("Cleaning stats: %s", stats)
    return df.reset_index(drop=True), stats
