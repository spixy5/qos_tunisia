"""
Per-log-type parsers. These exist because the raw files are NOT consistent
with each other - the radio team's export tool produces different column
names/sets from export to export (different field selections, different
tool versions, English/French labels, etc).

HTTP files are handled with an ALIAS-BASED approach: each standardized
field (time, latitude, longitude, status, ...) is matched independently
against a list of known raw-column aliases, instead of trying to detect
one fixed "format" for the whole file. This means any combination of
aliases can appear in a given export and still be parsed correctly. To
support a brand-new column name in the future, add it to the relevant
list in HTTP_ALIASES below - no other logic needs to change.

NOTE (2026-08): the radio team's export tool now produces ONE http file
containing both successful and failed tests, distinguished by a
"Test status" column (values: "Success" / "Failure"), instead of two
separate exports. `read_http()` (formerly `read_http_attempt` +
`read_http_failure`) handles both shapes: old-style attempt-only files
(no failure-specific columns), old-style failure-only files (the
malformed-header case), and the new unified file. Downstream, all rows
- success and failure - are written to a single `test_http_attempt`
table with a `status` column; there is no more per-outcome table split.

RSRP files still use the original rename-map / header-recovery approach,
since only HTTP exports have shown this kind of variation so far. If
they start varying too, the same alias-based pattern used below can be
applied to them.
"""
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Column order used only as a last-resort positional fallback when a
# file's header row failed to parse (see _recover_headerless_http below).
# This is the superset of columns seen in old-style http_failure exports.
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
# Column alias groups for HTTP files (attempt / success / failure - all
# now come from the same export shape, distinguished only by the
# "test_status" value).
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
HTTP_ALIASES: dict[str, list[str]] = {
    "latitude": ["Test start latitude", "Latitude", "Lat.", "Lat"],
    "longitude": ["Test start longitude", "Longitude", "Lon.", "Lon", "Long."],
    "time": ["Test start time", "Time"],
    "test_end_time": ["Test end time"],
    # Success/Failure outcome of the test. Was implicit in which file you
    # uploaded (http_success.xlsx vs http_failure.xlsx); now it's an
    # explicit column ("Test status") in a single combined export. The old
    # failure-only export also had a "Status" column meaning the same thing.
    # Canonical name matches the existing `test_status` column on
    # test_http_attempt - no translation layer needed at load time.
    "test_status": ["Test status", "Status"],
    "application_protocol": [
        "Test protocol", "Application protocol", "Mode(Application protocol)",
    ],
    "start_system_band_raw": ["Start system and band"],
    "end_system_and_band": ["End system and band"],
    "best_rsrp": ["Avg(1. best RSRP)", "AvgRSRP", "1. best RSRP", "best RSRP"],
    "best_rscp": ["AvgRSCP", "Avg(RSCP)", "RSCP"],
    "channel": ["Mode(Ch)", "Ch"],
    "pci": ["Mode(PCI)", "PCI"],
    "event_id": ["Event ID", "Mode(Event ID)"],
    "event_label": ["event"],
    "event_number": ["Event#"],
    "measurement": ["measurement"],
    "system": ["System", "Mode(System)"],
    "serving_band": ["Serving band", "Mode(Serving band)"],
    "data_transfer_address": ["Data transfer address", "Mode(IP)"],
    "redirect_address": ["Redirect address"],
    "data_transfer_security_protocol": ["Data transfer security protocol"],
    "data_transfer_authentication_scheme": ["Data transfer authentication scheme"],
    "data_transfer_description": ["Data transfer description"],
    "failure_cause": ["Failure cause"],
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
                    f"'{lookup[key]}' and '{canonical}' - fix HTTP_ALIASES."
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


def _normalize_status(value):
    """'success' / 'SUCCESS' / ' Success ' -> 'Success'; same for Failure.
    Anything else is passed through title-cased so odd values are still
    visible in the DB rather than silently dropped."""
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


def _recover_headerless_http(file_path: Path, df: pd.DataFrame) -> pd.DataFrame:
    """
    Defends against the malformed-header case observed in
    HTTP_FAILURE_TT4G_3G.xlsx, where the file's single data row was read as
    the header (0 data rows resulted). If the detected header doesn't look
    like a real header (e.g. contains a raw float timestamp instead of a
    recognizable column name), we re-read with header=None and apply the
    known column order positionally instead.
    """
    header_looks_valid = any(
        isinstance(c, str) and c.strip().lower() in ("time", "test start time")
        for c in df.columns
    )
    if header_looks_valid:
        return df

    logger.warning(
        "%s: header row not detected (columns=%s) - re-reading positionally, "
        "ADMIN SHOULD VERIFY this file's header row against a known-good export.",
        file_path.name, list(df.columns),
    )
    df = pd.read_excel(file_path, header=None)
    if len(df.columns) != len(EXPECTED_HTTP_FAILURE_COLUMNS):
        raise ValueError(
            f"{file_path.name}: column count {len(df.columns)} doesn't match the "
            f"expected {len(EXPECTED_HTTP_FAILURE_COLUMNS)} for a headerless recovery - "
            "cannot safely recover columns positionally. Please re-export with headers."
        )
    df.columns = EXPECTED_HTTP_FAILURE_COLUMNS
    return df


def read_http(
    file_path: Path,
    operator: str,
    technology: str | None
) -> pd.DataFrame:
    """
    Handles any HTTP export the radio team sends - attempts, successes,
    and failures all included in the same file and distinguished by the
    "status" field - regardless of which columns are present, by matching
    each expected field independently against a list of known aliases
    (HTTP_ALIASES) instead of trying to detect one fixed "format".

    Every row (success or failure) is returned in a single DataFrame with
    a `status` column ("Success" / "Failure" / whatever the file reported,
    title-cased). There is no more splitting into separate success/failure
    outputs - both are written to the same `test_http_attempt` table.

    To support a new export variant in the future: run
    `inspect_columns.py` on the new file, find which of its column
    names aren't yet recognized, and add them to the relevant alias
    list above. No other code needs to change.
    """
    df = _read_excel_or_csv(file_path)
    logger.info("%s: raw columns = %s", file_path.name, list(df.columns))

    df = _recover_headerless_http(file_path, df)
    if pd.api.types.is_numeric_dtype(df.get("Time", pd.Series(dtype=object))):
        # Headerless recovery can leave Time as a raw Excel serial number.
        logger.warning(
            "%s: 'Time' column recovered as raw Excel serial number - will convert "
            "via origin=1899-12-30 below. Verify against the source file if precision matters.",
            file_path.name,
        )

    rename_map = _build_alias_rename_map(df.columns, HTTP_ALIASES)
    df = df.rename(columns=rename_map)
    logger.info("%s: columns after alias rename = %s", file_path.name, list(df.columns))

    # --- Test status -> normalized status -----------------------------
    if "test_status" in df.columns:
        df["test_status"] = df["test_status"].apply(_normalize_status)
    else:
        logger.warning(
            "%s: no 'Test status'/'Status' column found - defaulting test_status to "
            "'Unknown'. This file predates the unified success/failure export; verify "
            "it's not an old attempt-only export missing outcome info.",
            file_path.name,
        )
        df["test_status"] = "Unknown"

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
            f"{file_path.name}: HTTP file missing expected columns "
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


# Backward-compatible aliases: old code/log_types calling read_http_attempt
# or read_http_failure now get the same unified parser. Remove these once
# all callers have moved to log_type="http".
read_http_attempt = read_http
read_http_failure = read_http


PARSERS = {
    "rsrp": read_rsrp,
    "http": read_http,
    # Deprecated log_types kept temporarily so in-flight uploads / saved
    # dropdown selections don't break during rollout. Both now route to
    # the same unified parser and both success and failure rows land in
    # the same test_http_attempt table (see migration).
    "http_attempt": read_http,
    "http_failure": read_http,
}


def parse_uploaded_file(file_path: Path, log_type: str, operator: str,
                         technology: str | None) -> pd.DataFrame:
    if log_type not in PARSERS:
        raise ValueError(f"Unknown log_type '{log_type}', expected one of {list(PARSERS)}")
    return PARSERS[log_type](file_path, operator, technology)