"""Suggest which uploaded column holds which standard field.

Two signals:
1. The column name, compared with each field's list of common names.
2. The values: a date field must hold dates, a money field numbers, and so on.
The result is only a suggestion - the user confirms or changes it in the app.
"""

from __future__ import annotations

import pandas as pd

from salesinsight.upload.parsing import date_ratio, number_ratio
from salesinsight.upload.schema import FIELDS, SALES_ALTERNATIVE, normalise

STRONG = 100      # exact name match
PARTIAL = 70      # the name contains a common name (e.g. "Order Date (dd/mm)")
VALUES_ONLY = 35  # no name match, but the values fit (only used for the order date)
MIN_SCORE = 50


def name_score(column: str, synonyms: tuple[str, ...], kind: str = "money") -> int:
    """Exact match 100; partial match ~70-85. For text and ID fields, short generic words
    ("type", "group", "area") must match exactly - "Payment Type" is not a product type."""
    min_partial = 6 if kind in ("text", "id") else 4
    col = normalise(column)
    if not col:
        return 0
    best = 0
    for syn in synonyms:
        s = normalise(syn)
        if col == s:
            return STRONG
        if len(s) >= min_partial and (col.startswith(s) or col.endswith(s) or (len(s) >= 6 and s in col)):
            # longer common names are more specific -> slightly higher score
            best = max(best, PARTIAL + min(len(s), 15))
    return best


def values_fit(series: pd.Series, kind: str) -> float:
    """0-1: how well the values fit the field type."""
    if kind == "date":
        return date_ratio(series)
    if kind == "percent":
        return number_ratio(series.astype(str).str.replace("%", "", regex=False))
    if kind in ("money", "number"):
        return number_ratio(series)
    if kind == "text":
        # text fields should not be (almost) all numbers with decimals
        r = number_ratio(series)
        return 0.3 if r > 0.9 else 1.0
    return 1.0   # ids can be anything


def score_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for order, f in enumerate(FIELDS):
        for col in df.columns:
            name = name_score(col, f.synonyms, f.kind)
            if name == 0 and not (f.key == "order_date"):
                continue
            fit = values_fit(df[col], f.kind)
            if f.kind in ("date", "money", "number", "percent") and fit < 0.8:
                continue
            score = name * fit if name else (VALUES_ONLY if fit >= 0.9 else 0)
            if score > 0:
                rows.append({"field": f.key, "column": col, "score": round(score, 1), "order": order})
    return pd.DataFrame(rows, columns=["field", "column", "score", "order"])


def suggest_mapping(df: pd.DataFrame) -> tuple[dict[str, str | None], dict[str, float]]:
    """Returns ({field: column or None}, {field: confidence 0-100})."""
    table = score_table(df)
    mapping: dict[str, str | None] = {f.key: None for f in FIELDS}
    confidence: dict[str, float] = {}
    used: set[str] = set()
    if not table.empty:
        table = table.sort_values(["score", "order"], ascending=[False, True])
        for row in table.itertuples(index=False):
            threshold = VALUES_ONLY if row.field == "order_date" else MIN_SCORE
            if row.score < threshold or mapping[row.field] is not None or row.column in used:
                continue
            mapping[row.field] = row.column
            confidence[row.field] = min(100.0, float(row.score))
            used.add(row.column)
    # A unit price is only needed when there is no sales column.
    if mapping["sales"] is not None and mapping["unit_price"] is not None:
        confidence.pop("unit_price", None)
        mapping["unit_price"] = None
    return mapping, confidence


def sales_like_problem(df: pd.DataFrame) -> str | None:
    """A plain-language reason why the file does not look like sales data, or None."""
    has_date = any(date_ratio(df[c]) >= 0.8 for c in df.columns)
    has_number = any(number_ratio(df[c]) >= 0.8 for c in df.columns)
    if has_date and has_number:
        return None
    missing = []
    if not has_date:
        missing.append("date column")
    if not has_number:
        missing.append("column with amounts")
    return ("This doesn't look like sales data: no " + " and no ".join(missing) + " was found. "
            "SalesInsight needs at least the date of each sale and its amount. "
            f"(Sales can also be calculated from {SALES_ALTERNATIVE[0].replace('_', ' ')} x quantity.)")
