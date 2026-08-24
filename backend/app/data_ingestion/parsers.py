"""
Per-log-type parsers. These exist because the raw files are NOT consistent
with each other - the radio team's export tool produces different column
names/sets from export to export (different field selections, different
tool versions, English/French labels, etc).

HTTP attempt files in particular are handled with an ALIAS-BASED approach:
each standardized field (time, latitude, longitude, ...) is matched
independently against a list of known raw-column aliases, instead of
trying to detect one fixed "format" for the whole file. This means any
combination of aliases can appear in a given export and still be parsed
correctly. To support a brand-new column name in the future, add it to
the relevant list in HTTP_ATTEMPT_ALIASES below - no other logic needs
to change.

RSRP and HTTP failure files still use the original rename-map / header-
recovery approach, since only HTTP attempt exports have shown this kind
of variation so far. If they start varying too, the same alias-based
pattern used below can be applied to them.
"""
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

EXPECTED_HTTP_FAILURE_COLUMNS = [
    "Event ID", "event", "Event#", "measurement", "Time", "System", "Serving band",
    "Data transfer address", "Redirect address", "Application protocol",
    "Data transfer security protocol", "Data transfer authentication scheme",
    "Data transfer description", "Status", "Failure cause", "Longitude", "Latitude",
]


# Converts a raw Excel date/time column into a proper timestamp
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

def read_rsrp(file_path: Path, operator: str, technology: str | None) -> pd.DataFrame:
    df = _read_excel_or_csv(file_path)

    # Some scanner exports report 3G and 4G side-by-side in the same file
    # (RSCP/Time_3G/Ch_3G for 3G, RSRP/Time_4G/Ch_4G/PCI/DL BW for 4G)
    # instead of a single "1. best RSRP"/"Time"/"Ch" triplet.
    if "Time_3G" in df.columns and "Time_4G" in df.columns:
        tech = (technology or "").upper()
        shared_cols = [c for c in df.columns if c not in
                       ("RSCP", "Time_3G", "Ch_3G", "SC",
                        "RSRP", "Time_4G", "Ch_4G", "DL BW", "PCI")]

        def build_4g():
            out = df[shared_cols + ["RSRP", "Time_4G", "Ch_4G", "DL BW", "PCI"]].rename(columns={
                "RSRP": "best_rsrp", "Time_4G": "time", "Ch_4G": "channel",
                "DL BW": "dl_bw", "PCI": "pci",
            })
            out["technology"] = "4G"
            return out

        def build_3g():
            out = df[shared_cols + ["RSCP", "Time_3G", "Ch_3G"]].rename(columns={
                "RSCP": "best_rsrp", "Time_3G": "time", "Ch_3G": "channel",
            })
            out["technology"] = "3G"
            return out

        if tech == "4G_3G":
            # Combined upload selection - emit one row set per technology
            # instead of collapsing to a single tech and losing half the data.
            combined = pd.concat([build_4g(), build_3g()], ignore_index=True)
        elif "3G" in tech and "4G" not in tech:
            combined = build_3g()
        else:
            # single "4G" selection (or anything else) defaults to 4G columns
            combined = build_4g()

        combined = combined.rename(columns={"Lon.": "longitude", "Lat.": "latitude"})

        required = {"best_rsrp", "time", "latitude", "longitude"}
        missing = required - set(combined.columns)
        if missing:
            raise ValueError(f"RSRP file missing expected columns after rename: {missing}")
        combined = _coerce_time_column(combined, file_path.name)
        combined["operator"] = operator
        return combined

    # --- original single-technology format (unchanged) ---
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
# ---------------------------------------------------------------------
# Column alias groups for HTTP attempt files.
#
# The radio team's export tool changes column names between exports
# (different field selections, different tool versions, French/English
# labels, etc). Rather than trying to detect a fixed "format", every
# field is matched independently against a list of known aliases. If a
# new export shows up with yet another label for an existing field, add
# it to the relevant list below - no other logic needs to change.
#
# Matching is case-insensitive and ignores leading/trailing whitespace.
# ---------------------------------------------------------------------
HTTP_ATTEMPT_ALIASES: dict[str, list[str]] = {
    "latitude": ["Test start latitude", "Latitude", "Lat.", "Lat"],
    "longitude": ["Test start longitude", "Longitude", "Lon.", "Lon", "Long."],
    "time": ["Test start time", "Time"],
    "test_end_time": ["Test end time"],
    "test_status": ["Test status"],
    "application_protocol": [
        "Test protocol", "Application protocol", "Mode(Application protocol)",
    ],
    "start_system_band_raw": ["Start system and band"],
    "end_system_and_band": ["End system and band"],
    "best_rsrp": ["Avg(1. best RSRP)", "AvgRSRP", "1. best RSRP", "best RSRP"],
    "channel": ["Mode(Ch)", "Ch"],
    "pci": ["Mode(PCI)", "PCI"],
    "event_id": ["Event ID", "Mode(Event ID)"],
    "system": ["System", "Mode(System)"],
    "serving_band": ["Serving band", "Mode(Serving band)"],
    "data_transfer_address": ["Data transfer address", "Mode(IP)"],
    "connection_timeout_raw": [
        "Data transfer connection timeout", "Mode(Connection timeout)",
    ],
    # Identifying columns - used only to cross-check against the upload
    # dropdown and log a warning on mismatch. Never override the dropdown.
    "device_label": ["Device label"],
    "home_operator": ["Home operator"],
    "operator_from_file": ["operateur"],
    "technology_from_file": ["Technologie"],
    # Metadata we don't need downstream.
    "file_name": ["File name"],
}


def _build_alias_rename_map(columns, alias_groups: dict[str, list[str]]) -> dict:
    """Map each raw column name to its canonical target, based on the
    alias lists above. Matching is case-insensitive / whitespace-trimmed.
    """
    lookup = {}
    for canonical, aliases in alias_groups.items():
        for alias in aliases:
            key = alias.strip().lower()
            if key in lookup and lookup[key] != canonical:
                # Two canonical fields claim the same alias - a bug in
                # the alias table above, not in the uploaded file.
                raise ValueError(
                    f"Alias '{alias}' is mapped to both "
                    f"'{lookup[key]}' and '{canonical}' - fix HTTP_ATTEMPT_ALIASES."
                )
            lookup[key] = canonical

    rename = {}
    for col in columns:
        key = str(col).strip().lower()
        if key in lookup:
            rename[col] = lookup[key]
    return rename


def _parse_device_label(value):
    """'ORANGE 4G' -> ('ORANGE', '4G'). Also tolerates a bare operator
    name with no technology, e.g. 'ORANGE' -> ('ORANGE', None)."""
    if pd.isna(value):
        return None, None
    value = str(value).strip()
    if not value:
        return None, None
    parts = value.split(maxsplit=1)
    parsed_operator = parts[0]
    parsed_technology = parts[1].strip() if len(parts) > 1 else None
    return parsed_operator, parsed_technology


def _parse_system_and_band(value):
    """'LTE FDD 1800' -> ('LTE FDD', 'L1800'). Prefixes the frequency
    with L/U/G depending on the detected radio system, matching the
    convention used elsewhere for the `band` field."""
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


def read_http_attempt(
    file_path: Path,
    operator: str,
    technology: str | None
) -> pd.DataFrame:
    """
    Handles any HTTP attempt export the radio team sends, regardless of
    which columns are present, by matching each expected field
    independently against a list of known aliases (HTTP_ATTEMPT_ALIASES)
    instead of trying to detect one fixed "format".

    To support a new export variant in the future: run
    `inspect_columns.py` on the new file, find which of its column
    names aren't yet recognized, and add them to the relevant alias
    list above. No other code needs to change.
    """
    df = _read_excel_or_csv(file_path)
    logger.info("%s: raw columns = %s", file_path.name, list(df.columns))

    rename_map = _build_alias_rename_map(df.columns, HTTP_ATTEMPT_ALIASES)
    df = df.rename(columns=rename_map)
    logger.info("%s: columns after alias rename = %s", file_path.name, list(df.columns))

    # --- Start system and band -> system / serving_band -------------
    # Only derive from the combined text field if we don't already have
    # direct system/serving_band columns from this file's own aliases
    # (e.g. Mode(System) / Mode(Serving band)).
    if "start_system_band_raw" in df.columns:
        if "system" not in df.columns or "serving_band" not in df.columns:
            parsed = df["start_system_band_raw"].apply(_parse_system_and_band)
            if "system" not in df.columns:
                df["system"] = parsed.apply(lambda x: x[0])
            if "serving_band" not in df.columns:
                df["serving_band"] = parsed.apply(lambda x: x[1])
        df = df.drop(columns=["start_system_band_raw"])

    # --- Connection timeout: extract numeric ms -----------------------
    if "connection_timeout_raw" in df.columns:
        df["connection_timeout_ms"] = pd.to_numeric(
            df["connection_timeout_raw"].astype(str).str.extract(r"(\d+(?:\.\d+)?)")[0],
            errors="coerce",
        )
        df = df.drop(columns=["connection_timeout_raw"])

    # --- Cross-check file-reported operator/technology against the ---
    # --- upload dropdown (logging only - dropdown always wins) -------
    reported_operators, reported_technologies = [], []

    if "device_label" in df.columns:
        parsed = df["device_label"].apply(_parse_device_label)
        reported_operators += list(parsed.apply(lambda x: x[0]).dropna().unique())
        reported_technologies += list(parsed.apply(lambda x: x[1]).dropna().unique())
        df = df.drop(columns=["device_label"])

    if "home_operator" in df.columns:
        reported_operators += list(df["home_operator"].dropna().astype(str).unique())
        df = df.drop(columns=["home_operator"])

    if "operator_from_file" in df.columns:
        reported_operators += list(df["operator_from_file"].dropna().astype(str).unique())
        df = df.drop(columns=["operator_from_file"])

    if "technology_from_file" in df.columns:
        reported_technologies += list(df["technology_from_file"].dropna().astype(str).unique())
        df = df.drop(columns=["technology_from_file"])

    if reported_operators and any(v != operator for v in reported_operators):
        logger.warning(
            "%s: file reports operator(s) %s but upload dropdown says %s",
            file_path.name, reported_operators, operator,
        )
    if technology is not None and reported_technologies and any(
        v != technology for v in reported_technologies
    ):
        logger.warning(
            "%s: file reports technology(ies) %s but upload selection says %s",
            file_path.name, reported_technologies, technology,
        )

    if "file_name" in df.columns:
        df = df.drop(columns=["file_name"])

    # --- Required standardized fields ---------------------------------
    required = {"time", "latitude", "longitude"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"{file_path.name}: HTTP attempt file missing expected columns "
            f"after alias matching: {missing}. Raw columns were: "
            f"{list(_read_excel_or_csv(file_path).columns)}"
        )

    # Some raw exports include a couple of near-empty trailing rows past
    # the real data range (stray Excel formatting, blank rows the radio
    # team's tool leaves at the end, etc). Those rows have no time/lat/lon
    # and would otherwise crash the whole upload on the NOT NULL `time`
    # column. Drop only the specific rows missing required data instead
    # of failing the entire file.
    before_count = len(df)
    df = df.dropna(subset=["time", "latitude", "longitude"], how="any")
    dropped_count = before_count - len(df)
    if dropped_count:
        logger.warning(
            "%s: dropped %d row(s) missing time/latitude/longitude "
            "(likely blank trailing rows in the source file)",
            file_path.name, dropped_count,
        )

    df = _coerce_time_column(df, file_path.name, col="time")
    if "test_end_time" in df.columns:
        df = _coerce_time_column(df, file_path.name, col="test_end_time")

    # Upload-time dropdown values remain the source of truth.
    df["operator"] = operator
    df["technology"] = technology

    return df


def read_http_failure(file_path: Path, operator: str, technology: str | None) -> pd.DataFrame:
    """
    Defends against the malformed-header case observed in
    HTTP_FAILURE_TT4G_3G.xlsx, where the file's single data row was read as
    the header (0 data rows resulted). If the detected header doesn't look
    like a real header (e.g. contains a raw float timestamp instead of the
    word 'Time'), we re-read with header=None and apply the known column
    order positionally instead.
    """
    df = pd.read_excel(file_path)

    header_looks_valid = "Time" in df.columns or any(
        isinstance(c, str) and c.strip().lower() == "time" for c in df.columns
    )

    if not header_looks_valid:
        logger.warning(
            "%s: header row not detected (columns=%s) - re-reading positionally, "
            "ADMIN SHOULD VERIFY this file's header row against a known-good export "
            "like http_failure_TT4G.xlsx",
            file_path.name, list(df.columns),
        )
        df = pd.read_excel(file_path, header=None)
        if len(df.columns) != len(EXPECTED_HTTP_FAILURE_COLUMNS):
            raise ValueError(
                f"{file_path.name}: column count {len(df.columns)} doesn't match the "
                f"expected {len(EXPECTED_HTTP_FAILURE_COLUMNS)} for an http_failure file - "
                "cannot safely recover columns positionally. Please re-export with headers."
            )
        df.columns = EXPECTED_HTTP_FAILURE_COLUMNS

        # Headerless reads lose the cell's datetime formatting, so a genuine
        # timestamp can come back as a raw Excel serial number (e.g. 46223.487
        # instead of a Timestamp). Detect and convert.
        time_col = df["Time"]
        if pd.api.types.is_numeric_dtype(time_col):
            logger.warning(
                "%s: 'Time' column recovered as raw Excel serial number - converting "
                "via origin=1899-12-30. Verify this against the source file if precision matters.",
                file_path.name,
            )
            df["Time"] = pd.to_datetime(time_col, unit="D", origin="1899-12-30")

    df = df.rename(columns={
        "Event ID": "event_id",
        "event": "event_label",
        "Event#": "event_number",
        "measurement": "measurement",
        "Time": "time",
        "System": "system",
        "Serving band": "serving_band",
        "Data transfer address": "data_transfer_address",
        "Redirect address": "redirect_address",
        "Application protocol": "application_protocol",
        "Status": "status",
        "Failure cause": "failure_cause",
        "Longitude": "longitude",
        "Latitude": "latitude",
        "technologie": "technology_from_file",
        "operateur": "operator_from_file",
    })

    required = {"time", "latitude", "longitude"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"HTTP failure file missing expected columns after rename: {missing}")
    df = _coerce_time_column(df, file_path.name)

    for extra in ("operator_from_file", "technology_from_file"):
        if extra in df.columns:
            df = df.drop(columns=[extra])

    df["operator"] = operator
    df["technology"] = technology
    return df


PARSERS = {
    "rsrp": read_rsrp,
    "http_attempt": read_http_attempt,
    "http_failure": read_http_failure,
}


def parse_uploaded_file(file_path: Path, log_type: str, operator: str,
                         technology: str | None) -> pd.DataFrame:
    if log_type not in PARSERS:
        raise ValueError(f"Unknown log_type '{log_type}', expected one of {list(PARSERS)}")
    return PARSERS[log_type](file_path, operator, technology)

