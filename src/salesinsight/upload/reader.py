"""Read an uploaded CSV or Excel file safely (in memory only)."""

from __future__ import annotations

import csv
import io

import pandas as pd

MAX_FILE_MB = 20
MAX_ROWS = 200_000
MAX_COLUMNS = 150
CSV_TYPES = (".csv", ".txt")
EXCEL_TYPES = (".xlsx", ".xlsm")
ALLOWED_TYPES = CSV_TYPES + EXCEL_TYPES


class UploadError(ValueError):
    """A problem with the uploaded file, explained in plain words."""


def _extension(name: str) -> str:
    name = name.lower().strip()
    return name[name.rfind("."):] if "." in name else ""


def _check_size(name: str, data: bytes) -> None:
    if _extension(name) not in ALLOWED_TYPES:
        raise UploadError("Please upload a CSV file (.csv) or an Excel file (.xlsx). "
                          "Older .xls files: open them in Excel and save as .xlsx.")
    if not data:
        raise UploadError("The file is empty.")
    if len(data) > MAX_FILE_MB * 1024 * 1024:
        raise UploadError(f"The file is {len(data) / 1024 / 1024:.1f} MB. The limit is {MAX_FILE_MB} MB - "
                          "remove columns you do not need or split the file by year.")


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UploadError("The file's text encoding could not be read. Save it as 'CSV UTF-8' and try again.")


def _read_csv(data: bytes) -> pd.DataFrame:
    text = _decode(data)
    sample = text[:20_000]
    try:
        sep = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        sep = ","
    try:
        return pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False,
                           skipinitialspace=True, nrows=MAX_ROWS + 1)
    except Exception as exc:  # noqa: BLE001
        raise UploadError(f"The CSV file could not be read ({exc}).") from exc


def excel_sheets(data: bytes) -> list[str]:
    """Sheet names of an Excel file (so the user can pick one)."""
    try:
        return pd.ExcelFile(io.BytesIO(data), engine="openpyxl").sheet_names
    except Exception as exc:  # noqa: BLE001
        raise UploadError("The Excel file could not be opened. Is it password-protected or damaged?") from exc


def _read_excel(data: bytes, sheet: str | int | None) -> pd.DataFrame:
    try:
        df = pd.read_excel(io.BytesIO(data), sheet_name=sheet if sheet is not None else 0,
                           engine="openpyxl", nrows=MAX_ROWS + 1)
    except Exception as exc:  # noqa: BLE001
        raise UploadError("The Excel file could not be read. Is it password-protected or damaged?") from exc
    # Keep real dates as dates; everything else as text, like the CSV path.
    for col in df.columns:
        if not pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].map(lambda v: "" if pd.isna(v) else str(v))
    return df


def read_upload(name: str, data: bytes, sheet: str | int | None = None) -> pd.DataFrame:
    """Read the file into a DataFrame (all columns as text, except Excel dates).

    Raises UploadError with a message a non-technical user can act on.
    """
    _check_size(name, data)
    df = _read_excel(data, sheet) if _extension(name) in EXCEL_TYPES else _read_csv(data)

    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, [c for c in df.columns if c and not c.lower().startswith("unnamed")]
                or list(df.columns)]
    if df.shape[1] > MAX_COLUMNS:
        raise UploadError(f"The file has {df.shape[1]} columns; the limit is {MAX_COLUMNS}.")
    if len(df) > MAX_ROWS:
        raise UploadError(f"The file has more than {MAX_ROWS:,} rows. Please upload a smaller period "
                          "(for example one or two years).")
    # Drop rows that are completely empty (common at the end of Excel sheets).
    blank = pd.concat([df[c].isna() | (df[c].astype(str).str.strip() == "") for c in df.columns],
                      axis=1).all(axis=1)
    df = df.loc[~blank].reset_index(drop=True)
    if df.empty or df.shape[1] < 2:
        raise UploadError("No data found. The first row should hold the column names and the rows below "
                          "the sales records.")
    # pandas renames a repeated header "Amount" to "Amount.1" - treat that as a duplicate name.
    names = set(df.columns)
    dupes = sorted({c.rsplit(".", 1)[0] for c in df.columns
                    if "." in c and c.rsplit(".", 1)[1].isdigit() and c.rsplit(".", 1)[0] in names})
    if dupes:
        raise UploadError(f"Two columns have the same name: {', '.join(map(str, dupes))}. "
                          "Please rename one of them.")
    return df
