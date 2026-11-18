"""Data-quality checks for the raw Superstore data.

Each check returns a ValidationResult with a status:
    PASS - no problem found
    WARN - something unusual that we will handle or explain in Phase 3
    FAIL - a serious problem; the data should not be used until it is fixed

Validation never changes the data. It only reports.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from salesinsight.data_loader import EXPECTED_COLUMNS
from salesinsight.logger import get_logger

logger = get_logger(__name__)

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"

# Allowed values for the categorical columns.
ALLOWED_VALUES: dict[str, set[str]] = {
    "Region": {"Central", "East", "South", "West"},
    "Category": {"Furniture", "Office Supplies", "Technology"},
    "Segment": {"Consumer", "Corporate", "Home Office"},
    "Ship Mode": {"First Class", "Same Day", "Second Class", "Standard Class"},
}

# Columns that must never be empty.
KEY_COLUMNS: list[str] = [
    "Row ID", "Order ID", "Order Date", "Ship Date", "Customer ID",
    "Product ID", "Category", "Region", "Sales", "Quantity", "Discount", "Profit",
]

# Plain-English meaning of each column (used for the data dictionary).
COLUMN_DESCRIPTIONS: dict[str, str] = {
    "Row ID": "Unique number for each row (one product line in an order)",
    "Order ID": "Order identifier; one order can contain several products (rows)",
    "Order Date": "Date the order was placed",
    "Ship Date": "Date the order was shipped",
    "Ship Mode": "Shipping class chosen by the customer",
    "Customer ID": "Unique customer identifier",
    "Customer Name": "Customer's name",
    "Segment": "Customer type: Consumer, Corporate or Home Office",
    "Country": "Country of delivery (United States only)",
    "City": "City of delivery",
    "State": "US state of delivery",
    "Postal Code": "ZIP code of delivery (kept as text to keep leading zeros)",
    "Region": "US sales region: Central, East, South or West",
    "Product ID": "Product identifier",
    "Category": "Product category: Furniture, Office Supplies or Technology",
    "Sub-Category": "Product sub-category, e.g. Chairs, Phones, Binders",
    "Product Name": "Full product name",
    "Sales": "Revenue for the row in USD, after discount",
    "Quantity": "Number of units sold",
    "Discount": "Discount given as a fraction (0.2 = 20%)",
    "Profit": "Profit for the row in USD (negative = loss)",
}


@dataclass
class ValidationResult:
    check: str
    status: str
    affected_rows: int
    details: str


def _result(check: str, bad_count: int, details: str, fail_level: str = FAIL) -> ValidationResult:
    status = PASS if bad_count == 0 else fail_level
    return ValidationResult(check, status, int(bad_count), details if bad_count else "OK")


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------
def check_required_columns(df: pd.DataFrame) -> ValidationResult:
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    extra = [c for c in df.columns if c not in EXPECTED_COLUMNS]
    details = f"Missing: {missing}" if missing else ""
    if extra:
        details += f" Extra (ignored): {extra}"
    result = _result("Required columns present", len(missing), details.strip())
    if not missing and extra:
        result.status, result.details = WARN, details.strip()
    return result


def check_not_empty(df: pd.DataFrame) -> ValidationResult:
    return _result("Dataset has rows", int(len(df) == 0), "The file has no data rows")


def check_missing_key_values(df: pd.DataFrame) -> ValidationResult:
    cols = [c for c in KEY_COLUMNS if c in df.columns]
    missing = df[cols].isna().sum()
    missing = missing[missing > 0]
    rows = int(df[cols].isna().any(axis=1).sum())
    return _result("No missing values in key columns", rows, f"Missing per column: {missing.to_dict()}")


def check_missing_other_values(df: pd.DataFrame) -> ValidationResult:
    cols = [c for c in df.columns if c not in KEY_COLUMNS]
    missing = df[cols].isna().sum()
    missing = missing[missing > 0]
    rows = int(df[cols].isna().any(axis=1).sum())
    return _result("Missing values in other columns", rows, f"Missing per column: {missing.to_dict()}", WARN)


def check_duplicate_row_ids(df: pd.DataFrame) -> ValidationResult:
    if "Row ID" not in df.columns:
        return ValidationResult("Row ID is unique", FAIL, 0, "Column 'Row ID' missing")
    dupes = int(df["Row ID"].duplicated().sum())
    return _result("Row ID is unique", dupes, f"{dupes} repeated Row IDs")


def check_duplicate_records(df: pd.DataFrame) -> ValidationResult:
    """Rows identical in every column except Row ID (possible double entry)."""
    cols = [c for c in df.columns if c != "Row ID"]
    dupes = df[df.duplicated(subset=cols, keep=False)]
    extra_copies = int(df.duplicated(subset=cols).sum())
    ids = dupes["Row ID"].tolist()[:10] if "Row ID" in dupes else []
    return _result("No duplicate records (ignoring Row ID)", extra_copies,
                   f"{extra_copies} extra copies; Row IDs involved: {ids}", WARN)


def check_dates_parsed(df: pd.DataFrame) -> ValidationResult:
    bad = 0
    notes = []
    for col in ("Order Date", "Ship Date"):
        if col not in df.columns:
            continue
        if not pd.api.types.is_datetime64_any_dtype(df[col]):
            return ValidationResult("Dates are valid", FAIL, len(df), f"'{col}' is not a date column")
        n = int(df[col].isna().sum())
        bad += n
        if n:
            notes.append(f"{col}: {n} unreadable")
    return _result("Dates are valid", bad, "; ".join(notes))


def check_ship_after_order(df: pd.DataFrame) -> ValidationResult:
    bad = int((df["Ship Date"] < df["Order Date"]).sum())
    return _result("Ship Date is on or after Order Date", bad, f"{bad} rows shipped before they were ordered")


def check_sales_positive(df: pd.DataFrame) -> ValidationResult:
    bad = int((df["Sales"] <= 0).sum())
    return _result("Sales is greater than 0", bad, f"{bad} rows with zero or negative Sales")


def check_quantity_valid(df: pd.DataFrame) -> ValidationResult:
    q = df["Quantity"]
    bad = int(((q <= 0) | (q != q.round())).sum())
    return _result("Quantity is a positive whole number", bad, f"{bad} rows with invalid Quantity")


def check_discount_range(df: pd.DataFrame) -> ValidationResult:
    bad = int(((df["Discount"] < 0) | (df["Discount"] >= 1)).sum())
    return _result("Discount is between 0 and 1", bad, f"{bad} rows outside [0, 1)")


def check_profit_not_above_sales(df: pd.DataFrame) -> ValidationResult:
    bad = int((df["Profit"] > df["Sales"]).sum())
    return _result("Profit is not greater than Sales", bad, f"{bad} rows where Profit > Sales")


def check_allowed_values(df: pd.DataFrame) -> list[ValidationResult]:
    results = []
    for col, allowed in ALLOWED_VALUES.items():
        if col not in df.columns:
            continue
        unexpected = sorted(set(df[col].dropna().unique()) - allowed)
        bad = int(df[col].isin(unexpected).sum())
        results.append(_result(f"'{col}' has only known values", bad, f"Unexpected values: {unexpected}"))
    return results


def check_order_consistency(df: pd.DataFrame) -> ValidationResult:
    """Every row of one order should share the same customer and order date."""
    per_order = df.groupby("Order ID").agg(
        customers=("Customer ID", "nunique"), dates=("Order Date", "nunique")
    )
    bad_orders = per_order[(per_order["customers"] > 1) | (per_order["dates"] > 1)]
    return _result("Each order has one customer and one date", len(bad_orders),
                   f"{len(bad_orders)} inconsistent orders, e.g. {bad_orders.index[:5].tolist()}", WARN)


def check_product_id_names(df: pd.DataFrame) -> ValidationResult:
    """A Product ID should map to one Product Name (a known quirk in this dataset)."""
    names = df.groupby("Product ID")["Product Name"].nunique()
    bad = names[names > 1]
    return _result("Each Product ID has one Product Name", len(bad),
                   f"{len(bad)} Product IDs have more than one name, e.g. {bad.index[:5].tolist()}", WARN)


def check_customer_id_names(df: pd.DataFrame) -> ValidationResult:
    names = df.groupby("Customer ID")["Customer Name"].nunique()
    bad = names[names > 1]
    return _result("Each Customer ID has one Customer Name", len(bad),
                   f"{len(bad)} Customer IDs have more than one name", WARN)


# ---------------------------------------------------------------------------
# Run everything
# ---------------------------------------------------------------------------
def run_all_checks(df: pd.DataFrame) -> list[ValidationResult]:
    """Run every check. Stops early only if required columns are missing."""
    results = [check_required_columns(df), check_not_empty(df)]
    if any(r.status == FAIL for r in results):
        return results

    results += [
        check_missing_key_values(df),
        check_missing_other_values(df),
        check_duplicate_row_ids(df),
        check_duplicate_records(df),
        check_dates_parsed(df),
        check_ship_after_order(df),
        check_sales_positive(df),
        check_quantity_valid(df),
        check_discount_range(df),
        check_profit_not_above_sales(df),
        *check_allowed_values(df),
        check_order_consistency(df),
        check_product_id_names(df),
        check_customer_id_names(df),
    ]
    for r in results:
        log = logger.error if r.status == FAIL else logger.warning if r.status == WARN else logger.info
        log("[%s] %s - %s", r.status, r.check, r.details)
    return results


def results_to_frame(results: list[ValidationResult]) -> pd.DataFrame:
    return pd.DataFrame([asdict(r) for r in results])


def has_failures(results: list[ValidationResult]) -> bool:
    return any(r.status == FAIL for r in results)


def build_data_dictionary(df: pd.DataFrame) -> pd.DataFrame:
    """One row per column: type, missing count, unique count, example, meaning."""
    rows = []
    for col in df.columns:
        series = df[col]
        non_null = series.dropna()
        rows.append({
            "column": col,
            "dtype": str(series.dtype),
            "non_null": int(series.notna().sum()),
            "missing": int(series.isna().sum()),
            "unique_values": int(series.nunique()),
            "example": str(non_null.iloc[0]) if len(non_null) else "",
            "min": str(non_null.min()) if pd.api.types.is_numeric_dtype(series)
                   or pd.api.types.is_datetime64_any_dtype(series) else "",
            "max": str(non_null.max()) if pd.api.types.is_numeric_dtype(series)
                   or pd.api.types.is_datetime64_any_dtype(series) else "",
            "description": COLUMN_DESCRIPTIONS.get(col, ""),
        })
    return pd.DataFrame(rows)
