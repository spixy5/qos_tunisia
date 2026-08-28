"""
Per-log-type parsers.

RSRP (SCANNER_TT.xlsx and equivalents): each source row holds a 4G
reading (RSRP, always present) and a 3G reading (RSCP, nullable - a
meaningful fraction of rows have no 3G fix at that instant). Split into
UP TO TWO output rows - one per technology - since test_rsrp has single
(non-suffixed) time/channel/best_rsrp columns rather than separate _4g/
_3g columns: a source row can't be represented as one test_rsrp row
without losing one technology's reading. GPS (Lat./Lon.) is captured
alongside the 3G reading only (confirmed against real data: null in
exactly the same rows RSCP is null) - the 4G row for one of those source
rows will have no GPS at all, which is why latitude/longitude are
nullable on test_rsrp.

HTTP (HTTP_TT.xlsx and equivalents): every attempt - success or failure -
in one file, distinguished by "Test status". test_http_attempt already
has separate best_rsrp/best_rscp columns, so no split is needed here -
one file row = one output row.
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


# ---------------------------------------------------------------------
# RSRP: combined 3G+4G scanner export (SCANNER_TT.xlsx and equivalents).
# Columns: RSCP, Time_3G, Ch_3G, SC, Lon., Lat., RSRP, Time_4G, Ch_4G,
# DL BW, PCI. Output columns match test_rsrp exactly - `band` is NOT set
# here, it's filled downstream by attach_band_column() from `channel`.
# ---------------------------------------------------------------------
RSRP_OUTPUT_COLUMNS = [
    "time", "best_rsrp", "channel", "dl_bw", "pci", "rscp", "sc",
    "latitude", "longitude",
]


def read_rsrp(file_path: Path, operator: str, technology: str | None) -> pd.DataFrame:
    """
    Parses the official combined 3G+4G scanner export and splits each
    source row into up to two test_rsrp rows: a 4G row (from RSRP/Time_4G/
    Ch_4G/DL BW/PCI) and a 3G row (from RSCP/Time_3G/Ch_3G/SC), emitted
    independently and only when that technology's reading is present.
    """
    df = _read_excel_or_csv(file_path)
    logger.info("%s: raw columns = %s", file_path.name, list(df.columns))

    required_raw = {"RSRP", "Time_4G", "RSCP", "Time_3G", "Lon.", "Lat."}
    missing = required_raw - set(df.columns)
    if missing:
        raise ValueError(
            f"{file_path.name}: RSRP file missing expected columns: {missing}. "
            f"Raw columns were: {list(df.columns)}"
        )

    df = df.rename(columns={"Lon.": "longitude", "Lat.": "latitude"})

    # --- 4G row: one per source row with a valid RSRP reading -----------
    rsrp_present = df["RSRP"].notna()
    rows_4g = df.loc[rsrp_present, ["longitude", "latitude", "RSRP", "Time_4G", "Ch_4G", "DL BW", "PCI"]].rename(
        columns={"RSRP": "best_rsrp", "Time_4G": "time", "Ch_4G": "channel", "DL BW": "dl_bw", "PCI": "pci"}
    )
    rows_4g["technology"] = "4G"
    rows_4g["rscp"] = None
    rows_4g["sc"] = None

    # --- 3G row: only when this source row has a 3G fix ------------------
    # best_rsrp is NOT NULL on test_rsrp and there's no separate "3G
    # reading" column beyond rscp (which just duplicates the value for
    # anything querying it by that name directly) - the RSCP value goes
    # into best_rsrp for this row, same convention as the 4G row: those
    # generic columns hold "the reading" for whatever `technology` the
    # row is.
    rscp_present = df["RSCP"].notna()
    rows_3g = df.loc[rscp_present, ["longitude", "latitude", "RSCP", "Time_3G", "Ch_3G", "SC"]].rename(
        columns={"RSCP": "best_rsrp", "Time_3G": "time", "Ch_3G": "channel", "SC": "sc"}
    )
    rows_3g["technology"] = "3G"
    rows_3g["dl_bw"] = None
    rows_3g["pci"] = None
    rows_3g["rscp"] = rows_3g["best_rsrp"]

    combined = pd.concat([rows_4g, rows_3g], ignore_index=True)
    combined = _coerce_time_column(combined, file_path.name, col="time")

    for col in RSRP_OUTPUT_COLUMNS:
        if col not in combined.columns:
            combined[col] = None
    combined = combined[RSRP_OUTPUT_COLUMNS + ["technology"]].copy()

    combined["operator"] = operator
    return combined


# ---------------------------------------------------------------------
# HTTP: official "Home operator" export (HTTP_TT.xlsx and equivalents).
# ---------------------------------------------------------------------
HTTP_ALIASES: dict[str, list[str]] = {
    "test_start_time": ["Test start time"],
    "test_end_time": ["Test end time"],
    "test_status": ["Test status"],
    "application_protocol": ["Test protocol"],
    "latitude": ["Test start latitude"],
    "longitude": ["Test start longitude"],
    "start_system_band_raw": ["Start system and band"],
    "best_rsrp": ["AvgRSRP"],
    "best_rscp": ["AvgRSCP"],
    # Cross-check only against the upload dropdown - never stored.
    "home_operator": ["Home operator"],
    # Metadata we don't need downstream.
    "file_name": ["File name"],
}

OUTPUT_COLUMNS = [
    "test_start_time", "test_end_time",
    "system", "serving_band", "application_protocol", "test_status",
    "best_rsrp", "best_rscp", "download_duration_seconds",
    "latitude", "longitude",
]


def _build_alias_rename_map(columns, alias_groups: dict[str, list[str]]) -> dict:
    lookup = {}
    for canonical, aliases in alias_groups.items():
        for alias in aliases:
            key = alias.strip().lower()
            if key in lookup and lookup[key] != canonical:
                raise ValueError(
                    f"Alias '{alias}' is mapped to both "
                    f"'{lookup[key]}' and '{canonical}' - fix HTTP_ALIASES."
                )
            lookup[key] = canonical

    rename = {}
    for col in columns:
        key = str(col).strip().lower()
        if key in lookup:
            rename[col] = lookup[key]
    return rename


def _parse_system_and_band(value):
    """'LTE FDD 1800' -> ('LTE FDD', 'L1800')."""
    if pd.isna(value):
        return None, None
    value = str(value).strip()
    if not value:
        return None, None
    parts = value.rsplit(maxsplit=1)
    if len(parts) == 1:
        return parts[0], None
    system, frequency = parts[0].strip(), parts[1].strip()
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


def _normalize_status(value):
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered.startswith("succ"):
        return "Success"
    if lowered.startswith("fail"):
        return "Failure"
    return text.title()


def read_http(file_path: Path, operator: str, technology: str | None) -> pd.DataFrame:
    """
    Parses the official HTTP export format. Every row - success or
    failure - is returned in the same DataFrame, distinguished by
    `test_status`. No row splitting: test_http_attempt already has
    separate best_rsrp/best_rscp columns.
    """
    df = _read_excel_or_csv(file_path)
    logger.info("%s: raw columns = %s", file_path.name, list(df.columns))

    rename_map = _build_alias_rename_map(df.columns, HTTP_ALIASES)
    df = df.rename(columns=rename_map)
    logger.info("%s: columns after alias rename = %s", file_path.name, list(df.columns))

    if "test_status" in df.columns:
        df["test_status"] = df["test_status"].apply(_normalize_status)
    else:
        logger.warning(
            "%s: no 'Test status' column found - defaulting test_status to 'Unknown'.",
            file_path.name,
        )
        df["test_status"] = "Unknown"

    if "start_system_band_raw" in df.columns:
        parsed = df["start_system_band_raw"].apply(_parse_system_and_band)
        df["system"] = parsed.apply(lambda x: x[0])
        df["serving_band"] = parsed.apply(lambda x: x[1])
    else:
        df["system"] = None
        df["serving_band"] = None

    if "home_operator" in df.columns:
        reported = list(df["home_operator"].dropna().astype(str).unique())
        if reported and any(v != operator for v in reported):
            logger.warning(
                "%s: file reports operator(s) %s but upload dropdown says %s",
                file_path.name, reported, operator,
            )

    required = {"test_start_time", "latitude", "longitude"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"{file_path.name}: HTTP file missing expected columns "
            f"after alias matching: {missing}. Raw columns were: "
            f"{list(_read_excel_or_csv(file_path).columns)}"
        )

    before_count = len(df)
    df = df.dropna(subset=["test_start_time", "latitude", "longitude"], how="any")
    dropped_count = before_count - len(df)
    if dropped_count:
        logger.warning(
            "%s: dropped %d row(s) missing test_start_time/latitude/longitude "
            "(likely blank trailing rows in the source file)",
            file_path.name, dropped_count,
        )

    df = _coerce_time_column(df, file_path.name, col="test_start_time")
    if "test_end_time" in df.columns:
        df = _coerce_time_column(df, file_path.name, col="test_end_time")

    if "test_end_time" in df.columns:
        df["download_duration_seconds"] = (
            df["test_end_time"] - df["test_start_time"]
        ).dt.total_seconds()
    else:
        df["download_duration_seconds"] = None

    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df = df[OUTPUT_COLUMNS].copy()

    df["operator"] = operator
    df["technology"] = technology

    return df


PARSERS = {
    "rsrp": read_rsrp,
    "http_attempt": read_http,

}


def parse_uploaded_file(file_path: Path, log_type: str, operator: str,
                         technology: str | None) -> pd.DataFrame:
    if log_type not in PARSERS:
        raise ValueError(f"Unknown log_type '{log_type}', expected one of {list(PARSERS)}")
    return PARSERS[log_type](file_path, operator, technology)