"""
Per-log-type parsers.

CHANGED (this revision): both combined-format parsers now emit UP TO TWO
rows per source row - one for the 4G reading, one for the 3G reading -
instead of one row carrying both. A technology's row is only emitted when
that technology's reading is actually present:
  - SCANNER_OR.xlsx: 4G row requires non-null RSRP, 3G row requires non-null RSCP.
  - HTTP_OR.xlsx:     4G row requires non-null AvgRSRP, 3G row requires non-null AvgRSCP.
`technology` is therefore set per emitted row ("4G"/"3G"), not passed
through from the upload dropdown, since a single source row can produce
rows of both technologies.

http_attempt supports ONLY the unified "Home operator" export format
(e.g. HTTP_OR.xlsx). Every older variant this parser used to handle - OLD
format, "Previous revised" format, the "Device label" variant, and the
separate http_failure file format - has been removed, since the Home
operator export is the single source of both Pass and Fail HTTP rows
(via test_status).

RSRP keeps both formats it already supported:
  - single-technology RSRP.xlsx ('Lon.'/'Lat.'/'1. best RSRP'/etc.) - one
    row per source row, technology comes from the upload dropdown as before.
  - combined 3G+4G scanner export (SCANNER_OR.xlsx) - see read_rsrp.

Every parser returns a dataframe with STANDARDIZED column names ready for
preprocessing/cleaning.py + spatial_mapping/spatial_join.py, regardless of
which raw shape came in.
"""
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def _coerce_time_column(df: pd.DataFrame, source_name: str, col: str = "time") -> pd.DataFrame:
    if col not in df.columns:
        return df
    if pd.api.types.is_numeric_dtype(df[col]):
        logger.warning(
            "%s: '%s' column read as a raw Excel serial number - converting via origin=1899-12-30.",
            source_name, col,
        )
        df[col] = pd.to_datetime(df[col], unit="D", origin="1899-12-30")
    else:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _read_excel_or_csv(file_path: Path) -> pd.DataFrame:
    if file_path.suffix.lower() == ".csv":
        return pd.read_csv(file_path)
    return pd.read_excel(file_path)


# Columns that mark a combined 3G+4G scanner export (SCANNER_OR.xlsx), as
# opposed to the single-technology RSRP format.
_COMBINED_SCANNER_MARKER_COLS = {"RSCP", "Time_3G", "Ch_3G", "SC", "RSRP", "Time_4G", "Ch_4G"}


def read_rsrp(file_path: Path, operator: str, technology: str | None) -> pd.DataFrame:
    df = _read_excel_or_csv(file_path)

    # ============================================================
    # COMBINED 3G+4G SCANNER FORMAT (e.g. SCANNER_OR.xlsx)
    # ============================================================
    # One source row holds both a 4G reading (RSRP) and a 3G reading
    # (RSCP) at (roughly) the same location. Split into up to two output
    # rows - a technology's row is skipped when its reading is null,
    # since a null RSRP/RSCP means that scan simply didn't get a reading
    # for that technology at that point.
    if _COMBINED_SCANNER_MARKER_COLS.issubset(df.columns):
        logger.info("%s: detected combined 3G+4G scanner format", file_path.name)

        df = df.rename(columns={"Lon.": "longitude", "Lat.": "latitude"})

        # --- 4G row ----------------------------------------------------
        rsrp_present = df["RSRP"].notna()
        rows_4g = df.loc[rsrp_present, ["longitude", "latitude", "RSRP", "Time_4G", "Ch_4G", "DL BW", "PCI"]].rename(
            columns={"RSRP": "best_rsrp", "Time_4G": "time", "Ch_4G": "channel", "DL BW": "dl_bw", "PCI": "pci"}
        )
        rows_4g["technology"] = "4G"

        # --- 3G row ------------------------------------------------------
        # No dedicated 3G columns on test_rsrp - the 3G reading goes into
        # the SAME time/channel/best_rsrp columns the 4G row uses, same
        # convention as the single-technology format below: those columns
        # hold "the reading" for whatever `technology` this row is.
        # There's no column for SC (scrambling code) at all, so it's
        # simply not persisted.
        rscp_present = df["RSCP"].notna()
        rows_3g = df.loc[rscp_present, ["longitude", "latitude", "RSCP", "Time_3G", "Ch_3G"]].rename(
            columns={"RSCP": "best_rsrp", "Time_3G": "time", "Ch_3G": "channel"}
        )
        rows_3g["technology"] = "3G"
        rows_3g["dl_bw"] = None
        rows_3g["pci"] = None

        combined = pd.concat([rows_4g, rows_3g], ignore_index=True)
        combined = _coerce_time_column(combined, file_path.name, col="time")
        combined["operator"] = operator
        return combined

    # ============================================================
    # SINGLE-TECHNOLOGY RSRP FORMAT
    # ============================================================
    df = df.rename(columns={
        "1. best RSRP": "best_rsrp",
        "Time": "time",
        "Ch": "channel",
        "DL BW": "dl_bw",
        "PCI": "pci",
        "Lon.": "longitude",
        "Lat.": "latitude",
        "to_interval": "to_interval",
    })

    required = {"best_rsrp", "time", "latitude", "longitude"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"RSRP file missing expected columns after rename: {missing}")
    df = _coerce_time_column(df, file_path.name)
    df["operator"] = operator
    df["technology"] = technology
    return df


def _parse_system_and_band(value):
    """'LTE FDD 1800' -> system='LTE FDD', serving_band='L1800'."""
    if pd.isna(value):
        return None, None

    value = str(value).strip()
    if not value:
        return None, None

    parts = value.rsplit(maxsplit=1)
    if len(parts) == 1:
        return parts[0], None

    system = parts[0].strip()
    frequency = parts[1].strip()
    system_upper = system.upper()

    if "LTE" in system_upper:
        serving_band = f"L{frequency}"
    elif "UMTS" in system_upper:
        serving_band = f"U{frequency}"
    elif "GSM" in system_upper:
        serving_band = f"G{frequency}"
    else:
        serving_band = frequency

    return system, serving_band


def read_http_attempt(
    file_path: Path,
    operator: str,
    technology: str | None
) -> pd.DataFrame:
    """
    Supports ONLY the unified "Home operator" export format:

        File name
        Home operator
        Test status
        Test protocol
        Test start time
        Test end time
        Test start latitude
        Test start longitude
        Start system and band
        AvgRSRP
        AvgRSCP

    This file carries both Success and Fail rows via Test status - there
    is no separate http_failure format anymore.

    Each source row can carry a 4G reading (AvgRSRP), a 3G reading
    (AvgRSCP), or both - same as the SCANNER_OR format. Split into up to
    two output rows accordingly, skipping a technology when its reading
    is null. Unlike test_rsrp, test_http_attempt already has separate
    best_rsrp/best_rscp columns, so no value duplication is needed here -
    each emitted row just nulls out whichever field doesn't apply to it.
    """
    df = _read_excel_or_csv(file_path)

    if "Home operator" not in df.columns:
        raise ValueError(
            f"{file_path.name}: expected the 'Home operator' HTTP attempt "
            f"format (columns found: {list(df.columns)}). Older formats "
            f"(Device label, OLD/REVISED) are no longer supported."
        )

    logger.info("%s: detected Home operator HTTP attempt format", file_path.name)

    # Kept only for the mismatch-warning check below - the upload dropdown
    # remains the actual source of truth for operator.
    file_operators = df["Home operator"].dropna().astype(str).unique()
    if len(file_operators) and any(v != operator for v in file_operators):
        logger.warning(
            "File %s reports operator(s) %s but upload dropdown says %s",
            file_path.name, list(file_operators), operator,
        )

    df = df.rename(columns={
        "Test status": "test_status",
        "Test protocol": "application_protocol",
        "Test start time": "time",
        "Test end time": "test_end_time",
        "Test start latitude": "latitude",
        "Test start longitude": "longitude",
        "AvgRSRP": "best_rsrp",
        "AvgRSCP": "best_rscp",
    })

    parsed_system = df["Start system and band"].apply(_parse_system_and_band)
    df["system"] = parsed_system.apply(lambda x: x[0])
    df["serving_band"] = parsed_system.apply(lambda x: x[1])

    df = df.drop(columns=["File name", "Home operator", "Start system and band"], errors="ignore")

    required = {"time", "latitude", "longitude"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"HTTP attempt file missing expected columns after parsing: {missing}")

    df = _coerce_time_column(df, file_path.name, col="time")
    df = _coerce_time_column(df, file_path.name, col="test_end_time")

    # The Home operator format has no explicit duration column - compute
    # it from the two timestamps instead of leaving it null. NaT on
    # either side (e.g. a Fail row with no end time) -> NaN, which
    # becomes NULL at insert time same as any other missing value.
    df["download_duration_seconds"] = (
        (df["test_end_time"] - df["time"]).dt.total_seconds()
    )

    df["operator"] = operator

    # --- split into up to two rows: one 4G, one 3G --------------------
    rsrp_present = df["best_rsrp"].notna()
    rscp_present = df["best_rscp"].notna()

    rows_4g = df.loc[rsrp_present].copy()
    rows_4g["technology"] = "4G"
    rows_4g["best_rscp"] = None

    rows_3g = df.loc[rscp_present].copy()
    rows_3g["technology"] = "3G"
    rows_3g["best_rsrp"] = None

    return pd.concat([rows_4g, rows_3g], ignore_index=True)


PARSERS = {
    "rsrp": read_rsrp,
    "http_attempt": read_http_attempt,
}


def parse_uploaded_file(file_path: Path, log_type: str, operator: str,
                         technology: str | None) -> pd.DataFrame:
    if log_type not in PARSERS:
        raise ValueError(f"Unknown log_type '{log_type}', expected one of {list(PARSERS)}")
    return PARSERS[log_type](file_path, operator, technology)