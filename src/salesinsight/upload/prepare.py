"""Apply the user's column mapping, clean and validate the data.

The output has the same 35 columns as the cleaned Superstore data, so the
existing analysis code can run on it. Fields the file does not have are filled
with neutral values (NaN for numbers, "Unknown" for text), and `capabilities`
lists what the data really supports, so the app can hide charts that would be
meaningless (e.g. profit charts without profit or cost data).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from salesinsight.features import add_discount_band
from salesinsight.geo import STATE_CODES
from salesinsight.upload.parsing import (MISSING_TEXT, detect_currency, parse_dates, parse_number,
                                         parse_percent)
from salesinsight.upload.schema import BY_KEY, SALES_ALTERNATIVE

UNKNOWN = "Unknown"
MIN_VALID_SHARE = 0.5          # below this the mapping is probably wrong
SMALL_DATA_ROWS = 30

# Same column order as data/processed/sales_clean.csv
OUTPUT_COLUMNS = [
    "row_id", "order_id", "order_date", "ship_date", "ship_mode", "customer_id", "customer_name", "segment",
    "country", "city", "state", "postal_code", "region", "product_id", "category", "sub_category",
    "product_name", "sales", "quantity", "discount", "profit", "product_key", "order_year", "order_quarter",
    "order_month", "order_month_name", "year_month", "order_weekday", "ship_days", "profit_margin",
    "unit_price", "gross_sales", "discount_amount", "is_loss", "discount_band",
]
TEXT_FIELDS = ["ship_mode", "customer_name", "segment", "country", "city", "state", "region", "category",
               "sub_category", "product_name"]

# Capability -> what the app can show with it
CAPABILITY_LABELS = {
    "orders": "Orders and average order value",
    "customers": "Customer analysis (repeat buyers, RFM, top customers)",
    "products": "Product rankings and Pareto",
    "quantity": "Units sold",
    "profit": "Profit, margin and loss analysis",
    "discount": "Discount analysis",
    "category": "Categories",
    "sub_category": "Sub-categories",
    "region": "Regions",
    "state": "States",
    "us_map": "US map",
    "city": "Cities",
    "segment": "Customer segments",
    "shipping": "Shipping times",
}


@dataclass
class Message:
    level: str        # "error", "warning", "fixed", "info"
    text: str


@dataclass
class PrepResult:
    data: pd.DataFrame | None
    messages: list[Message] = field(default_factory=list)
    capabilities: set[str] = field(default_factory=set)
    rows_in: int = 0
    rows_out: int = 0
    date_order: str = "other"
    currency: str | None = None
    duplicates: int = 0

    @property
    def ok(self) -> bool:
        return self.data is not None and not any(m.level == "error" for m in self.messages)

    def add(self, level: str, text: str) -> None:
        self.messages.append(Message(level, text))

    def report(self) -> pd.DataFrame:
        return pd.DataFrame([vars(m) for m in self.messages], columns=["level", "text"])


def check_mapping(mapping: dict[str, str | None], columns) -> list[str]:
    """Problems with the mapping itself (before any data is touched)."""
    problems = []
    cols = set(columns)
    chosen = {k: v for k, v in mapping.items() if v}
    for key, col in chosen.items():
        if key not in BY_KEY:
            problems.append(f"Unknown field: {key}")
        elif col not in cols:
            problems.append(f"Column '{col}' (for {BY_KEY[key].label}) is not in the file.")
    used: dict[str, list[str]] = {}
    for key, col in chosen.items():
        used.setdefault(col, []).append(BY_KEY[key].label if key in BY_KEY else key)
    for col, labels in used.items():
        if len(labels) > 1:
            problems.append(f"Column '{col}' is chosen for more than one field ({', '.join(labels)}).")
    if not chosen.get("order_date"):
        problems.append("Choose the column that holds the order date.")
    if not chosen.get("sales") and not all(chosen.get(k) for k in SALES_ALTERNATIVE):
        problems.append("Choose the sales amount column (or both unit price and quantity, "
                        "so sales can be calculated).")
    return problems


def _text(series: pd.Series) -> pd.Series:
    """Trim and tidy text; empty or 'N/A'-style values become 'Unknown' (vectorised)."""
    codes, uniques = pd.factorize(series, use_na_sentinel=True)   # clean each distinct value once
    u = pd.Series(uniques, dtype=object).astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
    u = u.where(~u.str.lower().isin(MISSING_TEXT), UNKNOWN)
    cleaned = np.append(u.to_numpy(dtype=object), UNKNOWN)       # code -1 (missing) -> last item
    return pd.Series(cleaned[codes], index=series.index, dtype=object).astype(str)


def _plural(n: int, word: str) -> str:
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def prepare_sales(raw: pd.DataFrame, mapping: dict[str, str | None], dayfirst: bool | None = None,
                  remove_duplicates: bool = False) -> PrepResult:
    """Clean and validate an uploaded file. Never raises for data problems:
    they are returned as messages (level "error" stops the analysis)."""
    result = PrepResult(data=None, rows_in=len(raw))
    for problem in check_mapping(mapping, raw.columns):
        result.add("error", problem)
    if result.messages:
        return result

    m = {k: v for k, v in mapping.items() if v}
    df = pd.DataFrame(index=raw.index)

    # --- Dates ---------------------------------------------------------------------------
    df["order_date"], result.date_order = parse_dates(raw[m["order_date"]], dayfirst)
    bad_dates = int(df["order_date"].isna().sum())
    if bad_dates > MIN_VALID_SHARE * len(df):
        result.add("error", f"Most values in '{m['order_date']}' are not dates. Check the order date column.")
        return result
    if result.date_order == "ambiguous":
        chosen = "day/month/year" if dayfirst in (None, True) else "month/day/year"
        result.add("warning", f"Dates like 05/03/2024 can be read two ways; they were read as {chosen}. "
                              "Change this if the months look wrong.")
    elif result.date_order in ("day-first", "month-first"):
        result.add("info", f"Dates were read as {'day/month/year' if result.date_order == 'day-first' else 'month/day/year'}.")

    if "ship_date" in m:
        df["ship_date"], _ = parse_dates(raw[m["ship_date"]], dayfirst if dayfirst is not None
                                         else result.date_order != "month-first")
    else:
        df["ship_date"] = pd.NaT

    # --- Money and numbers ---------------------------------------------------------------
    quantity = parse_number(raw[m["quantity"]]) if "quantity" in m else pd.Series(np.nan, index=raw.index)
    if "sales" in m:
        df["sales"] = parse_number(raw[m["sales"]])
        result.currency = detect_currency(raw[m["sales"]])
    else:
        price = parse_number(raw[m["unit_price"]])
        df["sales"] = price * quantity
        result.currency = detect_currency(raw[m["unit_price"]])
        result.add("fixed", "Sales were calculated as unit price x quantity.")
    bad_sales = int(df["sales"].isna().sum())
    if bad_sales > MIN_VALID_SHARE * len(df):
        result.add("error", "Most sales values are not numbers. Check the sales amount column.")
        return result

    df["quantity"] = quantity
    if "profit" in m:
        df["profit"] = parse_number(raw[m["profit"]])
    elif "cost" in m:
        df["profit"] = df["sales"] - parse_number(raw[m["cost"]])
        result.add("fixed", "Profit was calculated as sales minus cost.")
    else:
        df["profit"] = np.nan

    if "discount" in m:
        disc = parse_percent(raw[m["discount"]])
        missing_disc = int(disc.isna().sum())
        outside = int(((disc < 0) | (disc >= 1)).sum())
        disc = disc.where((disc >= 0) & (disc < 1))
        if missing_disc:
            result.add("fixed", f"{_plural(missing_disc, 'empty discount')} set to 0.")
        if outside:
            result.add("warning", f"{_plural(outside, 'discount')} outside 0-99% set to 0.")
        df["discount"] = disc.fillna(0.0)
    else:
        df["discount"] = 0.0

    # --- Remove rows that cannot be analysed ---------------------------------------------
    keep = df["order_date"].notna() & df["sales"].notna()
    if bad_dates:
        result.add("fixed", f"{_plural(bad_dates, 'row')} without a valid order date removed.")
    no_sales = int((df["order_date"].notna() & df["sales"].isna()).sum())
    if no_sales:
        result.add("fixed", f"{_plural(no_sales, 'row')} without a valid sales amount removed.")
    df, raw = df.loc[keep].copy(), raw.loc[keep]
    if df.empty:
        result.add("error", "No rows are left after removing rows without a date or sales amount.")
        return result

    # --- IDs and text ----------------------------------------------------------------------
    for key in TEXT_FIELDS:
        df[key] = _text(raw[m[key]]) if key in m else UNKNOWN
    for key in ("order_id", "customer_id", "product_id"):
        df[key] = _text(raw[m[key]]) if key in m else None
    if "order_id" not in m:
        df["order_id"] = [f"LINE-{i + 1}" for i in range(len(df))]
        result.add("info", "No order ID column: each row is counted as one order.")
    if "customer_id" not in m:
        df["customer_id"] = df["customer_name"]
    if "customer_name" not in m and "customer_id" in m:
        df["customer_name"] = df["customer_id"]
    if "product_id" not in m:
        df["product_id"] = df["product_name"]
    if "product_name" not in m and "product_id" in m:
        df["product_name"] = df["product_id"]
    df["product_key"] = np.where(df["product_id"] == df["product_name"], df["product_name"],
                                 df["product_id"] + " | " + df["product_name"])
    df["postal_code"] = ""

    # --- Quality checks (reported, data kept) -----------------------------------------------
    dup_cols = [c for c in ["order_id", "order_date", "customer_id", "product_key", "sales", "quantity"]
                if c in df]
    duplicated = df.duplicated(subset=dup_cols, keep="first") if "order_id" in m else \
        pd.Series(False, index=df.index)
    result.duplicates = int(duplicated.sum())
    if result.duplicates:
        if remove_duplicates:
            df = df.loc[~duplicated]
            result.add("fixed", f"{_plural(result.duplicates, 'duplicate row')} removed.")
        else:
            verb = "looks" if result.duplicates == 1 else "look"
            result.add("warning", f"{_plural(result.duplicates, 'row')} {verb} like an exact duplicate "
                                  "(same order, product and amount); kept in the data - remove if "
                                  "they were entered twice.")
    negative = int((df["sales"] < 0).sum())
    if negative:
        result.add("info", f"{_plural(negative, 'row')} with negative sales kept (treated as returns or refunds).")
    if "quantity" in m:
        bad_q = int(df["quantity"].isna().sum())
        if bad_q:
            result.add("warning", f"{_plural(bad_q, 'quantity')} could not be read; those rows count no units.")
    if "profit" in m or "cost" in m:
        bad_p = int(df["profit"].isna().sum())
        if bad_p:
            result.add("warning", f"{_plural(bad_p, 'profit value')} could not be read and count as missing.")
    future = int((df["order_date"] > pd.Timestamp.now().normalize() + pd.Timedelta(days=1)).sum())
    if future:
        result.add("warning", f"{_plural(future, 'order date')} in the future - check the date format.")
    if "ship_date" in m:
        early = int((df["ship_date"] < df["order_date"]).sum())
        if early:
            result.add("warning", f"{_plural(early, 'ship date')} before the order date.")

    # --- Features (same columns as the Superstore data) ---------------------------------------
    df = time_features(df)
    df["ship_days"] = (df["ship_date"] - df["order_date"]).dt.days.astype("Int64")
    with np.errstate(divide="ignore", invalid="ignore"):
        df["profit_margin"] = np.where(df["sales"] != 0, df["profit"] / df["sales"], np.nan)
        df["unit_price"] = np.where(df["quantity"] > 0, df["sales"] / df["quantity"], np.nan)
        df["gross_sales"] = df["sales"] / (1 - df["discount"])
    df["discount_amount"] = df["gross_sales"] - df["sales"]
    df["is_loss"] = df["profit"].lt(0)
    df = add_discount_band(df)
    df = df.sort_values("order_date", kind="stable").reset_index(drop=True)
    df["row_id"] = np.arange(1, len(df) + 1)
    df = df[OUTPUT_COLUMNS]

    result.capabilities = _capabilities(df, m)
    result.data = df
    result.rows_out = len(df)
    if len(df) < SMALL_DATA_ROWS:
        result.add("warning", f"Only {_plural(len(df), 'row')} - many charts and tests need more data.")
    result.add("info", f"{result.rows_out:,} of {result.rows_in:,} rows ready, "
                       f"{df['order_date'].min():%d %b %Y} - {df['order_date'].max():%d %b %Y}.")
    return result


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Same columns and values as features.add_time_features(), without formatting
    every date as text (much faster on large uploads)."""
    df = df.copy()
    d = df["order_date"]
    year, month = d.dt.year.astype("int64"), d.dt.month.astype("int64")
    df["order_year"] = year
    df["order_quarter"] = d.dt.quarter.astype("int64")
    df["order_month"] = month
    df["order_month_name"] = month.map(lambda i: MONTHS[i - 1]).astype(str)
    key = year * 100 + month
    labels = {k: f"{k // 100:04d}-{k % 100:02d}" for k in key.unique()}
    df["year_month"] = key.map(labels).astype(str)
    df["order_weekday"] = d.dt.day_of_week.map(lambda i: WEEKDAYS[i]).astype(str)
    return df


def _real(df: pd.DataFrame, col: str, min_values: int = 2) -> bool:
    values = df[col][df[col] != UNKNOWN]
    return values.nunique() >= min_values


def _capabilities(df: pd.DataFrame, m: dict[str, str]) -> set[str]:
    caps = set()
    if "order_id" in m:
        caps.add("orders")
    if ("customer_id" in m or "customer_name" in m) and _real(df, "customer_id"):
        caps.add("customers")
    if ("product_name" in m or "product_id" in m) and _real(df, "product_key"):
        caps.add("products")
    if "quantity" in m and df["quantity"].notna().any():
        caps.add("quantity")
    if ("profit" in m or "cost" in m) and df["profit"].notna().mean() > 0.5:
        caps.add("profit")
    if "discount" in m and (df["discount"] > 0).any():
        caps.add("discount")
    for key in ("category", "sub_category", "region", "state", "city", "segment"):
        if key in m and _real(df, key):
            caps.add(key)
    if "state" in caps and df["state"].isin(list(STATE_CODES)).mean() >= 0.8:
        caps.add("us_map")
    if "ship_date" in m and df["ship_days"].notna().mean() > 0.5:
        caps.add("shipping")
    return caps
