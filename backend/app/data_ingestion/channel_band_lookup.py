"""
Resolves each row's `channel` (RSRP.xlsx's 'Ch' column, or the new HTTP
attempt file's 'Mode(Ch)' column) to a real `band` via
ChannelBandMapping(operator, channel). Band lookup is intentionally
independent of the upload-time `technology` field - technology is NOT
derived here (per requirement: "do not derive the technology per row via
the channel lookup table").

If a channel isn't found in the mapping table for that operator, the row
keeps band=None (kept, not dropped - per agreed behavior) and is excluded
from TAI's band-based pass/fail evaluation (see kpi_engine/tai.py).
"""
import pandas as pd
from sqlalchemy.orm import Session

from app.models.config_models import ChannelBandMapping


def attach_band_column(df: pd.DataFrame, operator: str, db: Session) -> pd.DataFrame:
    """Adds a `band` column, looked up per-row by `channel`. No-ops (sets
    band=None for every row) if the dataframe has no `channel` column at
    all - e.g. an older-format HTTP attempt file without embedded RSRP."""
    if "channel" not in df.columns:
        df["band"] = None
        return df

    rows = db.query(ChannelBandMapping.channel, ChannelBandMapping.band).filter(
        ChannelBandMapping.operator == operator
    ).all()
    channel_to_band = {r.channel: r.band for r in rows}

    df["band"] = df["channel"].map(
        lambda ch: channel_to_band.get(int(ch)) if pd.notnull(ch) else None
    )
    return df
