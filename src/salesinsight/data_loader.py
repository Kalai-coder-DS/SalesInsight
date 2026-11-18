"""Load the raw Superstore CSV into a pandas DataFrame with correct types.

What this module does:
1. Checks that the file exists and is a real file (not a folder).
2. Reads it with the right text encoding (the Kaggle file is not UTF-8).
3. Makes column names consistent between different Kaggle versions.
4. Keeps ID and postal-code columns as text (so leading zeros are not lost).
5. Converts "Order Date" and "Ship Date" from text to real dates.

It does NOT change or remove any rows. Cleaning happens in Phase 3.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from salesinsight import config
from salesinsight.logger import get_logger

logger = get_logger(__name__)

# The 21 columns we expect, in the original order.
EXPECTED_COLUMNS: list[str] = [
    "Row ID", "Order ID", "Order Date", "Ship Date", "Ship Mode",
    "Customer ID", "Customer Name", "Segment", "Country", "City",
    "State", "Postal Code", "Region", "Product ID", "Category",
    "Sub-Category", "Product Name", "Sales", "Quantity", "Discount", "Profit",
]

# Some Kaggle versions use different names for the same column.
COLUMN_ALIASES: dict[str, str] = {
    "Country/Region": "Country",
    "Sub Category": "Sub-Category",
    "Row Id": "Row ID",
}

DATE_COLUMNS: list[str] = ["Order Date", "Ship Date"]

# Columns that look like numbers but are really labels -> keep as text.
TEXT_COLUMNS: list[str] = ["Order ID", "Customer ID", "Product ID", "Postal Code"]

# Date formats to try, most likely first (US data is month/day/year).
DATE_FORMATS: tuple[str, ...] = ("%m/%d/%Y", "%d/%m/%Y", "%d-%m-%Y", "%m-%d-%Y", "%Y-%m-%d")


def parse_date_column(series: pd.Series, column_name: str = "date") -> pd.Series:
    """Convert a text column to dates by trying each known format.

    The format that parses the most values wins. Values that cannot be
    parsed become NaT (missing date) and are reported by validation.
    """
    text = series.astype("string").str.strip()
    best_parsed: pd.Series | None = None
    best_failures = len(series) + 1
    best_format = ""

    for fmt in DATE_FORMATS:
        parsed = pd.to_datetime(text, format=fmt, errors="coerce")
        failures = int((parsed.isna() & text.notna()).sum())
        if failures < best_failures:
            best_parsed, best_failures, best_format = parsed, failures, fmt
        if failures == 0:
            break

    logger.info("Parsed '%s' with format %s (%d values could not be parsed)",
                column_name, best_format, best_failures)
    return best_parsed


def load_raw_data(
    path: Path | str = config.RAW_DATA_FILE,
    encoding: str = config.RAW_DATA_ENCODING,
) -> pd.DataFrame:
    """Read the raw Superstore CSV and return a typed DataFrame.

    Raises:
        FileNotFoundError: the file does not exist.
        IsADirectoryError: the path is a folder, not a file.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Data file not found: {path}\n"
            "Download the Superstore dataset and save it as data/raw/Superstore.csv"
        )
    if path.is_dir():
        raise IsADirectoryError(
            f"{path} is a folder, not a file. Delete the folder and copy the real CSV file there."
        )

    logger.info("Reading %s", path)
    df = pd.read_csv(path, encoding=encoding, dtype={col: str for col in TEXT_COLUMNS})

    # Make column names consistent.
    df.columns = df.columns.str.strip()
    df = df.rename(columns=COLUMN_ALIASES)
    # Postal Code may have been renamed by the alias step; force text again.
    for col in TEXT_COLUMNS:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()

    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = parse_date_column(df[col], col)

    logger.info("Loaded %d rows x %d columns", df.shape[0], df.shape[1])
    return df


def summarise(df: pd.DataFrame) -> dict[str, object]:
    """Return a few headline numbers used as a quick sanity check."""
    summary: dict[str, object] = {"rows": len(df), "columns": df.shape[1]}
    if "Order Date" in df.columns:
        summary["first_order_date"] = df["Order Date"].min()
        summary["last_order_date"] = df["Order Date"].max()
    for col in ("Order ID", "Customer ID", "Product ID"):
        if col in df.columns:
            summary[f"unique_{col.lower().replace(' ', '_')}s"] = df[col].nunique()
    for col in ("Sales", "Profit"):
        if col in df.columns:
            summary[f"total_{col.lower()}"] = round(float(df[col].sum()), 2)
    return summary


# Columns of the processed file that must stay as text when read back.
CLEAN_TEXT_COLUMNS: list[str] = ["order_id", "customer_id", "product_id", "postal_code", "product_key"]
CLEAN_DATE_COLUMNS: list[str] = ["order_date", "ship_date"]


def load_clean_data(path: Path | str = config.CLEAN_DATA_FILE) -> pd.DataFrame:
    """Read the cleaned file created in Phase 3 (data/processed/sales_clean.csv).

    All later phases (SQL, KPIs, trends, ...) start from this function.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            f"Clean data not found: {path}\nRun first:  python scripts/run_cleaning.py"
        )
    df = pd.read_csv(
        path,
        dtype={col: str for col in CLEAN_TEXT_COLUMNS},
        parse_dates=CLEAN_DATE_COLUMNS,
    )
    logger.info("Loaded clean data: %d rows x %d columns", df.shape[0], df.shape[1])
    return df
