"""Phase 3: clean the raw data.

Every step is logged in a cleaning log, so anyone can see exactly what
changed and why. Steps:

1. Rename columns to snake_case (Order Date -> order_date).
2. Trim extra spaces in text columns.
3. Fix postal codes: restore lost leading zeros (5401 -> 05401) and fill
   missing ones from the same city + state where possible.
4. Remove duplicate records (identical in every column except row_id).
5. Add product_key: one key per (product_id, product_name) pair, because
   some Product IDs are shared by different product names.
6. Set final data types.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from salesinsight.logger import get_logger

logger = get_logger(__name__)

TEXT_COLUMNS: list[str] = [
    "order_id", "ship_mode", "customer_id", "customer_name", "segment", "country",
    "city", "state", "postal_code", "region", "product_id", "category",
    "sub_category", "product_name",
]

# Fallback for postal codes that cannot be filled from other rows.
# Burlington, Vermont is blank in some versions of the dataset.
KNOWN_POSTAL_CODES: dict[tuple[str, str], str] = {
    ("Burlington", "Vermont"): "05401",
}


@dataclass
class CleaningStep:
    step: str
    rows_before: int
    rows_after: int
    values_changed: int
    note: str


def to_snake_case(name: str) -> str:
    """'Sub-Category' -> 'sub_category', 'Row ID' -> 'row_id'."""
    return name.strip().lower().replace("-", "_").replace("/", "_").replace(" ", "_")


def standardise_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={c: to_snake_case(c) for c in df.columns})


def strip_text(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Remove spaces at the start/end of text values. Returns (df, values changed)."""
    df = df.copy()
    changed = 0
    for col in TEXT_COLUMNS:
        if col in df.columns:
            before = df[col].astype("string")
            after = before.str.strip()
            changed += int((before != after).fillna(False).sum())
            df[col] = after
    return df, changed


def fix_postal_codes(df: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    """Pad postal codes to 5 digits and fill missing ones.

    Returns (df, codes padded, codes filled).
    """
    df = df.copy()
    codes = df["postal_code"].astype("string").str.replace(r"\.0$", "", regex=True)
    padded = codes.str.zfill(5)
    n_padded = int((codes != padded).fillna(False).sum())

    missing = padded.isna()
    n_filled = 0
    if missing.any():
        known = (
            df.loc[~missing].assign(postal_code=padded[~missing])
            .groupby(["city", "state"])["postal_code"]
            .agg(lambda s: s.mode().iloc[0])
            .to_dict()
        )
        known = {**KNOWN_POSTAL_CODES, **known}
        fills = [known.get((c, s), pd.NA) for c, s in zip(df.loc[missing, "city"], df.loc[missing, "state"])]
        padded.loc[missing] = fills
        n_filled = int(missing.sum() - padded.isna().sum())

    df["postal_code"] = padded
    return df, n_padded, n_filled


def remove_duplicate_records(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Drop rows identical in every column except row_id (keep the first)."""
    cols = [c for c in df.columns if c != "row_id"]
    is_dupe = df.duplicated(subset=cols, keep="first")
    removed = df.loc[is_dupe, "row_id"].tolist()
    if removed:
        logger.info("Removed duplicate rows with row_id: %s", removed)
    return df.loc[~is_dupe].reset_index(drop=True), int(is_dupe.sum())


def add_product_key(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Give each (product_id, product_name) pair its own key, e.g. P00001.

    Returns (df, number of product_ids that needed more than one key).
    """
    df = df.copy()
    numbers = df.groupby(["product_id", "product_name"], sort=True).ngroup() + 1
    df["product_key"] = "P" + numbers.astype(str).str.zfill(5)
    shared_ids = int((df.groupby("product_id")["product_name"].nunique() > 1).sum())
    return df, shared_ids


def set_types(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["row_id"] = df["row_id"].astype("int64")
    df["quantity"] = df["quantity"].astype("int64")
    for col in ("sales", "discount", "profit"):
        df[col] = df[col].astype("float64")
    for col in TEXT_COLUMNS + ["product_key"]:
        if col in df.columns:
            df[col] = df[col].astype("string")
    return df


def clean_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run every cleaning step. Returns (clean DataFrame, cleaning log)."""
    log: list[CleaningStep] = []

    def record(step: str, before: int, after: int, changed: int, note: str) -> None:
        log.append(CleaningStep(step, before, after, changed, note))
        logger.info("%-28s rows %d -> %d, changed %d. %s", step, before, after, changed, note)

    n = len(raw)
    df = standardise_columns(raw)
    record("Standardise column names", n, len(df), df.shape[1], "Column names converted to snake_case")

    df, changed = strip_text(df)
    record("Trim text spaces", n, len(df), changed, "Leading/trailing spaces removed")

    df, padded, filled = fix_postal_codes(df)
    still_missing = int(df["postal_code"].isna().sum())
    record("Fix postal codes", n, len(df), padded + filled,
           f"{padded} padded to 5 digits, {filled} filled, {still_missing} still missing")

    before = len(df)
    df, removed = remove_duplicate_records(df)
    record("Remove duplicate records", before, len(df), removed, f"{removed} duplicate rows removed")

    df, shared = add_product_key(df)
    record("Add product_key", len(df), len(df), df["product_key"].nunique(),
           f"{shared} product_ids are shared by more than one product name")

    df = set_types(df)
    record("Set data types", len(df), len(df), 0, "Integers, decimals, text and dates fixed")

    return df, pd.DataFrame([asdict(s) for s in log])
