"""Turn messy text from real business files into numbers and dates.

Handles, for example:
    "₹1,25,000.50"  "$ 1,250"  "Rs. 300"  "(500)"  "500-"  "1.234,56"  ->  numbers
    "20%"  "0.2"  "20"                                                 ->  0.20
    "05/03/2024" (day first or month first)  "2024-03-05"  "5 Mar 2024"
    Excel date numbers (45356)                                          ->  dates
"""

from __future__ import annotations

import re
import warnings

import numpy as np
import pandas as pd

MISSING_TEXT = {"", "-", "--", "na", "n/a", "nan", "none", "null", "nil", "#n/a", "?"}
CURRENCY_RE = re.compile(r"(₹|\$|€|£|¥|\brs\.?|\binr\b|\busd\b|\beur\b|\bgbp\b)", re.IGNORECASE)
EUROPEAN_RE = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d{1,2}$|^-?\d+,\d{1,2}$")
DMY_RE = re.compile(r"^\s*(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})")
ISO_RE = re.compile(r"^\s*\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2}")

CURRENCY_SYMBOLS = {"₹": "₹", "rs": "₹", "inr": "₹", "$": "$", "usd": "$", "€": "€", "eur": "€",
                    "£": "£", "gbp": "£", "¥": "¥"}


def is_missing(value: object) -> bool:
    return value is None or (isinstance(value, float) and np.isnan(value)) or \
        str(value).strip().lower() in MISSING_TEXT


def _clean_number_text(value: object) -> str | None:
    if is_missing(value):
        return None
    s = str(value).strip()
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1]
    s = CURRENCY_RE.sub("", s).strip()
    if s.endswith("-") and not s.startswith("-"):
        negative, s = True, s[:-1]
    s = s.replace(" ", "").replace(" ", "").replace(" ", "").replace("'", "")
    if EUROPEAN_RE.match(s):                       # 1.234,56 -> 1234.56
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")                     # 1,25,000.50 -> 125000.50
    if s.startswith("+"):
        s = s[1:]
    if negative and not s.startswith("-"):
        s = "-" + s
    return s


def parse_number(series: pd.Series) -> pd.Series:
    """Numbers from text; anything that is not a number becomes NaN."""
    if pd.api.types.is_numeric_dtype(series):
        return series.astype("float64")
    # Fast path: most values are plain numbers already.
    direct = pd.to_numeric(series, errors="coerce")
    todo = direct.isna() & series.notna()
    if todo.any():
        direct.loc[todo] = pd.to_numeric(clean_number_texts(series.loc[todo]), errors="coerce")
    return direct.astype("float64")


def clean_number_texts(series: pd.Series) -> pd.Series:
    """Column-wide version of _clean_number_text (same rules, much faster on big files)."""
    s = series.astype(str).str.strip()
    missing = s.str.lower().isin(MISSING_TEXT)
    paren = s.str.startswith("(") & s.str.endswith(")")
    s = s.where(~paren, s.str[1:-1])
    s = s.str.replace(CURRENCY_RE, "", regex=True).str.strip()
    trailing = s.str.endswith("-") & ~s.str.startswith("-")
    s = s.where(~trailing, s.str[:-1])
    s = s.str.replace(r"[\s\u00a0\u2009']", "", regex=True)
    euro = s.str.match(EUROPEAN_RE)
    s = s.where(~euro, s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    s = s.where(euro, s.str.replace(",", "", regex=False))
    s = s.str.lstrip("+")
    neg = (paren | trailing) & ~s.str.startswith("-")
    s = s.where(~neg, "-" + s)
    return s.where(~missing, None)


def parse_percent(series: pd.Series) -> pd.Series:
    """Rates as fractions: '20%' -> 0.2, 0.2 -> 0.2, and a column of 0-100 values -> /100."""
    text = series.astype(str)
    had_percent = text.str.contains("%", regex=False)
    values = parse_number(text.str.replace("%", "", regex=False))
    values = values.where(~had_percent, values / 100)
    plain = values[~had_percent].dropna()
    if len(plain) and plain.max() > 1 and plain.max() <= 100:
        values = values.where(had_percent, values / 100)
    return values


def number_ratio(series: pd.Series, sample: int = 500) -> float:
    """Share of non-empty values that are numbers (used to check a mapping)."""
    values = series[~series.map(is_missing)].head(sample)
    if values.empty:
        return 0.0
    return float(parse_number(values).notna().mean())


def detect_currency(series: pd.Series) -> str | None:
    """'₹', '$', '€', ... if the sales text carries a currency mark."""
    text = " ".join(series.astype(str).head(200)).lower()
    for mark in ("₹", "rs", "inr", "€", "eur", "£", "gbp", "¥", "$", "usd"):
        found = (mark in text) if len(mark) == 1 else bool(re.search(rf"\b{re.escape(mark)}\b", text))
        if found:
            return CURRENCY_SYMBOLS[mark]
    return None


def present_text(series: pd.Series) -> pd.Series:
    """Trimmed text with empty / 'N/A'-style values as None (column-wide)."""
    s = series.astype(object).where(series.notna(), None)
    t = s.astype(str).str.strip()
    return t.where(series.notna() & ~t.str.lower().isin(MISSING_TEXT), None)


# --- Dates -----------------------------------------------------------------------------
def _formats(dayfirst: bool) -> list[str]:
    first = ["%d{s}%m{s}%Y", "%d{s}%m{s}%y"] if dayfirst else ["%m{s}%d{s}%Y", "%m{s}%d{s}%y"]
    out = []
    for base in first:
        for sep in ("/", "-", "."):
            core = base.format(s=sep)
            out += [core, core + " %H:%M", core + " %H:%M:%S", core + " %I:%M %p", core + " %I:%M:%S %p"]
    return out


ISO_FORMATS = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
               "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"]


def date_order(series: pd.Series) -> str:
    """'iso', 'day-first', 'month-first', 'ambiguous' (all parts <= 12), 'excel' or 'other'."""
    values = present_text(series).dropna().head(5000)
    if values.empty:
        return "other"
    numeric = pd.to_numeric(values, errors="coerce")
    if numeric.notna().mean() > 0.9 and numeric.between(20000, 80000).mean() > 0.9:
        return "excel"
    if values.str.match(ISO_RE).mean() > 0.8:
        return "iso"
    parts = values.str.extract(DMY_RE).dropna()
    if len(parts) < 0.8 * len(values):
        return "other"
    first, second = parts[0].astype(int), parts[1].astype(int)
    day_first_votes, month_first_votes = int((first > 12).sum()), int((second > 12).sum())
    if day_first_votes and not month_first_votes:
        return "day-first"
    if month_first_votes and not day_first_votes:
        return "month-first"
    if day_first_votes and month_first_votes:
        return "day-first" if day_first_votes >= month_first_votes else "month-first"
    return "ambiguous"


def _best_format(values: pd.Series, formats: list[str]) -> str | None:
    sample = values.head(500)
    best, best_ok = None, 0.0
    for fmt in formats:
        ok = pd.to_datetime(sample, format=fmt, errors="coerce").notna().mean()
        if ok > best_ok:
            best, best_ok = fmt, ok
    return best if best_ok >= 0.95 else None


def parse_dates(series: pd.Series, dayfirst: bool | None = None) -> tuple[pd.Series, str]:
    """Parse a date column. Returns (dates, order) - order as in date_order().

    dayfirst: the user's choice for dates like 05/03/2024. None = decide from the
    data (if the data cannot tell, day first is used and the order is 'ambiguous').
    """
    if pd.api.types.is_datetime64_any_dtype(series):
        return series.dt.tz_localize(None) if series.dt.tz is not None else series, "excel"
    text = present_text(series)
    order = date_order(series)
    if order == "excel":
        nums = pd.to_numeric(text, errors="coerce")
        return pd.to_datetime(nums, unit="D", origin="1899-12-30", errors="coerce").dt.floor("s"), order

    if dayfirst is None:
        dayfirst = order != "month-first"
    candidates = ISO_FORMATS if order == "iso" else _formats(dayfirst) + ISO_FORMATS
    present = text.dropna()
    fmt = _best_format(present, candidates) if len(present) else None
    if fmt:
        parsed = pd.to_datetime(text, format=fmt, errors="coerce")
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parsed = pd.to_datetime(text, format="mixed", dayfirst=dayfirst, errors="coerce")
    return parsed, order


def date_ratio(series: pd.Series, sample: int = 300) -> float:
    """Share of non-empty values that are dates (used to check a mapping)."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return float(series.notna().mean()) if len(series) else 0.0
    values = series[~series.map(is_missing)].head(sample)
    if values.empty:
        return 0.0
    # Plain numbers are not dates unless they look like Excel date numbers.
    nums = pd.to_numeric(values.astype(str), errors="coerce")
    if nums.notna().mean() > 0.5 and not nums.between(20000, 80000).mean() > 0.9:
        return 0.0
    parsed, _ = parse_dates(values)
    return float(parsed.notna().mean())
