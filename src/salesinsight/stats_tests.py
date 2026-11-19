"""Phase 10: statistical analysis.

The earlier phases found patterns (e.g. "high discounts lose money").
This module checks whether each pattern is real or could just be chance,
and how big the effect is.

Two numbers matter for every test:
- p-value: the chance of seeing a difference this big if there were really
  no difference. Small (below 0.05) = unlikely to be chance = "significant".
- effect size: how BIG the difference is. With ~10,000 rows even tiny
  differences become "significant", so the effect size tells us whether
  the difference matters in practice.

Why mostly non-parametric tests (Spearman, Kruskal-Wallis, Mann-Whitney)?
Sales and margins are skewed with long tails (a few huge orders, a few
huge losses), so tests that assume a normal distribution are less reliable.
The classic tests (Pearson, ANOVA, t-test) are reported alongside for comparison.

File name is stats_tests.py, not statistics.py, so it does not clash with
Python's built-in "statistics" module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from scipy import stats

from salesinsight import config

ALPHA = 0.05
DISCOUNT_BAND_ORDER = ["No discount", "1-20%", "21-40%", "Over 40%"]


@dataclass
class TestResult:
    test: str
    question: str
    method: str
    statistic: float
    p_value: float
    effect_size: float
    effect_measure: str
    effect_label: str
    n: int
    significant: bool
    conclusion: str


# ---------------------------------------------------------------------------
# Helpers: plain-English wording
# ---------------------------------------------------------------------------
def describe_p(p: float) -> str:
    if p < 0.001:
        return "very unlikely to be chance (p < 0.001)"
    if p < ALPHA:
        return f"statistically significant (p = {p:.3f})"
    return f"possibly due to chance (p = {p:.2f})"


def effect_label(value: float, kind: str) -> str:
    """Conventional thresholds (Cohen) for how big an effect is."""
    v = abs(value)
    if kind in ("r", "v"):                 # correlation, Cramer's V, rank-biserial
        cuts = (0.1, 0.3, 0.5)
    elif kind == "eta":                    # eta-squared / epsilon-squared
        cuts = (0.01, 0.06, 0.14)
    else:
        raise ValueError(kind)
    if v < cuts[0]:
        return "negligible"
    if v < cuts[1]:
        return "small"
    if v < cuts[2]:
        return "medium"
    return "large"


def line_margin(df: pd.DataFrame) -> pd.Series:
    """Profit margin % of each order line."""
    return 100 * df["profit"] / df["sales"]


# ---------------------------------------------------------------------------
# Effect sizes
# ---------------------------------------------------------------------------
def cramers_v(table: pd.DataFrame) -> float:
    """Strength of association between two categorical variables (0 = none, 1 = perfect)."""
    chi2 = stats.chi2_contingency(table, correction=False)[0]
    n = table.to_numpy().sum()
    k = min(table.shape) - 1
    return float(np.sqrt(chi2 / (n * k))) if k > 0 else float("nan")


def epsilon_squared(h: float, n: int, k: int) -> float:
    """Effect size for Kruskal-Wallis: share of rank variation explained by the groups."""
    return float(max(0.0, (h - k + 1) / (n - k)))     # tiny negatives -> 0


def rank_biserial(u: float, n1: int, n2: int) -> float:
    """Effect size for Mann-Whitney U, from -1 to 1.

    Positive = values in group 1 tend to be larger than in group 2.
    """
    return float(2 * u / (n1 * n2) - 1)


# ---------------------------------------------------------------------------
# The tests
# ---------------------------------------------------------------------------
def test_discount_vs_margin(df: pd.DataFrame) -> TestResult:
    """Q: do order lines with a higher discount have a lower profit margin?"""
    margin = line_margin(df)
    rho, p = stats.spearmanr(df["discount"], margin)
    pearson_r = stats.pearsonr(df["discount"], margin)[0]
    direction = "lower" if rho < 0 else "higher"
    return TestResult(
        test="discount_vs_margin",
        question="Do bigger discounts go with lower profit margins?",
        method=f"Spearman rank correlation (Pearson r = {pearson_r:.2f} for comparison)",
        statistic=float(rho), p_value=float(p), effect_size=float(rho),
        effect_measure="Spearman rho", effect_label=effect_label(rho, "r"), n=len(df),
        significant=p < ALPHA,
        conclusion=(f"Higher discounts go with {direction} margins (rho = {rho:.2f}, "
                    f"{effect_label(rho, 'r')} effect); {describe_p(p)}."),
    )


def test_discount_vs_loss(df: pd.DataFrame) -> TestResult:
    """Q: does the chance of a loss depend on the discount band?"""
    table = pd.crosstab(df["discount_band"], df["is_loss"])
    chi2, p, dof, _ = stats.chi2_contingency(table, correction=False)
    v = cramers_v(table)
    loss_rate = df.groupby("discount_band")["is_loss"].mean().mul(100)
    loss_rate = loss_rate.reindex([b for b in DISCOUNT_BAND_ORDER if b in loss_rate.index])
    rates = ", ".join(f"{band}: {rate:.0f}%" for band, rate in loss_rate.items())
    return TestResult(
        test="discount_vs_loss",
        question="Does the chance of an order line losing money depend on the discount level?",
        method=f"Chi-square test of independence ({dof} degrees of freedom)",
        statistic=float(chi2), p_value=float(p), effect_size=v,
        effect_measure="Cramer's V", effect_label=effect_label(v, "v"), n=len(df),
        significant=p < ALPHA,
        conclusion=f"Share of loss-making lines by discount - {rates}. "
                   f"Association is {effect_label(v, 'v')} (V = {v:.2f}); {describe_p(p)}.",
    )


def _groups_test(df: pd.DataFrame, values: pd.Series, by: str, name: str, question: str,
                 what: str) -> TestResult:
    """Kruskal-Wallis across groups (plus one-way ANOVA for comparison)."""
    groups = [values[df[by] == g].to_numpy() for g in sorted(df[by].unique())]
    n, k = len(values), len(groups)
    if values.nunique() <= 1:
        # Every value is identical: there is nothing to test, so no difference.
        h, p, f, p_anova = 0.0, 1.0, 0.0, 1.0
    else:
        h, p = stats.kruskal(*groups)
        f, p_anova = stats.f_oneway(*groups)
    eps = epsilon_squared(h, n, k)
    medians = values.groupby(df[by]).median().sort_values(ascending=False)
    med_text = ", ".join(f"{g}: {m:.1f}" for g, m in medians.items())
    return TestResult(
        test=name, question=question,
        method=f"Kruskal-Wallis H test (ANOVA F = {f:.1f}, p = {p_anova:.3g} for comparison)",
        statistic=float(h), p_value=float(p), effect_size=eps,
        effect_measure="epsilon-squared", effect_label=effect_label(eps, "eta"), n=n,
        significant=p < ALPHA,
        conclusion=f"Median {what} - {med_text}. The differences are {describe_p(p)}; "
                   f"effect size is {effect_label(eps, 'eta')} (epsilon-squared = {eps:.3f}).",
    )


def test_region_margin(df: pd.DataFrame) -> TestResult:
    return _groups_test(df, line_margin(df), "region", "region_margin",
                        "Do profit margins really differ between regions?", "line margin % by region")


def test_segment_order_value(df: pd.DataFrame) -> TestResult:
    orders = df.groupby("order_id").agg(order_value=("sales", "sum"), segment=("segment", "first"))
    return _groups_test(orders, orders["order_value"], "segment", "segment_order_value",
                        "Do Consumer, Corporate and Home Office orders differ in value?",
                        "order value ($) by segment")


def test_category_margin(df: pd.DataFrame, category: str = "Furniture") -> TestResult:
    """Q: is the margin of one category lower than all other categories combined?"""
    margin = line_margin(df)
    a = margin[df["category"] == category]
    b = margin[df["category"] != category]
    u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    t, p_t = stats.ttest_ind(a, b, equal_var=False)
    r = rank_biserial(u, len(a), len(b))
    direction = "lower" if a.median() < b.median() else "higher"
    return TestResult(
        test=f"{category.lower().replace(' ', '_')}_margin",
        question=f"Is the {category} margin really {direction} than the other categories?",
        method=f"Mann-Whitney U test (Welch t-test p = {p_t:.3g} for comparison)",
        statistic=float(u), p_value=float(p), effect_size=r,
        effect_measure="rank-biserial r", effect_label=effect_label(r, "r"), n=len(margin),
        significant=p < ALPHA,
        conclusion=(f"Median line margin: {category} {a.median():.1f}% vs others {b.median():.1f}% "
                    f"({direction}); {describe_p(p)}; effect is {effect_label(r, 'r')} (r = {r:.2f})."),
    )


def test_q4_vs_rest(df: pd.DataFrame) -> TestResult:
    """Q: are Q4 months (Oct-Dec) really bigger than other months?"""
    monthly = df.groupby([df["order_date"].dt.to_period("M")])["sales"].sum()
    q4 = monthly[monthly.index.quarter == 4]
    rest = monthly[monthly.index.quarter != 4]
    t, p = stats.ttest_ind(q4, rest, equal_var=False)
    pooled_sd = np.sqrt((q4.var(ddof=1) + rest.var(ddof=1)) / 2)
    d = float((q4.mean() - rest.mean()) / pooled_sd) if pooled_sd else float("nan")
    label = "negligible" if abs(d) < 0.2 else "small" if abs(d) < 0.5 else "medium" if abs(d) < 0.8 else "large"
    return TestResult(
        test="q4_vs_rest",
        question="Is monthly revenue really higher in Q4 (Oct-Dec) than in other months?",
        method="Welch t-test on monthly revenue",
        statistic=float(t), p_value=float(p), effect_size=d,
        effect_measure="Cohen's d", effect_label=label, n=len(monthly),
        significant=p < ALPHA,
        conclusion=(f"Average Q4 month ${q4.mean():,.0f} vs other months ${rest.mean():,.0f}; "
                    f"{describe_p(p)}; {label} effect (d = {d:.2f})."),
    )


def bootstrap_ci(values: np.ndarray, statistic=np.mean, n_boot: int = 2000,
                 level: float = 95, seed: int = config.RANDOM_SEED) -> tuple[float, float, float]:
    """Bootstrap confidence interval: resample with replacement many times.

    Returns (estimate, lower, upper). Same seed -> same result every run.
    """
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(values), size=(n_boot, len(values)))
    boots = statistic(values[idx], axis=1)
    tail = (100 - level) / 2
    lower, upper = np.percentile(boots, [tail, 100 - tail])
    return float(statistic(values)), float(lower), float(upper)


def aov_confidence_by_year(df: pd.DataFrame) -> pd.DataFrame:
    """95% bootstrap confidence interval of average order value for each year."""
    orders = df.groupby(["order_year", "order_id"])["sales"].sum().reset_index()
    rows = []
    for year, g in orders.groupby("order_year"):
        est, lo, hi = bootstrap_ci(g["sales"].to_numpy())
        rows.append({"order_year": year, "orders": len(g), "avg_order_value": est,
                     "ci_lower": lo, "ci_upper": hi})
    return pd.DataFrame(rows)


def descriptive_statistics(df: pd.DataFrame) -> pd.DataFrame:
    """Mean, median, spread, skewness and outliers (IQR rule) for the main numbers."""
    cols = {"sales": df["sales"], "profit": df["profit"], "quantity": df["quantity"],
            "discount": df["discount"], "profit_margin_pct": line_margin(df)}
    rows = []
    for name, s in cols.items():
        q1, q3 = s.quantile([0.25, 0.75])
        iqr = q3 - q1
        outliers = int(((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum())
        rows.append({
            "variable": name, "count": int(s.count()), "mean": s.mean(), "median": s.median(),
            "std": s.std(), "min": s.min(), "q1": q1, "q3": q3, "max": s.max(),
            "skewness": float(stats.skew(s)) if s.nunique() > 1 else 0.0, "outliers_iqr": outliers,
            "outliers_pct": 100 * outliers / s.count(),
        })
    return pd.DataFrame(rows)


def run_all_tests(df: pd.DataFrame) -> list[TestResult]:
    return [
        test_discount_vs_margin(df),
        test_discount_vs_loss(df),
        test_region_margin(df),
        test_segment_order_value(df),
        test_category_margin(df, "Furniture"),
        test_q4_vs_rest(df),
    ]


def results_to_frame(results: list[TestResult]) -> pd.DataFrame:
    return pd.DataFrame([asdict(r) for r in results])
